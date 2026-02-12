"""
================================================================================
aws_xray.py - AWS X-Ray統合
================================================================================

【概要】
AWS X-Rayを使用した分散トレースとサービスマップ可視化です。

【機能】
1. X-Rayセグメント/サブセグメントによるトレース
2. カスタムメタデータ・アノテーション記録
3. 外部API呼び出しの自動追跡
4. エラー・例外の自動記録
5. 相関ID伝播

【使用例】
```python
from infrastructure.monitoring.aws_xray import AWSXRay

monitor = AWSXRay()

# トレース開始
with monitor.start_span("process_document", correlation_id) as segment:
    segment.put_annotation("correlation_id", correlation_id)
    segment.put_metadata("document_id", doc_id)

    # OCR処理
    with monitor.start_subsegment("bedrock_invocation") as subsegment:
        result = call_bedrock(prompt)
        subsegment.put_metadata("tokens", result["tokens"])
```

【依存関係】
- aws-xray-sdk>=2.12.0

================================================================================
"""
import os
import logging
from typing import Optional, Dict, Any
from contextlib import contextmanager

from .metrics import MetricsCollector

logger = logging.getLogger(__name__)


class AWSXRay(MetricsCollector):
    """
    AWS X-Ray統合クラス

    X-Ray SDKを使用して分散トレースとサービスマップを実装します。
    """

    def __init__(self):
        super().__init__()

        self.enabled = False
        self.xray_recorder = None

        # Lambda環境かどうか確認
        is_lambda = bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))

        try:
            # X-Ray SDKのインポート
            from aws_xray_sdk.core import xray_recorder
            from aws_xray_sdk.core import patch_all

            self.xray_recorder = xray_recorder

            if is_lambda:
                # Lambdaでは自動的にX-Rayが有効化される
                logger.info("AWS X-Ray: Lambda環境で自動有効化")
            else:
                # ローカル/開発環境ではデーモンモード
                logger.info("AWS X-Ray: デーモンモードで初期化")

            # 自動計装（AWS SDK、HTTPリクエストなど）
            patch_all()

            self.enabled = True
            logger.info("AWS X-Ray監視を初期化しました")

        except ImportError:
            logger.warning(
                "aws-xray-sdkがインストールされていません。"
                "pip install aws-xray-sdk"
            )
        except Exception as e:
            logger.error(f"X-Ray初期化エラー: {e}")

    @contextmanager
    def start_span(
        self,
        name: str,
        correlation_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        X-Rayサブセグメントを開始

        Args:
            name: セグメント名
            correlation_id: 相関ID
            attributes: 属性（メタデータ/アノテーション）

        Yields:
            サブセグメントオブジェクト
        """
        if not self.enabled or not self.xray_recorder:
            # フォールバック: ダミーセグメント
            class DummySegment:
                def put_annotation(self, key, value):
                    pass
                def put_metadata(self, key, value, namespace="default"):
                    pass

            yield DummySegment()
            return

        if attributes is None:
            attributes = {}

        # X-Rayサブセグメント開始
        subsegment = self.xray_recorder.begin_subsegment(name)

        try:
            # 相関IDをアノテーションとして追加（検索可能）
            if correlation_id:
                subsegment.put_annotation("correlation_id", correlation_id)

            # プラットフォームアノテーション
            subsegment.put_annotation("platform", "aws")

            # 属性をメタデータとして追加
            for key, value in attributes.items():
                subsegment.put_metadata(key, value)

            yield subsegment

        except Exception as e:
            # 例外記録
            subsegment.put_metadata("error", str(e))
            subsegment.put_annotation("error_occurred", True)
            raise

        finally:
            # サブセグメント終了
            self.xray_recorder.end_subsegment()

    @contextmanager
    def start_subsegment(
        self,
        name: str,
        correlation_id: Optional[str] = None,
        attributes: Optional[Dict[str, Any]] = None
    ):
        """
        サブセグメント開始のエイリアス（start_spanと同じ）

        Args:
            name: サブセグメント名
            correlation_id: 相関ID
            attributes: 属性

        Yields:
            サブセグメントオブジェクト
        """
        with self.start_span(name, correlation_id, attributes) as subsegment:
            yield subsegment

    def track_metric(
        self,
        name: str,
        value: float,
        dimensions: Optional[Dict[str, Any]] = None,
        unit: str = "count"
    ):
        """
        カスタムメトリクスを記録

        Note: X-Ray自体はメトリクスをサポートしないため、
        CloudWatch Metricsへの送信またはローカル記録のみ行います。

        Args:
            name: メトリクス名
            value: 値
            dimensions: ディメンション
            unit: 単位
        """
        # ローカルコレクターに記録
        self.record_metric(name, value, dimensions, unit)

        # 現在のセグメントにメタデータとして記録
        if self.enabled and self.xray_recorder:
            try:
                segment = self.xray_recorder.current_segment()
                if segment:
                    segment.put_metadata(f"metric_{name}", {
                        "value": value,
                        "unit": unit,
                        "dimensions": dimensions or {}
                    })
            except Exception:
                pass  # セグメント未開始の場合はスキップ

    def track_exception(
        self,
        exception: Exception,
        correlation_id: Optional[str] = None,
        properties: Optional[Dict[str, Any]] = None
    ):
        """
        例外をX-Rayに記録

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

        if not self.enabled or not self.xray_recorder:
            return

        try:
            # 現在のセグメントに例外を追加
            segment = self.xray_recorder.current_segment()
            if segment:
                segment.put_annotation("error_occurred", True)
                segment.put_metadata("exception", {
                    "type": type(exception).__name__,
                    "message": str(exception),
                    "properties": properties
                })

            logger.debug("Exception tracked to X-Ray")

        except Exception as e:
            logger.error(f"X-Ray例外記録エラー: {e}")

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
            dependency_type: タイプ（HTTP, DynamoDB, Bedrock, など）
            target: ターゲットURL/ARN
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

        if not self.enabled or not self.xray_recorder:
            return

        try:
            # 現在のセグメントにメタデータ追加
            segment = self.xray_recorder.current_segment()
            if segment:
                segment.put_metadata("dependency_call", {
                    "name": name,
                    "type": dependency_type,
                    "target": target,
                    "duration_ms": duration_ms,
                    "success": success
                })

        except Exception as e:
            logger.error(f"X-Ray依存関係記録エラー: {e}")

        logger.debug(
            f"Dependency tracked: {name} ({dependency_type}) -> {target} "
            f"in {duration_ms}ms (success={success})"
        )
