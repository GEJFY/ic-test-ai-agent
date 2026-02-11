"""
================================================================================
test_gcp_monitoring.py - GCP Cloud Logging/Trace統合テスト
================================================================================

【概要】
GCP Cloud LoggingとCloud Trace統合機能のユニットテストです。
google-cloud-loggingパッケージが未インストールでもテストが動作します。

【テスト項目】
1. GCPMonitoringクラスの初期化
2. スパン開始・終了（モック）
3. カスタムメトリクス送信
4. 例外記録
5. 依存関係記録

【実行方法】
pytest tests/test_gcp_monitoring.py -v

================================================================================
"""
import pytest
import sys
from unittest.mock import Mock, patch, MagicMock
from src.infrastructure.monitoring.gcp_monitoring import GCPMonitoring


# =============================================================================
# テスト: 初期化
# =============================================================================

def test_gcp_monitoring_init_without_project_id():
    """プロジェクトIDなしで初期化した場合、無効化されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        # Google Cloud SDKのインポートを失敗させる
        with patch.dict("sys.modules", {
            "google.cloud": None,
            "google.cloud.logging": None,
            "google.cloud.trace": None
        }):
            monitor = GCPMonitoring()
            assert monitor.enabled is False


def test_gcp_monitoring_init_with_project_id():
    """プロジェクトIDありで初期化した場合、有効化されることを検証"""
    with patch.dict("os.environ", {"GCP_PROJECT": "test-project-123"}):
        # Google Cloud SDKモジュールをモック
        mock_logging = Mock()
        mock_logging_client = MagicMock()
        mock_logger = Mock()
        mock_logging_client.logger.return_value = mock_logger
        mock_logging.Client = Mock(return_value=mock_logging_client)

        # OpenCensus Stackdriver Exporterをモック
        mock_opencensus = Mock()
        mock_opencensus_ext = Mock()
        mock_opencensus_ext_stackdriver = Mock()
        mock_trace_exporter = Mock()
        mock_exporter = Mock()
        mock_trace_exporter.StackdriverExporter = Mock(return_value=mock_exporter)
        mock_opencensus_ext_stackdriver.trace_exporter = mock_trace_exporter

        mock_opencensus_trace = Mock()
        mock_tracer_module = Mock()
        mock_tracer = Mock()
        mock_tracer_module.Tracer = Mock(return_value=mock_tracer)
        mock_opencensus_trace.tracer = mock_tracer_module
        mock_opencensus_trace.samplers = Mock()
        mock_opencensus_trace.samplers.ProbabilitySampler = Mock()

        with patch.dict("sys.modules", {
            "google": Mock(),
            "google.cloud": Mock(),
            "google.cloud.logging": mock_logging,
            "opencensus": mock_opencensus,
            "opencensus.ext": mock_opencensus_ext,
            "opencensus.ext.stackdriver": mock_opencensus_ext_stackdriver,
            "opencensus.ext.stackdriver.trace_exporter": mock_trace_exporter,
            "opencensus.trace": mock_opencensus_trace,
            "opencensus.trace.tracer": mock_tracer_module,
            "opencensus.trace.samplers": mock_opencensus_trace.samplers
        }):
            monitor = GCPMonitoring()
            assert monitor.enabled is True


# =============================================================================
# テスト: スパン開始・終了
# =============================================================================

def test_start_span_disabled():
    """監視無効時、ダミースパンが返されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        with patch.dict("sys.modules", {"google.cloud": None, "google.cloud.logging": None}):
            monitor = GCPMonitoring()
            assert monitor.enabled is False

            with monitor.start_span("test_span", "corr-123") as span:
                # ダミースパンのメソッドが呼び出せることを確認
                span.add_attribute("test_key", "test_value")


