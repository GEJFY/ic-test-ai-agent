"""
================================================================================
aws_dynamodb.py - AWS DynamoDB ジョブストレージ実装
================================================================================

【概要】
AWS DynamoDBを使用したジョブストレージ実装です。
Lambda IAMロールによる認証に対応しています。

【必要な環境変数】
- AWS_REGION: AWSリージョン（例: ap-northeast-1）
- AWS_DYNAMODB_TABLE: テーブル名（デフォルト: EvaluationJobs）
- AWS_ACCESS_KEY_ID: アクセスキー（Lambda IAMロール使用時は不要）
- AWS_SECRET_ACCESS_KEY: シークレットキー（Lambda IAMロール使用時は不要）

【テーブル構造】
- パーティションキー: tenant_id (String)
- ソートキー: job_id (String)
- GSI: status-created_at-index (status + created_at)
- GSI: job_id-index (job_id) - job_idのみで検索用

【必要なパッケージ】
pip install boto3

================================================================================
"""

import os
import json
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from decimal import Decimal

from core.async_job_manager import (
    JobStorageBase,
    EvaluationJob,
    JobStatus,
    generate_job_id,
)

logger = logging.getLogger(__name__)

# AWS SDK
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning(
        "[AWSDynamoDB] boto3 not installed. "
        "Run: pip install boto3"
    )


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB Decimal型をJSONエンコード可能にする"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super().default(obj)


def decimal_to_int(obj):
    """再帰的にDecimalをintに変換"""
    if isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_int(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_int(v) for v in obj]
    return obj


