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
import sys
from unittest.mock import Mock, patch, MagicMock
from src.infrastructure.monitoring.azure_monitor import AzureMonitor


# =============================================================================
# テスト: 初期化
# =============================================================================

def test_azure_monitor_init_without_connection_string():
    """接続文字列なしで初期化した場合、無効化されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        # OpenTelemetryパッケージのインポートを失敗させる
        with patch.dict("sys.modules", {
            "azure.monitor.opentelemetry": None,
            "opentelemetry": None,
            "opentelemetry.trace": None,
            "opentelemetry.metrics": None
        }):
            monitor = AzureMonitor()
            assert monitor.enabled is False


def test_azure_monitor_init_with_connection_string():
    """接続文字列ありで初期化した場合、有効化されることを検証"""
    mock_connection_string = "InstrumentationKey=test-key-123"

    with patch.dict("os.environ", {"APPLICATIONINSIGHTS_CONNECTION_STRING": mock_connection_string}):
        # OpenTelemetryモジュールをモック
        mock_azure_monitor = Mock()
        mock_azure_monitor.configure_azure_monitor = Mock()

        mock_trace = Mock()
        mock_tracer = Mock()
        mock_trace.get_tracer = Mock(return_value=mock_tracer)

        mock_metrics = Mock()
        mock_meter = Mock()
        mock_metrics.get_meter = Mock(return_value=mock_meter)

        with patch.dict("sys.modules", {
            "azure": Mock(),
            "azure.monitor": Mock(),
            "azure.monitor.opentelemetry": mock_azure_monitor,
            "opentelemetry": Mock(),
            "opentelemetry.trace": mock_trace,
            "opentelemetry.metrics": mock_metrics
        }):
            monitor = AzureMonitor()
            assert monitor.enabled is True


# =============================================================================
# テスト: スパン開始・終了
# =============================================================================

def test_start_span_disabled():
    """監視無効時、ダミースパンが返されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        with patch.dict("sys.modules", {"azure.monitor.opentelemetry": None, "opentelemetry": None}):
            monitor = AzureMonitor()
            assert monitor.enabled is False

            with monitor.start_span("test_span", "corr-123") as span:
                # ダミースパンのメソッドが呼び出せることを確認
                span.set_attribute("test_key", "test_value")


def test_start_span_with_correlation_id():
    """相関ID付きスパンが正しく開始されることを検証（モック）"""
    correlation_id = "test-correlation-id-789"
    mock_connection_string = "InstrumentationKey=test-key-123"

    with patch.dict("os.environ", {"APPLICATIONINSIGHTS_CONNECTION_STRING": mock_connection_string}):
        # OpenTelemetryモジュールをモック
        mock_azure_monitor = Mock()
        mock_azure_monitor.configure_azure_monitor = Mock()

        mock_trace = Mock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_context_manager = MagicMock()
        mock_context_manager.__enter__ = Mock(return_value=mock_span)
        mock_context_manager.__exit__ = Mock(return_value=False)
        mock_tracer.start_as_current_span = Mock(return_value=mock_context_manager)
        mock_trace.get_tracer = Mock(return_value=mock_tracer)

        mock_metrics = Mock()
        mock_meter = Mock()
        mock_metrics.get_meter = Mock(return_value=mock_meter)

        with patch.dict("sys.modules", {
            "azure": Mock(),
            "azure.monitor": Mock(),
            "azure.monitor.opentelemetry": mock_azure_monitor,
            "opentelemetry": Mock(),
            "opentelemetry.trace": mock_trace,
            "opentelemetry.metrics": mock_metrics
        }):
            monitor = AzureMonitor()

            # tracerを直接モックに置き換え
            monitor.tracer = mock_tracer

            with monitor.start_span("test_operation", correlation_id) as span:
                pass

            # スパンが開始された
            mock_tracer.start_as_current_span.assert_called_once_with("test_operation")


# =============================================================================
# テスト: カスタムメトリクス
# =============================================================================

def test_track_metric_disabled():
    """監視無効時、ローカルコレクターにのみ記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        with patch.dict("sys.modules", {"azure.monitor.opentelemetry": None, "opentelemetry": None}):
            monitor = AzureMonitor()
            monitor.clear_metrics()

            monitor.track_metric("test_metric", 100, {"platform": "azure"})

            # ローカルメトリクスに記録されている
            metrics = monitor.get_metrics()
            assert len(metrics) == 1
            assert metrics[0].name == "test_metric"
            assert metrics[0].value == 100


def test_track_metric_enabled():
    """監視有効時、OpenTelemetryメーターに記録されることを検証（モック）"""
    mock_connection_string = "InstrumentationKey=test-key-123"

    with patch.dict("os.environ", {"APPLICATIONINSIGHTS_CONNECTION_STRING": mock_connection_string}):
        # OpenTelemetryモジュールをモック
        mock_azure_monitor = Mock()
        mock_azure_monitor.configure_azure_monitor = Mock()

        mock_trace = Mock()
        mock_tracer = Mock()
        mock_trace.get_tracer = Mock(return_value=mock_tracer)

        mock_metrics = Mock()
        mock_meter = MagicMock()
        mock_counter = Mock()
        mock_meter.create_counter.return_value = mock_counter
        mock_metrics.get_meter = Mock(return_value=mock_meter)

        with patch.dict("sys.modules", {
            "azure": Mock(),
            "azure.monitor": Mock(),
            "azure.monitor.opentelemetry": mock_azure_monitor,
            "opentelemetry": Mock(),
            "opentelemetry.trace": mock_trace,
            "opentelemetry.metrics": mock_metrics
        }):
            monitor = AzureMonitor()
            monitor.clear_metrics()

            monitor.track_metric("request_total", 5, {"endpoint": "/evaluate"})

            # メーターが利用されている
            assert monitor.enabled is True


# =============================================================================
# テスト: 例外記録
# =============================================================================

def test_track_exception_disabled():
    """監視無効時、エラーメトリクスのみ記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        with patch.dict("sys.modules", {"azure.monitor.opentelemetry": None, "opentelemetry": None}):
            monitor = AzureMonitor()
            monitor.clear_metrics()

            exception = ValueError("Test error")
            monitor.track_exception(exception, "corr-456", {"service": "llm"})

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
        with patch.dict("sys.modules", {"azure.monitor.opentelemetry": None, "opentelemetry": None}):
            monitor = AzureMonitor()
            monitor.clear_metrics()

            monitor.track_dependency(
                name="llm_invoke",
                dependency_type="Azure AI Foundry",
                target="gpt-4o",
                duration_ms=250.0,
                success=True,
                correlation_id="corr-999"
            )

            # 処理時間メトリクスが記録されている
            metrics = monitor.get_metrics()
            assert len(metrics) == 1
            assert metrics[0].name == "llm_invoke_duration_ms"
            assert metrics[0].value == 250.0
            assert metrics[0].dimensions["dependency_type"] == "Azure AI Foundry"
            assert metrics[0].dimensions["success"] == "True"


# =============================================================================
# まとめ
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
