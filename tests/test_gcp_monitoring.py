"""
================================================================================
test_gcp_monitoring.py - GCP Cloud Logging/Trace統合テスト
================================================================================

【概要】
GCP Cloud Logging/Trace統合機能のユニットテストです。
GCPパッケージが未インストールでもテストが動作します。

【テスト項目】
1. GCPMonitoringクラスの初期化
2. スパン開始・終了（モック）
3. カスタムメトリクス送信
4. 例外記録（Error Reporting）
5. 依存関係記録

【実行方法】
pytest tests/test_gcp_monitoring.py -v

================================================================================
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.infrastructure.monitoring.gcp_monitoring import GCPMonitoring


# =============================================================================
# テスト: 初期化
# =============================================================================

def test_gcp_monitoring_init_without_project_id():
    """プロジェクトIDなしで初期化した場合、無効化されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = GCPMonitoring()
        assert monitor.enabled is False
        assert monitor.logging_client is None
        assert monitor.tracer is None


def test_gcp_monitoring_init_with_project_id():
    """プロジェクトIDありで初期化した場合、有効化されることを検証"""
    test_project_id = "test-gcp-project"

    with patch.dict("os.environ", {"GCP_PROJECT": test_project_id}):
        with patch("src.infrastructure.monitoring.gcp_monitoring.cloud_logging.Client") as mock_logging_client:
            with patch("src.infrastructure.monitoring.gcp_monitoring.stackdriver_exporter.StackdriverExporter"):
                with patch("src.infrastructure.monitoring.gcp_monitoring.Tracer") as mock_tracer:
                    monitor = GCPMonitoring()

                    # モック環境では有効化されることを確認
                    assert monitor.enabled is True


# =============================================================================
# テスト: スパン開始・終了
# =============================================================================

def test_start_span_disabled():
    """監視無効時、ダミースパンが返されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = GCPMonitoring()

        with monitor.start_span("test_span", "corr-123") as span:
            # ダミースパンのメソッドが呼び出せることを確認
            span.add_attribute("test_key", "test_value")


def test_start_span_with_correlation_id():
    """相関ID付きスパンが正しく開始されることを検証（モック）"""
    test_project_id = "test-gcp-project"
    correlation_id = "test-correlation-id-123"

    with patch.dict("os.environ", {"GCP_PROJECT": test_project_id}):
        with patch("src.infrastructure.monitoring.gcp_monitoring.cloud_logging.Client") as mock_logging_client:
            with patch("src.infrastructure.monitoring.gcp_monitoring.stackdriver_exporter.StackdriverExporter"):
                with patch("src.infrastructure.monitoring.gcp_monitoring.Tracer") as mock_tracer_class:
                    # モックTracer
                    mock_span = MagicMock()
                    mock_tracer = MagicMock()
                    mock_tracer.span.return_value.__enter__.return_value = mock_span
                    mock_tracer_class.return_value = mock_tracer

                    monitor = GCPMonitoring()

                    with monitor.start_span("test_operation", correlation_id) as span:
                        pass

                    # スパンが開始された
                    mock_tracer.span.assert_called_once()

                    # 相関IDが属性として追加された
                    mock_span.add_attribute.assert_any_call("correlation_id", correlation_id)
                    mock_span.add_attribute.assert_any_call("platform", "gcp")


# =============================================================================
# テスト: カスタムメトリクス
# =============================================================================

def test_track_metric_disabled():
    """監視無効時、ローカルコレクターにのみ記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = GCPMonitoring()
        monitor.clear_metrics()

        monitor.track_metric("test_metric", 100, {"platform": "gcp"})

        # ローカルメトリクスに記録されている
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].name == "test_metric"
        assert metrics[0].value == 100


def test_track_metric_enabled():
    """監視有効時、Cloud Loggingに構造化ログとして送信されることを検証（モック）"""
    test_project_id = "test-gcp-project"

    with patch.dict("os.environ", {"GCP_PROJECT": test_project_id}):
        with patch("src.infrastructure.monitoring.gcp_monitoring.cloud_logging.Client") as mock_logging_client_class:
            with patch("src.infrastructure.monitoring.gcp_monitoring.stackdriver_exporter.StackdriverExporter"):
                with patch("src.infrastructure.monitoring.gcp_monitoring.Tracer"):
                    # モックCloudLogger
                    mock_cloud_logger = MagicMock()
                    mock_logging_client = MagicMock()
                    mock_logging_client.logger.return_value = mock_cloud_logger
                    mock_logging_client_class.return_value = mock_logging_client

                    monitor = GCPMonitoring()
                    monitor.clear_metrics()

                    monitor.track_metric("request_total", 10, {"endpoint": "/evaluate"})

                    # Cloud Loggingにlog_structが呼ばれた
                    mock_cloud_logger.log_struct.assert_called_once()

                    # ログエントリに正しいデータが含まれることを確認
                    call_args = mock_cloud_logger.log_struct.call_args
                    log_entry = call_args[0][0]
                    assert log_entry["metric_name"] == "request_total"
                    assert log_entry["metric_value"] == 10
                    assert log_entry["labels"]["endpoint"] == "/evaluate"


# =============================================================================
# テスト: 例外記録
# =============================================================================

def test_track_exception_disabled():
    """監視無効時、エラーメトリクスのみ記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = GCPMonitoring()
        monitor.clear_metrics()

        exception = ValueError("Test error")
        monitor.track_exception(exception, "corr-789", {"service": "vertex_ai"})

        # エラーメトリクスが記録されている
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].name == "error_total"
        assert metrics[0].dimensions["error_type"] == "ValueError"


def test_track_exception_enabled():
    """監視有効時、Cloud Error Reportingに送信されることを検証（モック）"""
    test_project_id = "test-gcp-project"

    with patch.dict("os.environ", {"GCP_PROJECT": test_project_id}):
        with patch("src.infrastructure.monitoring.gcp_monitoring.cloud_logging.Client") as mock_logging_client_class:
            with patch("src.infrastructure.monitoring.gcp_monitoring.stackdriver_exporter.StackdriverExporter"):
                with patch("src.infrastructure.monitoring.gcp_monitoring.Tracer"):
                    # モックCloudLogger
                    mock_cloud_logger = MagicMock()
                    mock_logging_client = MagicMock()
                    mock_logging_client.logger.return_value = mock_cloud_logger
                    mock_logging_client_class.return_value = mock_logging_client

                    monitor = GCPMonitoring()
                    monitor.clear_metrics()

                    exception = RuntimeError("Test runtime error")
                    monitor.track_exception(exception, "corr-xyz", {"operation": "document_ai"})

                    # Cloud Loggingにエラーログが送信された
                    mock_cloud_logger.log_struct.assert_called_once()

                    # ログレベルがERROR
                    call_args = mock_cloud_logger.log_struct.call_args
                    assert call_args[1]["severity"] == "ERROR"


# =============================================================================
# テスト: 依存関係記録
# =============================================================================

def test_track_dependency():
    """依存関係呼び出しが記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = GCPMonitoring()
        monitor.clear_metrics()

        monitor.track_dependency(
            name="vertex_ai_invoke",
            dependency_type="Vertex AI",
            target="gemini-3-pro",
            duration_ms=280.5,
            success=True,
            correlation_id="corr-999"
        )

        # 処理時間メトリクスが記録されている
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].name == "vertex_ai_invoke_duration_ms"
        assert metrics[0].value == 280.5
        assert metrics[0].dimensions["dependency_type"] == "Vertex AI"
        assert metrics[0].dimensions["success"] == "True"


# =============================================================================
# まとめ
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