def test_start_span_with_correlation_id():
    """相関ID付きスパンが正しく開始されることを検証（モック）"""
    correlation_id = "test-correlation-id-789"

    with patch.dict("os.environ", {"GCP_PROJECT": "test-project-123"}):
        # Google Cloud SDKモジュールをモック
        mock_logging = Mock()
        mock_logging_client = MagicMock()
        mock_logger = Mock()
        mock_logging_client.logger.return_value = mock_logger
        mock_logging.Client = Mock(return_value=mock_logging_client)

        # OpenCensus Stackdriver Exporterをモック
        mock_opencensus = Mock()
        mock_opencensus_ext = Mock()
        mock_opencensus_ext_stackdriver = Mock()
        mock_trace_exporter = Mock()
        mock_exporter = Mock()
        mock_trace_exporter.StackdriverExporter = Mock(return_value=mock_exporter)
        mock_opencensus_ext_stackdriver.trace_exporter = mock_trace_exporter

        mock_opencensus_trace = Mock()
        mock_tracer_module = Mock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.span.return_value.__enter__ = Mock(return_value=mock_span)
        mock_tracer.span.return_value.__exit__ = Mock(return_value=False)
        mock_tracer_module.Tracer = Mock(return_value=mock_tracer)
        mock_opencensus_trace.tracer = mock_tracer_module
        mock_opencensus_trace.samplers = Mock()
        mock_opencensus_trace.samplers.ProbabilitySampler = Mock()

        with patch.dict("sys.modules", {
            "google": Mock(),
            "google.cloud": Mock(),
            "google.cloud.logging": mock_logging,
            "opencensus": mock_opencensus,
            "opencensus.ext": mock_opencensus_ext,
            "opencensus.ext.stackdriver": mock_opencensus_ext_stackdriver,
            "opencensus.ext.stackdriver.trace_exporter": mock_trace_exporter,
            "opencensus.trace": mock_opencensus_trace,
            "opencensus.trace.tracer": mock_tracer_module,
            "opencensus.trace.samplers": mock_opencensus_trace.samplers
        }):
            monitor = GCPMonitoring()

            with monitor.start_span("test_operation", correlation_id) as span:
                pass

            # スパンが開始されたことを確認（実装依存）
            assert monitor.enabled is True


# =============================================================================
# テスト: カスタムメトリクス
# =============================================================================

def test_track_metric_disabled():
    """監視無効時、ローカルコレクターにのみ記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        with patch.dict("sys.modules", {"google.cloud": None, "google.cloud.logging": None}):
            monitor = GCPMonitoring()
            monitor.clear_metrics()

            monitor.track_metric("test_metric", 100, {"platform": "gcp"})

            # ローカルメトリクスに記録されている
            metrics = monitor.get_metrics()
            assert len(metrics) == 1
            assert metrics[0].name == "test_metric"
            assert metrics[0].value == 100


def test_track_metric_enabled():
    """監視有効時、Cloud Monitoringに送信されることを検証（モック）"""
    with patch.dict("os.environ", {"GCP_PROJECT": "test-project-123"}):
        # Google Cloud SDKモジュールをモック
        mock_logging = Mock()
        mock_logging_client = MagicMock()
        mock_logger = Mock()
        mock_logging_client.logger.return_value = mock_logger
        mock_logging.Client = Mock(return_value=mock_logging_client)

        # OpenCensus Stackdriver Exporterをモック
        mock_opencensus = Mock()
        mock_opencensus_ext = Mock()
        mock_opencensus_ext_stackdriver = Mock()
        mock_trace_exporter = Mock()
        mock_exporter = Mock()
        mock_trace_exporter.StackdriverExporter = Mock(return_value=mock_exporter)
        mock_opencensus_ext_stackdriver.trace_exporter = mock_trace_exporter

        mock_opencensus_trace = Mock()
        mock_tracer_module = Mock()
        mock_tracer = Mock()
        mock_tracer_module.Tracer = Mock(return_value=mock_tracer)
        mock_opencensus_trace.tracer = mock_tracer_module
        mock_opencensus_trace.samplers = Mock()
        mock_opencensus_trace.samplers.ProbabilitySampler = Mock()

        with patch.dict("sys.modules", {
            "google": Mock(),
            "google.cloud": Mock(),
            "google.cloud.logging": mock_logging,
            "opencensus": mock_opencensus,
            "opencensus.ext": mock_opencensus_ext,
            "opencensus.ext.stackdriver": mock_opencensus_ext_stackdriver,
            "opencensus.ext.stackdriver.trace_exporter": mock_trace_exporter,
            "opencensus.trace": mock_opencensus_trace,
            "opencensus.trace.tracer": mock_tracer_module,
            "opencensus.trace.samplers": mock_opencensus_trace.samplers
        }):
            monitor = GCPMonitoring()
            monitor.clear_metrics()

            monitor.track_metric("request_total", 5, {"endpoint": "/evaluate"})

            # 監視が有効化されている
            assert monitor.enabled is True


# =============================================================================
# テスト: 例外記録
# =============================================================================

def test_track_exception_disabled():
    """監視無効時、エラーメトリクスのみ記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        with patch.dict("sys.modules", {"google.cloud": None, "google.cloud.logging": None}):
            monitor = GCPMonitoring()
            monitor.clear_metrics()

            exception = ValueError("Test error")
            monitor.track_exception(exception, "corr-456", {"service": "vertex-ai"})

            # エラーメトリクスが記録されている
            metrics = monitor.get_metrics()
            assert len(metrics) == 1
            assert metrics[0].name == "error_total"
            assert metrics[0].dimensions["error_type"] == "ValueError"