class AWSDynamoDBJobStorage(JobStorageBase):
    """
    AWS DynamoDB ジョブストレージ

    DynamoDBを使用してジョブを永続化します。
    Lambda IAMロールによる認証に対応。
    """

    DEFAULT_TABLE_NAME = "EvaluationJobs"

    def __init__(
        self,
        region: str = None,
        table_name: str = None,
        profile_name: str = None
    ):
        """
        Args:
            region: AWSリージョン
            table_name: テーブル名（デフォルト: EvaluationJobs）
            profile_name: AWS CLIプロファイル名（ローカル開発用）
        """
        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required. "
                "Install it with: pip install boto3"
            )

        self._region = region or os.getenv("AWS_REGION", "ap-northeast-1")
        self._table_name = (
            table_name or
            os.getenv("AWS_DYNAMODB_TABLE", self.DEFAULT_TABLE_NAME)
        )
        self._profile_name = profile_name or os.getenv("AWS_PROFILE")

        # DynamoDBリソースを初期化
        session_kwargs = {"region_name": self._region}
        if self._profile_name:
            session_kwargs["profile_name"] = self._profile_name

        session = boto3.Session(**session_kwargs)
        self._dynamodb = session.resource("dynamodb")
        self._table = self._dynamodb.Table(self._table_name)

        # テーブル存在確認
        self._ensure_table_exists()

        logger.info(
            f"[AWSDynamoDB] Initialized with table: {self._table_name}, "
            f"region: {self._region}"
        )

    def _ensure_table_exists(self):
        """テーブルが存在することを確認（存在しない場合は作成）"""
        try:
            self._table.load()
            logger.debug(f"[AWSDynamoDB] Table exists: {self._table_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                logger.info(f"[AWSDynamoDB] Creating table: {self._table_name}")
                self._create_table()
            else:
                raise

    def _create_table(self):
        """テーブルを作成"""
        try:
            table = self._dynamodb.create_table(
                TableName=self._table_name,
                KeySchema=[
                    {"AttributeName": "tenant_id", "KeyType": "HASH"},  # Partition key
                    {"AttributeName": "job_id", "KeyType": "RANGE"}     # Sort key
                ],
                AttributeDefinitions=[
                    {"AttributeName": "tenant_id", "AttributeType": "S"},
                    {"AttributeName": "job_id", "AttributeType": "S"},
                    {"AttributeName": "status", "AttributeType": "S"},
                    {"AttributeName": "created_at", "AttributeType": "S"}
                ],
                GlobalSecondaryIndexes=[
                    {
                        "IndexName": "status-created_at-index",
                        "KeySchema": [
                            {"AttributeName": "status", "KeyType": "HASH"},
                            {"AttributeName": "created_at", "KeyType": "RANGE"}
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5
                        }
                    },
                    {
                        "IndexName": "job_id-index",
                        "KeySchema": [
                            {"AttributeName": "job_id", "KeyType": "HASH"}
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {
                            "ReadCapacityUnits": 5,
                            "WriteCapacityUnits": 5
                        }
                    }
                ],
                ProvisionedThroughput={
                    "ReadCapacityUnits": 5,
                    "WriteCapacityUnits": 5
                }
            )
            # テーブル作成完了を待機
            table.wait_until_exists()
            self._table = table
            logger.info(f"[AWSDynamoDB] Table created: {self._table_name}")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceInUseException":
                logger.debug(f"[AWSDynamoDB] Table already being created: {self._table_name}")
            else:
                raise

    def _job_to_item(self, job: EvaluationJob) -> Dict[str, Any]:
        """EvaluationJobをDynamoDB Itemに変換"""
        return {
            "tenant_id": job.tenant_id,
            "job_id": job.job_id,
            "status": job.status.value,
            "items": json.dumps(job.items, ensure_ascii=False, cls=DecimalEncoder),
            "results": json.dumps(job.results, ensure_ascii=False, cls=DecimalEncoder) if job.results else "",
            "progress": job.progress,
            "message": job.message or "",
            "created_at": job.created_at.isoformat() if job.created_at else "",
            "started_at": job.started_at.isoformat() if job.started_at else "",
            "completed_at": job.completed_at.isoformat() if job.completed_at else "",
            "error_message": job.error_message or "",
            "metadata": json.dumps(job.metadata, ensure_ascii=False, cls=DecimalEncoder) if job.metadata else "{}"
        }

    def _item_to_job(self, item: Dict[str, Any]) -> EvaluationJob:
        """DynamoDB ItemをEvaluationJobに変換"""
        # Decimal型を変換
        item = decimal_to_int(item)

        return EvaluationJob(
            job_id=item["job_id"],
            tenant_id=item["tenant_id"],
            status=JobStatus(item["status"]),
            items=json.loads(item["items"]) if item.get("items") else [],
            results=json.loads(item["results"]) if item.get("results") else None,
            progress=item.get("progress", 0),
            message=item.get("message", ""),
            created_at=datetime.fromisoformat(item["created_at"]) if item.get("created_at") else None,
            started_at=datetime.fromisoformat(item["started_at"]) if item.get("started_at") else None,
            completed_at=datetime.fromisoformat(item["completed_at"]) if item.get("completed_at") else None,
            error_message=item.get("error_message", ""),
            metadata=json.loads(item["metadata"]) if item.get("metadata") else {}
        )

    async def create_job(
        self,
        tenant_id: str,
        items: List[Dict[str, Any]]
    ) -> EvaluationJob:
        """新規ジョブを作成"""
        job_id = generate_job_id()

        job = EvaluationJob(
            job_id=job_id,
            tenant_id=tenant_id,
            status=JobStatus.PENDING,
            items=items,
            created_at=datetime.utcnow(),
            message="Job created, waiting for processing"
        )

        item = self._job_to_item(job)
        self._table.put_item(Item=item)

        logger.info(
            f"[AWSDynamoDB] Job created: {job_id}, "
            f"tenant: {tenant_id}, items: {len(items)}"
        )

        return job

    async def get_job(self, job_id: str) -> Optional[EvaluationJob]:
        """ジョブを取得（job_idのみで検索）"""
        try:
            # GSI (job_id-index) を使用して検索
            response = self._table.query(
                IndexName="job_id-index",
                KeyConditionExpression="job_id = :jid",
                ExpressionAttributeValues={":jid": job_id}
            )

            items = response.get("Items", [])
            if items:
                job = self._item_to_job(items[0])
                logger.debug(f"[AWSDynamoDB] Job retrieved: {job_id}")
                return job
            else:
                logger.debug(f"[AWSDynamoDB] Job not found: {job_id}")
                return None

        except Exception as e:
            logger.error(f"[AWSDynamoDB] Error getting job {job_id}: {e}")
            return None

    async def update_job(self, job: EvaluationJob) -> None:
        """ジョブを更新"""
        try:
            item = self._job_to_item(job)
            self._table.put_item(Item=item)

            logger.debug(
                f"[AWSDynamoDB] Job updated: {job.job_id}, "
                f"status: {job.status.value}, progress: {job.progress}%"
            )

        except Exception as e:
            logger.error(f"[AWSDynamoDB] Error updating job {job.job_id}: {e}")
            raise

    async def delete_job(self, job_id: str) -> bool:
        """ジョブを削除"""
        try:
            # まずジョブを取得してtenant_idを確認
            job = await self.get_job(job_id)
            if not job:
                return False

            self._table.delete_item(
                Key={
                    "tenant_id": job.tenant_id,
                    "job_id": job_id
                }
            )

            logger.info(f"[AWSDynamoDB] Job deleted: {job_id}")
            return True

        except Exception as e:
            logger.error(f"[AWSDynamoDB] Error deleting job {job_id}: {e}")
            return False

    async def get_pending_jobs(self, limit: int = 10) -> List[EvaluationJob]:
        """処理待ちジョブを取得"""
        try:
            # GSI (status-created_at-index) を使用して検索
            response = self._table.query(
                IndexName="status-created_at-index",
                KeyConditionExpression="#s = :s",
                ExpressionAttributeNames={"#s": "status"},
                ExpressionAttributeValues={":s": JobStatus.PENDING.value},
                Limit=limit,
                ScanIndexForward=True  # 作成日時昇順（古い順）
            )

            jobs = [self._item_to_job(item) for item in response.get("Items", [])]
            logger.debug(f"[AWSDynamoDB] Found {len(jobs)} pending jobs")
            return jobs

        except Exception as e:
            logger.error(f"[AWSDynamoDB] Error getting pending jobs: {e}")
            return []

    async def get_jobs_by_tenant(
        self,
        tenant_id: str,
        limit: int = 100,
        status: Optional[JobStatus] = None
    ) -> List[EvaluationJob]:
        """テナントのジョブ一覧を取得"""
        try:
            # テナントIDで検索（パーティションキー）
            key_condition = "tenant_id = :tid"
            expression_values = {":tid": tenant_id}

            # ステータスフィルター
            filter_expression = None
            expression_names = None
            if status:
                filter_expression = "#s = :s"
                expression_values[":s"] = status.value
                expression_names = {"#s": "status"}

            query_params = {
                "KeyConditionExpression": key_condition,
                "ExpressionAttributeValues": expression_values,
                "Limit": limit,
                "ScanIndexForward": False  # 作成日時降順（新しい順）
            }

            if filter_expression:
                query_params["FilterExpression"] = filter_expression
            if expression_names:
                query_params["ExpressionAttributeNames"] = expression_names

            response = self._table.query(**query_params)

            jobs = [self._item_to_job(item) for item in response.get("Items", [])]
            # 作成日時でソート（新しい順）
            jobs.sort(key=lambda j: j.created_at or datetime.min, reverse=True)

            logger.debug(
                f"[AWSDynamoDB] Found {len(jobs)} jobs for tenant: {tenant_id}"
            )
            return jobs[:limit]

        except Exception as e:
            logger.error(
                f"[AWSDynamoDB] Error getting jobs for tenant {tenant_id}: {e}"
            )
            return []
