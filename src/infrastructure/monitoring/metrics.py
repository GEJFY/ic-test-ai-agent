"""
================================================================================
metrics.py - プラットフォーム非依存のカスタムメトリクス収集
================================================================================

【概要】
すべてのクラウドプラットフォームで共通利用できるメトリクス収集基盤です。

【主要メトリクス】
1. document_processing_total - 処理済みドキュメント数
2. ocr_duration_ms - OCR処理時間
3. llm_api_calls_total - LLM API呼び出し回数
4. llm_duration_ms - LLM処理時間
5. error_rate - エラー率
6. request_duration_ms - リクエスト全体の処理時間

【使用例】
```python
from infrastructure.monitoring.metrics import record_metric, record_duration

# メトリクス記録
record_metric("document_processing_total", 1, {
    "platform": "azure",
    "correlation_id": correlation_id
})

# 処理時間記録
with record_duration("ocr_duration_ms", {"method": "document_intelligence"}):
    result = extract_text(image)
```

================================================================================
"""
import time
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import contextmanager
from threading import Lock


logger = logging.getLogger(__name__)


@dataclass
class MetricEntry:
    """メトリクスエントリ"""
    name: str
    value: float
    unit: str = "count"
    dimensions: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MetricsCollector:
    """
    プラットフォーム非依存のメトリクス収集クラス

    このクラスはメモリ内でメトリクスを保持し、各プラットフォームの
    監視サービスへの送信は派生クラスで実装します。
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        """シングルトンパターン"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self.metrics: List[MetricEntry] = []
        self._initialized = True
        logger.info("MetricsCollector initialized")

    def record_metric(
        self,
        name: str,
        value: float,
        dimensions: Optional[Dict[str, Any]] = None,
        unit: str = "count"
    ):
        """
        メトリクスを記録

        Args:
            name: メトリクス名
            value: 値
            dimensions: ディメンション（タグ）
            unit: 単位（count, ms, bytes, など）
        """
        if dimensions is None:
            dimensions = {}

        metric = MetricEntry(
            name=name,
            value=value,
            unit=unit,
            dimensions=dimensions
        )

        self.metrics.append(metric)

        logger.debug(
            f"Metric recorded: {name}={value}{unit}",
            extra={
                "metric_name": name,
                "metric_value": value,
                "metric_unit": unit,
                "dimensions": dimensions
            }
        )

    def record_duration(
        self,
        name: str,
        duration_ms: float,
        dimensions: Optional[Dict[str, Any]] = None
    ):
        """
        処理時間メトリクスを記録

        Args:
            name: メトリクス名
            duration_ms: 処理時間（ミリ秒）
            dimensions: ディメンション
        """
        self.record_metric(name, duration_ms, dimensions, unit="ms")

    def record_error(
        self,
        error_type: str,
        dimensions: Optional[Dict[str, Any]] = None
    ):
        """
        エラーメトリクスを記録

        Args:
            error_type: エラータイプ
            dimensions: ディメンション
        """
        if dimensions is None:
            dimensions = {}

        dimensions["error_type"] = error_type
        self.record_metric("error_total", 1, dimensions)

    def get_metrics(self) -> List[MetricEntry]:
        """
        収集済みメトリクスを取得

        Returns:
            メトリクスエントリのリスト
        """
        return self.metrics.copy()

    def clear_metrics(self):
        """メトリクスをクリア"""
        self.metrics.clear()
        logger.debug("Metrics cleared")

    def get_metrics_summary(self) -> Dict[str, Any]:
        """
        メトリクスのサマリーを取得

        Returns:
            サマリー辞書
        """
        summary = {}

        for metric in self.metrics:
            if metric.name not in summary:
                summary[metric.name] = {
                    "count": 0,
                    "total": 0,
                    "min": float('inf'),
                    "max": float('-inf'),
                    "unit": metric.unit
                }

            stats = summary[metric.name]
            stats["count"] += 1
            stats["total"] += metric.value
            stats["min"] = min(stats["min"], metric.value)
            stats["max"] = max(stats["max"], metric.value)

        # 平均値を計算
        for name, stats in summary.items():
            if stats["count"] > 0:
                stats["avg"] = stats["total"] / stats["count"]

        return summary


# グローバルコレクターインスタンス
_global_collector = MetricsCollector()


def record_metric(
    name: str,
    value: float,
    dimensions: Optional[Dict[str, Any]] = None,
    unit: str = "count"
):
    """
    メトリクス記録のショートカット関数

    Args:
        name: メトリクス名
        value: 値
        dimensions: ディメンション
        unit: 単位
    """
    _global_collector.record_metric(name, value, dimensions, unit)


def record_error(error_type: str, dimensions: Optional[Dict[str, Any]] = None):
    """
    エラー記録のショートカット関数

    Args:
        error_type: エラータイプ
        dimensions: ディメンション
    """
    _global_collector.record_error(error_type, dimensions)


@contextmanager
def record_duration(name: str, dimensions: Optional[Dict[str, Any]] = None):
    """
    処理時間を自動記録するコンテキストマネージャー

    Args:
        name: メトリクス名
        dimensions: ディメンション

    Usage:
        with record_duration("ocr_processing", {"platform": "azure"}):
            result = extract_text(image)
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration_ms = (time.time() - start_time) * 1000
        _global_collector.record_duration(name, duration_ms, dimensions)


def get_metrics_summary() -> Dict[str, Any]:
    """
    メトリクスサマリー取得のショートカット関数

    Returns:
        サマリー辞書
    """
    return _global_collector.get_metrics_summary()
