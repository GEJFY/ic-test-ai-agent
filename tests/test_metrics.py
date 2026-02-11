"""
================================================================================
test_metrics.py - メトリクスCollectorユニットテスト
================================================================================

【概要】
プラットフォーム非依存のメトリクス収集機能のテストです。

【テスト項目】
1. メトリクス記録
2. 処理時間記録
3. エラー記録
4. サマリー生成
5. コンテキストマネージャー（record_duration）

【実行方法】
pytest tests/test_metrics.py -v

================================================================================
"""
import pytest
import time
from src.infrastructure.monitoring.metrics import (
    MetricsCollector,
    record_metric,
    record_duration,
    record_error,
    get_metrics_summary
)


# =============================================================================
# テスト: メトリクス記録
# =============================================================================

def test_metrics_collector_singleton():
    """シングルトンパターンの検証"""
    collector1 = MetricsCollector()
    collector2 = MetricsCollector()
    assert collector1 is collector2


def test_record_metric():
    """メトリクス記録の検証"""
    collector = MetricsCollector()
    collector.clear_metrics()

    collector.record_metric("test_metric", 100, {"platform": "azure"}, "count")

    metrics = collector.get_metrics()
    assert len(metrics) == 1
    assert metrics[0].name == "test_metric"
    assert metrics[0].value == 100
    assert metrics[0].unit == "count"
    assert metrics[0].dimensions == {"platform": "azure"}


def test_record_metric_shortcut():
    """グローバル関数record_metricの検証"""
    collector = MetricsCollector()
    collector.clear_metrics()

    record_metric("request_total", 5, {"endpoint": "/api/evaluate"})

    metrics = collector.get_metrics()
    assert len(metrics) == 1
    assert metrics[0].name == "request_total"
    assert metrics[0].value == 5


# =============================================================================
# テスト: 処理時間記録
# =============================================================================

def test_record_duration_direct():
    """処理時間記録の検証"""
    collector = MetricsCollector()
    collector.clear_metrics()

    collector.record_duration("ocr_duration_ms", 250.5, {"method": "document_intelligence"})

    metrics = collector.get_metrics()
    assert len(metrics) == 1
    assert metrics[0].name == "ocr_duration_ms"
    assert metrics[0].value == 250.5
    assert metrics[0].unit == "ms"


def test_record_duration_context_manager():
    """処理時間コンテキストマネージャーの検証"""
    collector = MetricsCollector()
    collector.clear_metrics()

    with record_duration("test_operation", {"platform": "aws"}):
        time.sleep(0.1)  # 100ms スリープ

    metrics = collector.get_metrics()
    assert len(metrics) == 1
    assert metrics[0].name == "test_operation"
    assert metrics[0].value >= 100  # 最低100ms
    assert metrics[0].unit == "ms"
    assert metrics[0].dimensions["platform"] == "aws"


def test_record_duration_context_manager_exception():
    """例外発生時でも処理時間が記録されることを検証"""
    collector = MetricsCollector()
    collector.clear_metrics()

    try:
        with record_duration("failing_operation"):
            time.sleep(0.05)
            raise ValueError("Test exception")
    except ValueError:
        pass

    metrics = collector.get_metrics()
    assert len(metrics) == 1
    assert metrics[0].name == "failing_operation"
    assert metrics[0].value >= 50  # 最低50ms


# =============================================================================
# テスト: エラー記録
# =============================================================================

def test_record_error():
    """エラー記録の検証"""
    collector = MetricsCollector()
    collector.clear_metrics()

    collector.record_error("ValidationError", {"correlation_id": "test-123"})

    metrics = collector.get_metrics()
    assert len(metrics) == 1
    assert metrics[0].name == "error_total"
    assert metrics[0].value == 1
    assert metrics[0].dimensions["error_type"] == "ValidationError"
    assert metrics[0].dimensions["correlation_id"] == "test-123"


def test_record_error_shortcut():
    """グローバル関数record_errorの検証"""
    collector = MetricsCollector()
    collector.clear_metrics()

    record_error("TimeoutError", {"service": "llm_api"})

    metrics = collector.get_metrics()
    assert len(metrics) == 1
    assert metrics[0].dimensions["error_type"] == "TimeoutError"


# =============================================================================
# テスト: サマリー生成
# =============================================================================

def test_get_metrics_summary():
    """メトリクスサマリーの検証"""
    collector = MetricsCollector()
    collector.clear_metrics()

    # 複数のメトリクス記録
    collector.record_metric("llm_api_calls", 1)
    collector.record_metric("llm_api_calls", 1)
    collector.record_metric("llm_api_calls", 1)

    collector.record_duration("llm_duration_ms", 100)
    collector.record_duration("llm_duration_ms", 200)
    collector.record_duration("llm_duration_ms", 150)

    summary = collector.get_metrics_summary()

    # llm_api_callsのサマリー
    assert "llm_api_calls" in summary
    assert summary["llm_api_calls"]["count"] == 3
    assert summary["llm_api_calls"]["total"] == 3
    assert summary["llm_api_calls"]["avg"] == 1

    # llm_duration_msのサマリー
    assert "llm_duration_ms" in summary
    assert summary["llm_duration_ms"]["count"] == 3
    assert summary["llm_duration_ms"]["total"] == 450
    assert summary["llm_duration_ms"]["avg"] == 150
    assert summary["llm_duration_ms"]["min"] == 100
    assert summary["llm_duration_ms"]["max"] == 200


def test_get_metrics_summary_shortcut():
    """グローバル関数get_metrics_summaryの検証"""
    collector = MetricsCollector()
    collector.clear_metrics()

    record_metric("document_processing_total", 10)
    record_metric("document_processing_total", 5)

    summary = get_metrics_summary()

    assert "document_processing_total" in summary
    assert summary["document_processing_total"]["count"] == 2
    assert summary["document_processing_total"]["total"] == 15
    assert summary["document_processing_total"]["avg"] == 7.5


# =============================================================================
# テスト: メトリクスクリア
# =============================================================================

def test_clear_metrics():
    """メトリクスクリアの検証"""
    collector = MetricsCollector()

    collector.record_metric("test_metric", 1)
    assert len(collector.get_metrics()) >= 1

    collector.clear_metrics()
    assert len(collector.get_metrics()) == 0


# =============================================================================
# まとめ
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
