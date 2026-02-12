"""
================================================================================
aws_sqs.py - AWS SQS ジョブキュー実装
================================================================================

【概要】
AWS SQSを使用したジョブキュー実装です。
Lambda SQSトリガーと連携して非同期処理を実現します。

【必要な環境変数】
- AWS_REGION: AWSリージョン（例: ap-northeast-1）
- AWS_SQS_QUEUE_URL: SQSキューURL（省略時は自動作成/検出）
- AWS_SQS_QUEUE_NAME: キュー名（デフォルト: evaluation-jobs）
- AWS_ACCESS_KEY_ID: アクセスキー（Lambda IAMロール使用時は不要）
- AWS_SECRET_ACCESS_KEY: シークレットキー（Lambda IAMロール使用時は不要）

【キュー設定】
- メッセージ保持期間: 14日
- 可視性タイムアウト: 300秒（5分）
- 受信待機時間: 20秒（ロングポーリング）

【必要なパッケージ】
pip install boto3

================================================================================
"""

import os
import json
import logging
from typing import Optional

from core.async_job_manager import JobQueueBase

logger = logging.getLogger(__name__)

# AWS SDK
try:
    import boto3
    from botocore.exceptions import ClientError
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning(
        "[AWSSQS] boto3 not installed. "
        "Run: pip install boto3"
    )


