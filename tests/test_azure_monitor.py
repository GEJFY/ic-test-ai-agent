"""
================================================================================
test_azure_monitor.py - Azure Application Insights統合テスト
================================================================================

【概要】
Application Insights統合機能のユニットテストです。
OpenTelemetryパッケージが未インストールでもテストが動作します。

【テスト項目】
1. AzureMonitorクラスの初期化
2. スパン開始・終了（モック）
3. カスタムメトリクス送信
4. 例外記録
5. 依存関係記録

【実行方法】
pytest tests/test_azure_monitor.py -v

================================================================================
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from src.infrastructure.monitoring.azure_monitor import AzureMonitor


# =============================================================================
# テスト: 初期化
# =============================================================================

def test_azure_monitor_init_without_connection_string():
    """接続文字列なしで初期化した場合、無効化されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = AzureMonitor()
        assert monitor.enabled is False
        assert monitor.tracer is None


def test_azure_monitor_init_with_connection_string():
    """接続文字列ありで初期化した場合、有効化されることを検証"""
    mock_connection_string = "InstrumentationKey=test-key-123"

    with patch.dict("os.environ", {"APPLICATIONINSIGHTS_CONNECTION_STRING": mock_connection_string}):
        with patch("src.infrastructure.monitoring.azure_monitor.configure_azure_monitor"):
            with patch("src.infrastructure.monitoring.azure_monitor.trace.get_tracer") as mock_get_tracer:
                with patch("src.infrastructure.monitoring.azure_monitor.metrics.get_meter") as mock_get_meter:
                    monitor = AzureMonitor()

                    # モック環境では有効化されることを確認
                    assert monitor.enabled is True


# =============================================================================
# テスト: スパン開始・終了
# =============================================================================

def test_start_span_disabled():
    """監視無効時、ダミースパンが返されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = AzureMonitor()

        with monitor.start_span("test_span", "corr-123") as span:
            # ダミースパンのメソッドが呼び出せることを確認
            span.set_attribute("test_key", "test_value")
            span.set_status("OK")
            span.record_exception(Exception("test"))


def test_start_span_with_correlation_id():
    """相関ID付きスパンが正しく開始されることを検証（モック）"""
    mock_connection_string = "InstrumentationKey=test-key-123"
    correlation_id = "test-correlation-id-456"

    with patch.dict("os.environ", {"APPLICATIONINSIGHTS_CONNECTION_STRING": mock_connection_string}):
        with patch("src.infrastructure.monitoring.azure_monitor.configure_azure_monitor"):
            with patch("src.infrastructure.monitoring.azure_monitor.trace.get_tracer") as mock_get_tracer:
                with patch("src.infrastructure.monitoring.azure_monitor.metrics.get_meter"):
                    # モックTracerとSpan
                    mock_span = MagicMock()
                    mock_tracer = MagicMock()
                    mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
                    mock_get_tracer.return_value = mock_tracer

                    monitor = AzureMonitor()

                    with monitor.start_span("test_operation", correlation_id) as span:
                        pass

                    # 相関IDが属性として設定されたことを確認
                    mock_span.set_attribute.assert_any_call("correlation_id", correlation_id)
                    mock_span.set_attribute.assert_any_call("platform", "azure")


# =============================================================================
# テスト: カスタムメトリクス
# =============================================================================

def test_track_metric_disabled():
    """監視無効時、ローカルコレクターにのみ記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = AzureMonitor()
        monitor.clear_metrics()

        monitor.track_metric("test_metric", 100, {"platform": "azure"})

        # ローカルメトリクスに記録されている
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].name == "test_metric"
        assert metrics[0].value == 100


def test_track_metric_enabled():
    """監視有効時、Application Insightsに送信されることを検証（モック）"""
    mock_connection_string = "InstrumentationKey=test-key-123"

    with patch.dict("os.environ", {"APPLICATIONINSIGHTS_CONNECTION_STRING": mock_connection_string}):
        with patch("src.infrastructure.monitoring.azure_monitor.configure_azure_monitor"):
            with patch("src.infrastructure.monitoring.azure_monitor.trace.get_tracer"):
                with patch("src.infrastructure.monitoring.azure_monitor.metrics.get_meter") as mock_get_meter:
                    # モックMeter
                    mock_counter = MagicMock()
                    mock_meter = MagicMock()
                    mock_meter.create_counter.return_value = mock_counter
                    mock_get_meter.return_value = mock_meter

                    monitor = AzureMonitor()
                    monitor.clear_metrics()

                    monitor.track_metric("request_total", 5, {"endpoint": "/api/evaluate"})

                    # Meterでcounterが作成された
                    mock_meter.create_counter.assert_called_once()

                    # counterにaddが呼ばれた
                    mock_counter.add.assert_called_once_with(5, {"endpoint": "/api/evaluate"})


# =============================================================================
# テスト: 例外記録
# =============================================================================

def test_track_exception_disabled():
    """監視無効時、エラーメトリクスのみ記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        monitor = AzureMonitor()
        monitor.clear_metrics()

        exception = ValueError("Test error")
        monitor.track_exception(exception, "corr-789", {"service": "llm_api"})

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
        monitor = AzureMonitor()
        monitor.clear_metrics()

        monitor.track_dependency(
            name="azure_ai_foundry",
            dependency_type="HTTP",
            target="https://api.openai.azure.com",
            duration_ms=250.5,
            success=True,
            correlation_id="corr-999"
        )

        # 処理時間メトリクスが記録されている
        metrics = monitor.get_metrics()
        assert len(metrics) == 1
        assert metrics[0].name == "azure_ai_foundry_duration_ms"
        assert metrics[0].value == 250.5
        assert metrics[0].dimensions["dependency_type"] == "HTTP"
        assert metrics[0].dimensions["success"] == "True"


# =============================================================================
# まとめ
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