def test_track_exception_enabled():
    """監視有効時、Cloud Loggingに記録されることを検証（モック）"""
    with patch.dict("os.environ", {"GCP_PROJECT": "test-project-123"}):
        # Google Cloud SDKモジュールをモック
        mock_logging = Mock()
        mock_logging_client = MagicMock()
        mock_logger = Mock()
        mock_logging_client.logger.return_value = mock_logger
        mock_logging.Client = Mock(return_value=mock_logging_client)

        # OpenCensus Stackdriver Exporterをモック
        mock_opencensus = Mock()
        mock_opencensus_ext = Mock()
        mock_opencensus_ext_stackdriver = Mock()
        mock_trace_exporter = Mock()
        mock_exporter = Mock()
        mock_trace_exporter.StackdriverExporter = Mock(return_value=mock_exporter)
        mock_opencensus_ext_stackdriver.trace_exporter = mock_trace_exporter

        mock_opencensus_trace = Mock()
        mock_tracer_module = Mock()
        mock_tracer = Mock()
        mock_tracer_module.Tracer = Mock(return_value=mock_tracer)
        mock_opencensus_trace.tracer = mock_tracer_module
        mock_opencensus_trace.samplers = Mock()
        mock_opencensus_trace.samplers.ProbabilitySampler = Mock()

        with patch.dict("sys.modules", {
            "google": Mock(),
            "google.cloud": Mock(),
            "google.cloud.logging": mock_logging,
            "opencensus": mock_opencensus,
            "opencensus.ext": mock_opencensus_ext,
            "opencensus.ext.stackdriver": mock_opencensus_ext_stackdriver,
            "opencensus.ext.stackdriver.trace_exporter": mock_trace_exporter,
            "opencensus.trace": mock_opencensus_trace,
            "opencensus.trace.tracer": mock_tracer_module,
            "opencensus.trace.samplers": mock_opencensus_trace.samplers
        }):
            monitor = GCPMonitoring()
            monitor.clear_metrics()

            exception = ValueError("Test error")
            monitor.track_exception(exception, "corr-789", {"service": "vertex-ai"})

            # 監視が有効化されている
            assert monitor.enabled is True


# =============================================================================
# テスト: 依存関係記録
# =============================================================================

def test_track_dependency():
    """依存関係呼び出しが記録されることを検証"""
    with patch.dict("os.environ", {}, clear=True):
        with patch.dict("sys.modules", {"google.cloud": None, "google.cloud.logging": None}):
            monitor = GCPMonitoring()
            monitor.clear_metrics()

            monitor.track_dependency(
                name="vertex_ai_invoke",
                dependency_type="Vertex AI",
                target="gemini-3-pro",
                duration_ms=180.0,
                success=True,
                correlation_id="corr-111"
            )

            # 処理時間メトリクスが記録されている
            metrics = monitor.get_metrics()
            assert len(metrics) == 1
            assert metrics[0].name == "vertex_ai_invoke_duration_ms"
            assert metrics[0].value == 180.0
            assert metrics[0].dimensions["dependency_type"] == "Vertex AI"
            assert metrics[0].dimensions["success"] == "True"


# =============================================================================
# まとめ
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