class AWSSQSJobQueue(JobQueueBase):
    """
    AWS SQS ジョブキュー

    Amazon SQSを使用してジョブ通知を管理します。
    Lambda SQSトリガーと連携します。
    """

    DEFAULT_QUEUE_NAME = "evaluation-jobs"

    def __init__(
        self,
        region: str = None,
        queue_url: str = None,
        queue_name: str = None,
        profile_name: str = None
    ):
        """
        Args:
            region: AWSリージョン
            queue_url: SQSキューURL（省略時は自動検出/作成）
            queue_name: キュー名（デフォルト: evaluation-jobs）
            profile_name: AWS CLIプロファイル名（ローカル開発用）
        """
        if not BOTO3_AVAILABLE:
            raise ImportError(
                "boto3 is required. "
                "Install it with: pip install boto3"
            )

        self._region = region or os.getenv("AWS_REGION", "ap-northeast-1")
        self._queue_url = queue_url or os.getenv("AWS_SQS_QUEUE_URL")
        self._queue_name = (
            queue_name or
            os.getenv("AWS_SQS_QUEUE_NAME") or
            os.getenv("JOB_QUEUE_NAME", self.DEFAULT_QUEUE_NAME)
        )
        self._profile_name = profile_name or os.getenv("AWS_PROFILE")

        # SQSクライアントを初期化
        session_kwargs = {"region_name": self._region}
        if self._profile_name:
            session_kwargs["profile_name"] = self._profile_name

        session = boto3.Session(**session_kwargs)
        self._sqs = session.client("sqs")

        # キューURLを取得または作成
        if not self._queue_url:
            self._queue_url = self._get_or_create_queue()

        logger.info(
            f"[AWSSQS] Initialized with queue: {self._queue_name}, "
            f"region: {self._region}"
        )

    def _get_or_create_queue(self) -> str:
        """キューURLを取得または作成"""
        try:
            # 既存のキューを取得
            response = self._sqs.get_queue_url(QueueName=self._queue_name)
            queue_url = response["QueueUrl"]
            logger.debug(f"[AWSSQS] Found existing queue: {queue_url}")
            return queue_url

        except ClientError as e:
            if e.response["Error"]["Code"] == "AWS.SimpleQueueService.NonExistentQueue":
                # キューが存在しない場合は作成
                logger.info(f"[AWSSQS] Creating queue: {self._queue_name}")
                return self._create_queue()
            else:
                raise

    def _create_queue(self) -> str:
        """キューを作成"""
        try:
            response = self._sqs.create_queue(
                QueueName=self._queue_name,
                Attributes={
                    "MessageRetentionPeriod": "1209600",  # 14日
                    "VisibilityTimeout": "300",           # 5分
                    "ReceiveMessageWaitTimeSeconds": "20" # ロングポーリング
                }
            )
            queue_url = response["QueueUrl"]
            logger.info(f"[AWSSQS] Queue created: {queue_url}")
            return queue_url

        except ClientError as e:
            logger.error(f"[AWSSQS] Error creating queue: {e}")
            raise

    async def enqueue(self, job_id: str) -> None:
        """
        ジョブをキューに追加

        Args:
            job_id: キューに追加するジョブID
        """
        try:
            # メッセージ内容（JSON形式）
            message = json.dumps({
                "job_id": job_id,
                "action": "process"
            })

            # キューにメッセージを送信
            response = self._sqs.send_message(
                QueueUrl=self._queue_url,
                MessageBody=message,
                # MessageGroupId は FIFO キューでのみ必要
                # DelaySeconds=0  # 即座に処理可能
            )

            message_id = response.get("MessageId", "unknown")
            logger.info(f"[AWSSQS] Job enqueued: {job_id}, MessageId: {message_id}")

        except Exception as e:
            logger.error(f"[AWSSQS] Error enqueuing job {job_id}: {e}")
            raise

    async def dequeue(self) -> Optional[str]:
        """
        キューからジョブIDを取得

        Returns:
            ジョブID（キューが空の場合はNone）

        Note:
            Lambda SQSトリガーを使用する場合、
            この関数は直接呼び出されません。
            SQSトリガーが自動的にメッセージを取得します。
        """
        try:
            response = self._sqs.receive_message(
                QueueUrl=self._queue_url,
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,  # ロングポーリング
                VisibilityTimeout=300  # 5分間他のワーカーから見えなくする
            )

            messages = response.get("Messages", [])

            if messages:
                message = messages[0]
                receipt_handle = message["ReceiptHandle"]

                # メッセージ本文をパース
                body = json.loads(message["Body"])
                job_id = body.get("job_id")

                # メッセージを削除（処理完了）
                self._sqs.delete_message(
                    QueueUrl=self._queue_url,
                    ReceiptHandle=receipt_handle
                )

                logger.info(f"[AWSSQS] Job dequeued: {job_id}")
                return job_id

            return None

        except Exception as e:
            logger.error(f"[AWSSQS] Error dequeuing: {e}")
            return None

    async def get_queue_length(self) -> int:
        """
        キュー内のメッセージ数を取得

        Returns:
            メッセージ数
        """
        try:
            response = self._sqs.get_queue_attributes(
                QueueUrl=self._queue_url,
                AttributeNames=["ApproximateNumberOfMessages"]
            )

            count = int(response["Attributes"].get("ApproximateNumberOfMessages", 0))
            logger.debug(f"[AWSSQS] Queue length: {count}")
            return count

        except Exception as e:
            logger.error(f"[AWSSQS] Error getting queue length: {e}")
            return 0

    async def purge(self) -> None:
        """キューをパージ（全メッセージ削除）"""
        try:
            self._sqs.purge_queue(QueueUrl=self._queue_url)
            logger.info(f"[AWSSQS] Queue purged: {self._queue_name}")

        except ClientError as e:
            if e.response["Error"]["Code"] == "AWS.SimpleQueueService.PurgeQueueInProgress":
                logger.warning("[AWSSQS] Purge already in progress")
            else:
                logger.error(f"[AWSSQS] Error purging queue: {e}")
                raise


def parse_sqs_event(event: dict) -> Optional[str]:
    """
    Lambda SQSトリガーイベントからジョブIDを取得

    Lambda関数がSQSトリガーで呼び出された際に使用します。

    Args:
        event: Lambda SQSイベント

    Returns:
        ジョブID

    Usage:
        def lambda_handler(event, context):
            for record in event.get('Records', []):
                job_id = parse_sqs_record(record)
                if job_id:
                    process_job(job_id)
    """
    try:
        records = event.get("Records", [])
        if records:
            body = records[0].get("body", "{}")
            data = json.loads(body)
            return data.get("job_id")
        return None

    except Exception as e:
        logger.error(f"[AWSSQS] Error parsing SQS event: {e}")
        return None


def parse_sqs_record(record: dict) -> Optional[str]:
    """
    単一のSQSレコードからジョブIDを取得

    Args:
        record: SQSレコード

    Returns:
        ジョブID
    """
    try:
        body = record.get("body", "{}")
        data = json.loads(body)
        return data.get("job_id")

    except json.JSONDecodeError:
        # JSON形式でない場合、メッセージ自体がジョブIDと仮定
        return record.get("body")
    except Exception as e:
        logger.error(f"[AWSSQS] Error parsing SQS record: {e}")
        return None
