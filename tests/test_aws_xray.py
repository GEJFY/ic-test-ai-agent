"""
================================================================================
test_aws_xray.py - AWS X-Ray統合テスト
================================================================================

【概要】
AWS X-Ray統合機能のユニットテストです。
aws-xray-sdkが未インストールでもテストが動作します。

【テスト項目】
1. AWSXRayクラスの初期化
2. サブセグメント開始・終了（モック）
3. カスタムメトリクス記録
4. 例外記録
5. 依存関係記録

【実行方法】
pytest tests/test_aws_xray.py -v

================================================================================
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.infrastructure.monitoring.aws_xray import AWSXRay


# =============================================================================
# テスト: 初期化
# =============================================================================

def test_aws_xray_init_without_sdk():
    """X-Ray SDK未インストール時、無効化されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        with patch("src.infrastructure.monitoring.aws_xray.xray_recorder", None):
            monitor = AWSXRay()
            assert monitor.enabled is False
            assert monitor.xray_recorder is None


def test_aws_xray_init_with_lambda_env():
    """Lambda環境で初期化されることを検証"""
    with patch.dict("os.environ", {"AWS_LAMBDA_FUNCTION_NAME": "test-function"}):
        with patch("src.infrastructure.monitoring.aws_xray.xray_recorder") as mock_recorder:
            with patch("src.infrastructure.monitoring.aws_xray.patch_all"):
                monitor = AWSXRay()
                assert monitor.enabled is True


# =============================================================================
# テスト: サブセグメント開始・終了
# =============================================================================

def test_start_span_disabled():
    """監視無効時、ダミーセグメントが返されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = AWSXRay()
        monitor.enabled = False

        with monitor.start_span("test_span", "corr-123") as segment:
            # ダミーセグメントのメソッドが呼び出せることを確認
            segment.put_annotation("test_key", "test_value")
            segment.put_metadata("test_metadata", "test_data")


def test_start_span_with_correlation_id():
    """相関ID付きサブセグメントが正しく開始されることを検証（モック）"""
    correlation_id = "test-correlation-id-789"

    with patch.dict("os.environ", {"AWS_LAMBDA_FUNCTION_NAME": "test-func"}):
        with patch("src.infrastructure.monitoring.aws_xray.xray_recorder") as mock_recorder_module:
            with patch("src.infrastructure.monitoring.aws_xray.patch_all"):
                # モックRecorder
                mock_recorder = MagicMock()
                mock_subsegment = MagicMock()
                mock_recorder.begin_subsegment.return_value = mock_subsegment
                mock_recorder_module.xray_recorder = mock_recorder

                monitor = AWSXRay()
                monitor.xray_recorder = mock_recorder

                with monitor.start_span("test_operation", correlation_id) as segment:
                    pass

                # サブセグメントが開始された
                mock_recorder.begin_subsegment.assert_called_once_with("test_operation")

                # 相関IDがアノテーションとして追加された
                mock_subsegment.put_annotation.assert_any_call("correlation_id", correlation_id)
                mock_subsegment.put_annotation.assert_any_call("platform", "aws")

                # サブセグメントが終了された
                mock_recorder.end_subsegment.assert_called_once()


# =============================================================================
# テスト: カスタムメトリクス
# =============================================================================

def test_track_metric_disabled():
    """監視無効時、ローカルコレクターにのみ記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = AWSXRay()
        monitor.clear_metrics()

        monitor.track_metric("test_metric", 100, {"platform": "aws"})

        # ローカルメトリクスに記録されている
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].name == "test_metric"
        assert metrics[0].value == 100


def test_track_metric_enabled():
    """監視有効時、現在のセグメントにメタデータとして記録されることを検証（モック）"""
    with patch.dict("os.environ", {"AWS_LAMBDA_FUNCTION_NAME": "test-func"}):
        with patch("src.infrastructure.monitoring.aws_xray.xray_recorder") as mock_recorder_module:
            with patch("src.infrastructure.monitoring.aws_xray.patch_all"):
                # モックRecorder
                mock_recorder = MagicMock()
                mock_segment = MagicMock()
                mock_recorder.current_segment.return_value = mock_segment
                mock_recorder_module.xray_recorder = mock_recorder

                monitor = AWSXRay()
                monitor.xray_recorder = mock_recorder
                monitor.clear_metrics()

                monitor.track_metric("request_total", 5, {"endpoint": "/evaluate"})

                # セグメントにメタデータが追加された（メトリクスとして）
                mock_segment.put_metadata.assert_called_once()


# =============================================================================
# テスト: 例外記録
# =============================================================================

def test_track_exception_disabled():
    """監視無効時、エラーメトリクスのみ記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = AWSXRay()
        monitor.clear_metrics()

        exception = ValueError("Test error")
        monitor.track_exception(exception, "corr-456", {"service": "bedrock"})

        # エラーメトリクスが記録されている
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].name == "error_total"
        assert metrics[0].dimensions["error_type"] == "ValueError"


# =============================================================================
# テスト: 依存関係記録
# =============================================================================

def test_track_dependency():
    """依存関係呼び出しが記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = AWSXRay()
        monitor.clear_metrics()

        monitor.track_dependency(
            name="bedrock_invoke",
            dependency_type="Bedrock",
            target="anthropic.claude-opus-4-20250514",
            duration_ms=350.0,
            success=True,
            correlation_id="corr-888"
        )

        # 処理時間メトリクスが記録されている
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].name == "bedrock_invoke_duration_ms"
        assert metrics[0].value == 350.0
        assert metrics[0].dimensions["dependency_type"] == "Bedrock"
        assert metrics[0].dimensions["success"] == "True"


# =============================================================================
# まとめ
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
