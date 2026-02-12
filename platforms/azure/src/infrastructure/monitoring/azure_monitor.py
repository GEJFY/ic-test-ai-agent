"""
================================================================================
azure_monitor.py - Azure Application Insights統合
================================================================================

【概要】
Application InsightsとOpenTelemetryを使用した詳細トレースとカスタムメトリクスです。

【機能】
1. OpenTelemetryによる分散トレース
2. カスタムメトリクスの送信
3. 依存関係の自動追跡
4. 例外の自動記録
5. 相関ID伝播

【使用例】
```python
from infrastructure.monitoring.azure_monitor import AzureMonitor

monitor = AzureMonitor()

# トレース開始
with monitor.start_span("process_document", correlation_id) as span:
    span.set_attribute("document_id", doc_id)

    # OCR処理
    with monitor.start_span("ocr_extraction") as ocr_span:
        result = extract_text(image)
        ocr_span.set_attribute("page_count", result["pages"])

    # LLM処理
    with monitor.start_span("llm_analysis") as llm_span:
        analysis = call_llm(result)
        llm_span.set_attribute("tokens", analysis["tokens"])

# カスタムメトリクス送信
monitor.track_metric("document_processing_total", 1, {
    "platform": "azure",
    "correlation_id": correlation_id
})
```

【依存関係】
- azure-monitor-opentelemetry>=1.0.0
- opentelemetry-api>=1.20.0
- opentelemetry-sdk>=1.20.0

================================================================================
"""
import os
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

from .metrics import MetricsCollector

logger = logging.getLogger(__name__)


class AzureMonitor(MetricsCollector):
    """
    Application Insights統合クラス

    OpenTelemetryを使用して分散トレースとカスタムメトリクスを実装します。
    """

    def __init__(self):
        super().__init__()

        self.enabled = False
        self.tracer = None
        self.meter = None

        # Application Insights接続文字列の確認
        connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")

        if not connection_string:
            logger.warning(
                "Application Insights接続文字列が設定されていません。"
                "監視機能は無効化されます。"
            )
            return

        try:
            # OpenTelemetryの初期化
            self._initialize_opentelemetry(connection_string)
            self.enabled = True
            logger.info("Azure Application Insights監視を初期化しました")

        except ImportError:
            logger.warning(
                "OpenTelemetryパッケージがインストールされていません。"
                "pip install azure-monitor-opentelemetry opentelemetry-api opentelemetry-sdk"
            )
        except Exception as e:
            logger.error(f"Application Insights初期化エラー: {e}")

    def _initialize_opentelemetry(self, connection_string: str):
        """OpenTelemetry初期化"""
        from azure.monitor.opentelemetry import configure_azure_monitor
        from opentelemetry import trace, metrics

        # Application Insights自動計装設定
        configure_azure_monitor(
            connection_string=connection_string,
            enable_live_metrics=True,
            # サンプリング設定（コスト最適化）
            sampler=trace.sampling.ParentBasedTraceIdRatioBased(0.1)  # 10%サンプリング
        )

        # Tracer取得
        self.tracer = trace.get_tracer(__name__)

        # Meter取得（カスタムメトリクス用）
        self.meter = metrics.get_meter(__name__)

        logger.info("OpenTelemetry configured for Application Insights")

    @contextmanager
    def start_span(
        self,
        name: str,
        correlation_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        トレーススパンを開始

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
                def set_attribute(self, key, value):
                    pass
                def set_status(self, status):
                    pass
                def record_exception(self, exception):
                    pass

            yield DummySpan()
            return

        if attributes is None:
            attributes = {}

        # 相関ID属性追加
        if correlation_id:
            attributes["correlation_id"] = correlation_id

        # プラットフォーム属性追加
        attributes["platform"] = "azure"

        with self.tracer.start_as_current_span(name) as span:
            # 属性設定
            for key, value in attributes.items():
                span.set_attribute(key, str(value))

            try:
                yield span
            except Exception as e:
                # 例外を自動記録
                span.record_exception(e)
                from opentelemetry.trace import Status, StatusCode
                span.set_status(Status(StatusCode.ERROR, str(e)))
                raise

    def track_metric(
        self,
        name: str,
        value: float,
        dimensions: Optional[Dict[str, Any]] = None,
        unit: str = "count"
    ):
        """
        カスタムメトリクスをApplication Insightsに送信

        Args:
            name: メトリクス名
            value: 値
            dimensions: ディメンション
            unit: 単位
        """
        # ローカルコレクターにも記録
        self.record_metric(name, value, dimensions, unit)

        if not self.enabled or not self.meter:
            return

        try:
            # OpenTelemetry Meterでメトリクス記録
            counter = self.meter.create_counter(
                name=name,
                description=f"Custom metric: {name}",
                unit=unit
            )

            # ディメンションを属性として追加
            attributes = dimensions or {}
            counter.add(value, attributes)

            logger.debug(f"Metric tracked to Application Insights: {name}={value}")

        except Exception as e:
            logger.error(f"Application Insightsメトリクス送信エラー: {e}")

    def track_exception(
        self,
        exception: Exception,
        correlation_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ):
        """
        例外をApplication Insightsに送信

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

        if not self.enabled:
            return

        try:
            from opentelemetry import trace

            # 現在のスパンに例外を記録
            span = trace.get_current_span()
            if span:
                span.record_exception(exception)
                span.set_status(trace.Status(trace.StatusCode.ERROR))

            logger.debug("Exception tracked to Application Insights")

        except Exception as e:
            logger.error(f"Application Insights例外送信エラー: {e}")

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
        依存関係呼び出しを記録

        Args:
            name: 依存関係名
            dependency_type: タイプ（HTTP, SQL, Azure AI, など）
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

        if not self.enabled:
            return

        logger.debug(
            f"Dependency tracked: {name} ({dependency_type}) -> {target} "
            f"in {duration_ms}ms (success={success})"
        )
