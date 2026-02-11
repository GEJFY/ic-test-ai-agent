"""
================================================================================
monitoring/__init__.py - 監視モジュール初期化
================================================================================

【概要】
Application Insights、X-Ray、Cloud Loggingの統合モジュールです。
カスタムメトリクス、トレース、ログの統一インターフェースを提供します。

【主要コンポーネント】
- metrics: プラットフォーム非依存のメトリクス収集
- azure_monitor: Application Insights統合
- aws_xray: X-Ray統合
- gcp_monitoring: Cloud Logging/Trace統合

【使用例】
```python
from infrastructure.monitoring import get_monitoring_provider, record_metric

# プラットフォーム自動検出
monitor = get_monitoring_provider()

# カスタムメトリクス記録
record_metric("document_processing_total", 1, {"platform": "azure"})

# トレース開始
with monitor.start_span("process_document") as span:
    span.set_attribute("correlation_id", correlation_id)
    result = process_document(data)
```

================================================================================
"""
import os
from typing import Optional, Dict, Any
from enum import Enum


class Platform(Enum):
    """クラウドプラットフォーム列挙型"""
    AZURE = "AZURE"
    AWS = "AWS"
    GCP = "GCP"
    UNKNOWN = "UNKNOWN"


def detect_platform() -> Platform:
    """
    環境変数からクラウドプラットフォームを自動検出

    Returns:
        Platform: 検出されたプラットフォーム
    """
    # Azure検出
    if os.getenv("AZURE_FUNCTIONS_ENVIRONMENT") or os.getenv("WEBSITE_INSTANCE_ID"):
        return Platform.AZURE

    # AWS検出
    if os.getenv("AWS_EXECUTION_ENV") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
        return Platform.AWS

    # GCP検出
    if os.getenv("FUNCTION_TARGET") or os.getenv("K_SERVICE"):
        return Platform.GCP

    # 環境変数LLM_PROVIDERで明示的に指定
    llm_provider = os.getenv("LLM_PROVIDER", "").upper()
    if llm_provider in ["AZURE", "AWS", "GCP"]:
        return Platform[llm_provider]

    return Platform.UNKNOWN


def get_monitoring_provider(platform: Optional[Platform] = None):
    """
    監視プロバイダーのインスタンスを取得

    Args:
        platform: プラットフォーム（Noneの場合は自動検出）

    Returns:
        監視プロバイダーインスタンス
    """
    if platform is None:
        platform = detect_platform()

    if platform == Platform.AZURE:
        from .azure_monitor import AzureMonitor
        return AzureMonitor()
    elif platform == Platform.AWS:
        from .aws_xray import AWSXRay
        return AWSXRay()
    elif platform == Platform.GCP:
        from .gcp_monitoring import GCPMonitoring
        return GCPMonitoring()
    else:
        # フォールバック: 基本的なロギングのみ
        from .metrics import MetricsCollector
        return MetricsCollector()


# 便利関数のエクスポート
from .metrics import (
    MetricsCollector,
    record_metric,
    record_duration,
    record_error,
    get_metrics_summary
)

__all__ = [
    "Platform",
    "detect_platform",
    "get_monitoring_provider",
    "MetricsCollector",
    "record_metric",
    "record_duration",
    "record_error",
    "get_metrics_summary"
]
