"""
================================================================================
gcp_monitoring.py - GCP Cloud Logging/Trace統合
================================================================================

【概要】
GCP Cloud LoggingとCloud Traceを使用した統合監視です。

【機能】
1. Cloud Traceによる分散トレース
2. 構造化ログのCloud Logging送信
3. カスタムメトリクスのCloud Monitoring送信
4. エラーReporting統合
5. 相関ID伝播

【使用例】
```python
from infrastructure.monitoring.gcp_monitoring import GCPMonitoring

monitor = GCPMonitoring()

# トレース開始
with monitor.start_span("process_document", correlation_id) as span:
    span.add_attribute("document_id", doc_id)

    # Vertex AI呼び出し
    with monitor.start_span("vertex_ai_invocation") as ai_span:
        result = call_vertex_ai(prompt)
        ai_span.add_attribute("tokens", result["tokens"])
```

【依存関係】
- google-cloud-logging>=3.8.0
- google-cloud-trace>=1.11.0
- opencensus-ext-stackdriver>=0.11.0

================================================================================
"""
import os
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

from .metrics import MetricsCollector

logger = logging.getLogger(__name__)


class GCPMonitoring(MetricsCollector):
    """
    GCP Cloud Logging/Trace統合クラス

    OpenCensusとCloud Logging/Traceを使用して統合監視を実装します。
    """

    def __init__(self):
        super().__init__()

        self.enabled = False
        self.tracer = None
        self.logging_client = None
        self.cloud_logger = None

        # GCP Project ID取得
        project_id = os.getenv("GCP_PROJECT") or os.getenv("GOOGLE_CLOUD_PROJECT")

        if not project_id:
            logger.warning(
                "GCP_PROJECT環境変数が設定されていません。"
                "監視機能は無効化されます。"
            )
            return

        try:
            # Cloud Logging初期化
            self._initialize_logging(project_id)

            # Cloud Trace初期化
            self._initialize_tracing(project_id)

            self.enabled = True
            logger.info("GCP Cloud Logging/Trace監視を初期化しました")

        except ImportError:
            logger.warning(
                "GCP監視パッケージがインストールされていません。"
                "pip install google-cloud-logging google-cloud-trace opencensus-ext-stackdriver"
            )
        except Exception as e:
            logger.error(f"GCP監視初期化エラー: {e}")

    def _initialize_logging(self, project_id: str):
        """Cloud Logging初期化"""
        from google.cloud import logging as cloud_logging

        # Cloud Loggingクライアント
        self.logging_client = cloud_logging.Client(project=project_id)

        # 構造化ログ用ロガー
        self.cloud_logger = self.logging_client.logger("ic-test-ai")

        logger.info(f"Cloud Logging initialized for project: {project_id}")

    def _initialize_tracing(self, project_id: str):
        """Cloud Trace初期化"""
        from opencensus.ext.stackdriver import trace_exporter as stackdriver_exporter
        from opencensus.trace.tracer import Tracer
        from opencensus.trace.samplers import ProbabilitySampler

        # Stackdriver Trace Exporter
        exporter = stackdriver_exporter.StackdriverExporter(
            project_id=project_id
        )

        # Tracer（10%サンプリングでコスト最適化）
        self.tracer = Tracer(
            exporter=exporter,
            sampler=ProbabilitySampler(0.1)
        )

        logger.info(f"Cloud Trace initialized for project: {project_id}")

    @contextmanager
    def start_span(
        self,
        name: str,
        correlation_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        Cloud Traceスパンを開始

        Args:
            name: スパン名
            correlation_id: 相関ID
            attributes: スパン属性

        Yields:
            スパンオブジェクト
        """
        if not self.enabled or not self.tracer:
            # フォールバック: ダミースパン
            class DummySpan:
                def add_attribute(self, key, value):
                    pass

            yield DummySpan()
            return

        if attributes is None:
            attributes = {}

        # 相関ID属性追加
        if correlation_id:
            attributes["correlation_id"] = correlation_id

        # プラットフォーム属性追加
        attributes["platform"] = "gcp"

        with self.tracer.span(name=name) as span:
            # 属性設定
            for key, value in attributes.items():
                span.add_attribute(key, str(value))

            try:
                yield span
            except Exception as e:
                # 例外を属性として記録
                span.add_attribute("error", True)
                span.add_attribute("error_message", str(e))
                span.add_attribute("error_type", type(e).__name__)
                raise

    def track_metric(
        self,
        name: str,
        value: float,
        dimensions: Optional[Dict[str, Any]] = None,
        unit: str = "count"
    ):
        """
        カスタムメトリクスをCloud Monitoringに送信

        Args:
            name: メトリクス名
            value: 値
            dimensions: ディメンション（ラベル）
            unit: 単位
        """
        # ローカルコレクターにも記録
        self.record_metric(name, value, dimensions, unit)

        if not self.enabled or not self.cloud_logger:
            return

        try:
            # 構造化ログとして記録（Log-based Metricsで活用）
            log_entry = {
                "metric_name": name,
                "metric_value": value,
                "metric_unit": unit,
                "labels": dimensions or {}
            }

            self.cloud_logger.log_struct(
                log_entry,
                severity="INFO"
            )

            logger.debug(f"Metric logged to Cloud Logging: {name}={value}")

        except Exception as e:
            logger.error(f"Cloud Loggingメトリクス送信エラー: {e}")

    def track_exception(
        self,
        exception: Exception,
        correlation_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ):
        """
        例外をCloud Error Reportingに送信

        Args:
            exception: 例外オブジェクト
            correlation_id: 相関ID
            properties: 追加プロパティ
        """
        if properties is None:
            properties = {}

        if correlation_id:
            properties["correlation_id"] = correlation_id

        # エラーメトリクス記録
        self.record_error(type(exception).__name__, properties)

        if not self.enabled or not self.cloud_logger:
            return

        try:
            # Cloud Logging経由でError Reportingに送信
            error_entry = {
                "message": str(exception),
                "exception_type": type(exception).__name__,
                "properties": properties
            }

            self.cloud_logger.log_struct(
                error_entry,
                severity="ERROR"
            )

            logger.debug("Exception logged to Cloud Error Reporting")

        except Exception as e:
            logger.error(f"Cloud Error Reporting送信エラー: {e}")

    def track_dependency(
        self,
        name: str,
        dependency_type: str,
        target: str,
        duration_ms: float,
        success: bool = True,
        correlation_id: Optional[str] = None
    ):
        """
        外部依存関係呼び出しを記録

        Args:
            name: 依存関係名
            dependency_type: タイプ（HTTP, Vertex AI, Document AI, など）
            target: ターゲットURL/エンドポイント
            duration_ms: 処理時間（ミリ秒）
            success: 成功フラグ
            correlation_id: 相関ID
        """
        dimensions = {
            "dependency_type": dependency_type,
            "target": target,
            "success": str(success)
        }

        if correlation_id:
            dimensions["correlation_id"] = correlation_id

        # 処理時間メトリクス記録
        self.record_duration(f"{name}_duration_ms", duration_ms, dimensions)

        if not self.enabled or not self.cloud_logger:
            return

        try:
            # 依存関係呼び出しを構造化ログとして記録
            dependency_entry = {
                "event": "dependency_call",
                "dependency_name": name,
                "dependency_type": dependency_type,
                "target": target,
                "duration_ms": duration_ms,
                "success": success,
                "correlation_id": correlation_id
            }

            self.cloud_logger.log_struct(
                dependency_entry,
                severity="INFO"
            )

        except Exception as e:
            logger.error(f"Cloud Logging依存関係記録エラー: {e}")

        logger.debug(
            f"Dependency tracked: {name} ({dependency_type}) -> {target} "
            f"in {duration_ms}ms (success={success})"
        )
