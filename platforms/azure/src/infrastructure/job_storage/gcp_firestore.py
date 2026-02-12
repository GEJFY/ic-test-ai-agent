"""
================================================================================
gcp_firestore.py - GCP Firestore ジョブストレージ実装
================================================================================

【概要】
GCP Firestoreを使用したジョブストレージ実装です。

【必要な環境変数】
- GCP_PROJECT_ID: GCPプロジェクトID
- GCP_FIRESTORE_COLLECTION: コレクション名（デフォルト: evaluation_jobs）
- GOOGLE_APPLICATION_CREDENTIALS: サービスアカウントキーのパス
  （Cloud Functions/Cloud Run上では自動認証）

【コレクション設計】
コレクション名: evaluation_jobs
ドキュメントID: job_id
- tenant_id: テナントID
- status: ジョブ状態
- items: 評価対象項目（JSON配列）
- results: 評価結果（JSON配列）
- progress: 進捗率
- created_at: 作成日時
- etc.

【必要なパッケージ】
pip install google-cloud-firestore

================================================================================
"""

import os
import logging
from datetime import datetime
from typing import List, Dict, Any, Optional

from core.async_job_manager import (
    JobStorageBase,
    EvaluationJob,
    JobStatus,
    generate_job_id,
)

logger = logging.getLogger(__name__)

# Firestore SDK
try:
    from google.cloud import firestore
    from google.cloud.firestore_v1.base_query import FieldFilter
    FIRESTORE_AVAILABLE = True
except ImportError:
    FIRESTORE_AVAILABLE = False
    logger.warning(
        "[GCPFirestore] google-cloud-firestore not installed. "
        "Run: pip install google-cloud-firestore"
    )


