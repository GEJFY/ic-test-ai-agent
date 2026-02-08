"""
================================================================================
gcp_tasks.py - GCP Cloud Tasks ジョブキュー実装
================================================================================

【概要】
GCP Cloud Tasksを使用したジョブキュー実装です。
Cloud Functions/Cloud Runと連携して非同期処理を実現します。

【必要な環境変数】
- GCP_PROJECT_ID: GCPプロジェクトID
- GCP_TASKS_LOCATION: ロケーション（例: asia-northeast1）
- GCP_TASKS_QUEUE: キュー名（デフォルト: evaluation-jobs）
- GCP_TASKS_TARGET_URL: タスク処理用のHTTPエンドポイントURL
- GOOGLE_APPLICATION_CREDENTIALS: サービスアカウントキーのパス
  （Cloud Functions/Cloud Run上では自動認証）

【キュー名】
デフォルト: evaluation-jobs
環境変数 GCP_TASKS_QUEUE で変更可能

【必要なパッケージ】
pip install google-cloud-tasks

================================================================================
"""

import os
import json
import logging
from typing import Optional

from core.async_job_manager import JobQueueBase

logger = logging.getLogger(__name__)

# Cloud Tasks SDK
try:
    from google.cloud import tasks_v2
    CLOUD_TASKS_AVAILABLE = True
except ImportError:
    CLOUD_TASKS_AVAILABLE = False
    logger.warning(
        "[GCPCloudTasks] google-cloud-tasks not installed. "
        "Run: pip install google-cloud-tasks"
    )


class GCPCloudTasksJobQueue(JobQueueBase):
    """
    GCP Cloud Tasks ジョブキュー

    Cloud Tasksを使用してジョブ通知を管理します。
    Cloud Functions/Cloud Runのトリガーと連携します。
    """

    DEFAULT_QUEUE_NAME = "evaluation-jobs"
    DEFAULT_LOCATION = "asia-northeast1"

    def __init__(
        self,
        project_id: str = None,
        location: str = None,
        queue_name: str = None,
        target_url: str = None,
        credentials_path: str = None
    ):
        """
        Args:
            project_id: GCPプロジェクトID
            location: ロケーション（例: asia-northeast1）
            queue_name: キュー名（デフォルト: evaluation-jobs）
            target_url: タスク処理用のHTTPエンドポイントURL
            credentials_path: サービスアカウントキーのパス
        """
        if not CLOUD_TASKS_AVAILABLE:
            raise ImportError(
                "google-cloud-tasks is required. "
                "Install it with: pip install google-cloud-tasks"
            )

        # プロジェクトID取得
        self._project_id = (
            project_id or
            os.getenv("GCP_PROJECT_ID") or
            os.getenv("GOOGLE_CLOUD_PROJECT")
        )

        if not self._project_id:
            raise ValueError(
                "GCP project ID is required. "
                "Set GCP_PROJECT_ID environment variable."
            )

        # ロケーション
        self._location = (
            location or
            os.getenv("GCP_TASKS_LOCATION") or
            self.DEFAULT_LOCATION
        )

        # キュー名
        self._queue_name = (
            queue_name or
            os.getenv("GCP_TASKS_QUEUE") or
            self.DEFAULT_QUEUE_NAME
        )

        # ターゲットURL（HTTPタスク用）
        self._target_url = (
            target_url or
            os.getenv("GCP_TASKS_TARGET_URL")
        )

        # 認証情報パス（オプション）
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

        # Cloud Tasksクライアント初期化
        self._client = tasks_v2.CloudTasksClient()

        # キューのフルパス
        self._queue_path = self._client.queue_path(
            self._project_id,
            self._location,
            self._queue_name
        )

        logger.info(
            f"[GCPCloudTasks] Initialized: project={self._project_id}, "
            f"location={self._location}, queue={self._queue_name}"
        )

    async def enqueue(self, job_id: str) -> None:
        """
        ジョブをキューに追加

        Args:
            job_id: キューに追加するジョブID
        """
        try:
            # タスクペイロード
            payload = json.dumps({
                "job_id": job_id,
                "action": "process"
            })

            # タスク定義
            if self._target_url:
                # HTTPターゲット
                task = {
                    "http_request": {
                        "http_method": tasks_v2.HttpMethod.POST,
                        "url": self._target_url,
                        "headers": {
                            "Content-Type": "application/json"
                        },
                        "body": payload.encode()
                    }
                }
            else:
                # App Engineターゲット
                task = {
                    "app_engine_http_request": {
                        "http_method": tasks_v2.HttpMethod.POST,
                        "relative_uri": "/process-job",
                        "headers": {
                            "Content-Type": "application/json"
                        },
                        "body": payload.encode()
                    }
                }

            # タスクを作成
            response = self._client.create_task(
                parent=self._queue_path,
                task=task
            )

            logger.info(
                f"[GCPCloudTasks] Job enqueued: {job_id}, "
                f"task: {response.name}"
            )

        except Exception as e:
            logger.error(f"[GCPCloudTasks] Error enqueuing job {job_id}: {e}")
            raise

    async def dequeue(self) -> Optional[str]:
        """
        キューからジョブIDを取得

        Returns:
            ジョブID（キューが空の場合はNone）

        Note:
            Cloud Tasksはプッシュ型のため、この関数は通常使用されません。
            Cloud FunctionsやCloud Runがタスクを受信して処理します。
        """
        logger.warning(
            "[GCPCloudTasks] dequeue() called, but Cloud Tasks is push-based. "
            "Jobs are delivered via HTTP to the target URL."
        )
        return None

    async def get_queue_length(self) -> int:
        """
        キュー内のタスク数を取得（概算）

        Returns:
            タスク数（概算）
        """
        try:
            # Cloud Tasks APIではキュー長を直接取得する方法がないため、
            # タスクをリストして数える（パフォーマンスに注意）
            tasks = list(self._client.list_tasks(parent=self._queue_path))
            count = len(tasks)
            logger.debug(f"[GCPCloudTasks] Queue length: {count}")
            return count
        except Exception as e:
            logger.error(f"[GCPCloudTasks] Error getting queue length: {e}")
            return 0

    async def purge(self) -> None:
        """キューを空にする"""
        try:
            self._client.purge_queue(name=self._queue_path)
            logger.info(f"[GCPCloudTasks] Queue purged: {self._queue_name}")
        except Exception as e:
            logger.error(f"[GCPCloudTasks] Error purging queue: {e}")
            raise


def parse_cloud_task_request(request_body: bytes) -> Optional[str]:
    """
    Cloud TasksからのリクエストをパースしてジョブIDを取得

    Cloud Functions/Cloud Runのハンドラーから呼び出されます。

    Args:
        request_body: HTTPリクエストボディ

    Returns:
        ジョブID
    """
    try:
        data = json.loads(request_body.decode("utf-8"))
        return data.get("job_id")
    except json.JSONDecodeError:
        logger.error("[GCPCloudTasks] Invalid JSON in request body")
        return None
    except Exception as e:
        logger.error(f"[GCPCloudTasks] Error parsing request: {e}")
        return None


def is_cloud_task_request(headers: dict) -> bool:
    """
    リクエストがCloud Tasksからのものかどうかを判定

    Args:
        headers: HTTPリクエストヘッダー

    Returns:
        Cloud Tasksからのリクエストの場合True
    """
    # Cloud Tasksは特定のヘッダーを付与する
    task_name = headers.get("X-CloudTasks-TaskName")
    queue_name = headers.get("X-CloudTasks-QueueName")
    return bool(task_name and queue_name)