class GCPFirestoreJobStorage(JobStorageBase):
    """
    GCP Firestore ジョブストレージ

    Firestoreを使用してジョブを永続化します。
    """

    DEFAULT_COLLECTION = "evaluation_jobs"

    def __init__(
        self,
        project_id: str = None,
        collection_name: str = None,
        credentials_path: str = None
    ):
        """
        Args:
            project_id: GCPプロジェクトID
            collection_name: コレクション名（デフォルト: evaluation_jobs）
            credentials_path: サービスアカウントキーのパス
        """
        if not FIRESTORE_AVAILABLE:
            raise ImportError(
                "google-cloud-firestore is required. "
                "Install it with: pip install google-cloud-firestore"
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

        # コレクション名
        self._collection_name = (
            collection_name or
            os.getenv("GCP_FIRESTORE_COLLECTION") or
            self.DEFAULT_COLLECTION
        )

        # 認証情報パス（オプション）
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

        # Firestoreクライアント初期化
        self._db = firestore.Client(project=self._project_id)
        self._collection = self._db.collection(self._collection_name)

        logger.info(
            f"[GCPFirestore] Initialized: project={self._project_id}, "
            f"collection={self._collection_name}"
        )

    def _job_to_doc(self, job: EvaluationJob) -> Dict[str, Any]:
        """EvaluationJobをFirestoreドキュメントに変換"""
        return {
            "job_id": job.job_id,
            "tenant_id": job.tenant_id,
            "status": job.status.value,
            "items": job.items,
            "results": job.results if job.results else None,
            "progress": job.progress,
            "message": job.message,
            "created_at": job.created_at,
            "started_at": job.started_at,
            "completed_at": job.completed_at,
            "error_message": job.error_message,
            "metadata": job.metadata if job.metadata else {}
        }

    def _doc_to_job(self, doc_data: Dict[str, Any]) -> EvaluationJob:
        """FirestoreドキュメントをEvaluationJobに変換"""
        # Firestoreのタイムスタンプをdatetimeに変換
        created_at = doc_data.get("created_at")
        if hasattr(created_at, "timestamp"):
            created_at = datetime.fromtimestamp(created_at.timestamp())

        started_at = doc_data.get("started_at")
        if hasattr(started_at, "timestamp"):
            started_at = datetime.fromtimestamp(started_at.timestamp())

        completed_at = doc_data.get("completed_at")
        if hasattr(completed_at, "timestamp"):
            completed_at = datetime.fromtimestamp(completed_at.timestamp())

        return EvaluationJob(
            job_id=doc_data.get("job_id"),
            tenant_id=doc_data.get("tenant_id"),
            status=JobStatus(doc_data.get("status", "pending")),
            items=doc_data.get("items", []),
            results=doc_data.get("results"),
            progress=doc_data.get("progress", 0),
            message=doc_data.get("message", ""),
            created_at=created_at,
            started_at=started_at,
            completed_at=completed_at,
            error_message=doc_data.get("error_message", ""),
            metadata=doc_data.get("metadata", {})
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

        doc_data = self._job_to_doc(job)
        self._collection.document(job_id).set(doc_data)

        logger.info(
            f"[GCPFirestore] Job created: {job_id}, "
            f"tenant: {tenant_id}, items: {len(items)}"
        )

        return job

    async def get_job(self, job_id: str) -> Optional[EvaluationJob]:
        """ジョブを取得"""
        try:
            doc_ref = self._collection.document(job_id)
            doc = doc_ref.get()

            if doc.exists:
                job = self._doc_to_job(doc.to_dict())
                logger.debug(f"[GCPFirestore] Job retrieved: {job_id}")
                return job
            else:
                logger.debug(f"[GCPFirestore] Job not found: {job_id}")
                return None

        except Exception as e:
            logger.error(f"[GCPFirestore] Error getting job {job_id}: {e}")
            return None

    async def update_job(self, job: EvaluationJob) -> None:
        """ジョブを更新"""
        try:
            doc_data = self._job_to_doc(job)
            self._collection.document(job.job_id).set(doc_data, merge=True)

            logger.debug(
                f"[GCPFirestore] Job updated: {job.job_id}, "
                f"status: {job.status.value}, progress: {job.progress}%"
            )

        except Exception as e:
            logger.error(f"[GCPFirestore] Error updating job {job.job_id}: {e}")
            raise

    async def delete_job(self, job_id: str) -> bool:
        """ジョブを削除"""
        try:
            doc_ref = self._collection.document(job_id)
            doc = doc_ref.get()

            if not doc.exists:
                logger.warning(f"[GCPFirestore] Job not found for deletion: {job_id}")
                return False

            doc_ref.delete()
            logger.info(f"[GCPFirestore] Job deleted: {job_id}")
            return True

        except Exception as e:
            logger.error(f"[GCPFirestore] Error deleting job {job_id}: {e}")
            return False

    async def get_pending_jobs(self, limit: int = 10) -> List[EvaluationJob]:
        """処理待ちジョブを取得"""
        try:
            # status = 'pending' のジョブを作成日時順で取得
            query = (
                self._collection
                .where(filter=FieldFilter("status", "==", "pending"))
                .order_by("created_at")
                .limit(limit)
            )
            docs = query.stream()

            jobs = [self._doc_to_job(doc.to_dict()) for doc in docs]

            logger.debug(f"[GCPFirestore] Found {len(jobs)} pending jobs")
            return jobs

        except Exception as e:
            logger.error(f"[GCPFirestore] Error getting pending jobs: {e}")
            return []

    async def get_jobs_by_tenant(
        self,
        tenant_id: str,
        limit: int = 100,
        status: Optional[JobStatus] = None
    ) -> List[EvaluationJob]:
        """テナントのジョブ一覧を取得"""
        try:
            query = self._collection.where(
                filter=FieldFilter("tenant_id", "==", tenant_id)
            )

            if status:
                query = query.where(
                    filter=FieldFilter("status", "==", status.value)
                )

            query = query.order_by("created_at", direction=firestore.Query.DESCENDING)
            query = query.limit(limit)

            docs = query.stream()
            jobs = [self._doc_to_job(doc.to_dict()) for doc in docs]

            logger.debug(
                f"[GCPFirestore] Found {len(jobs)} jobs for tenant: {tenant_id}"
            )
            return jobs

        except Exception as e:
            logger.error(
                f"[GCPFirestore] Error getting jobs for tenant {tenant_id}: {e}"
            )
            return []
