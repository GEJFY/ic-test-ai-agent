"""
================================================================================
memory.py - インメモリジョブストレージ実装
================================================================================

【概要】
ローカル開発およびテスト用のインメモリジョブストレージ実装です。
サーバー再起動でデータは消失します。

【用途】
- ローカル開発環境
- ユニットテスト
- 統合テスト

【注意】
本番環境では使用しないでください。
Azure/AWS/GCPの永続化ストレージを使用してください。

================================================================================
"""

import asyncio
from collections import OrderedDict
from datetime import datetime
from typing import Dict, List, Optional
import logging

from core.async_job_manager import (
    JobStorageBase,
    JobQueueBase,
    EvaluationJob,
    JobStatus,
    generate_job_id,
)

logger = logging.getLogger(__name__)


class InMemoryJobStorage(JobStorageBase):
    """
    インメモリジョブストレージ

    メモリ内の辞書でジョブを管理します。
    スレッドセーフではありませんが、asyncio環境では問題なく動作します。
    """

    def __init__(self, max_jobs: int = 1000):
        """
        Args:
            max_jobs: 保持する最大ジョブ数（古いものから削除）
        """
        self._jobs: OrderedDict[str, EvaluationJob] = OrderedDict()
        self._max_jobs = max_jobs
        self._lock = asyncio.Lock()
        logger.info(f"[InMemoryJobStorage] Initialized (max_jobs={max_jobs})")

    async def create_job(
        self,
        tenant_id: str,
        items: List[Dict]
    ) -> EvaluationJob:
        """新規ジョブを作成"""
        async with self._lock:
            job_id = generate_job_id()

            job = EvaluationJob(
                job_id=job_id,
                tenant_id=tenant_id,
                status=JobStatus.PENDING,
                items=items,
                created_at=datetime.utcnow(),
                message="Job created, waiting for processing"
            )

            # 最大件数を超えた場合、古いジョブを削除
            while len(self._jobs) >= self._max_jobs:
                oldest_id, _ = self._jobs.popitem(last=False)
                logger.debug(f"[InMemoryJobStorage] Removed old job: {oldest_id}")

            self._jobs[job_id] = job
            logger.info(
                f"[InMemoryJobStorage] Job created: {job_id}, "
                f"tenant: {tenant_id}, items: {len(items)}"
            )

            return job

    async def get_job(self, job_id: str) -> Optional[EvaluationJob]:
        """ジョブを取得"""
        async with self._lock:
            job = self._jobs.get(job_id)
            if job:
                logger.debug(f"[InMemoryJobStorage] Job retrieved: {job_id}")
            else:
                logger.debug(f"[InMemoryJobStorage] Job not found: {job_id}")
            return job

    async def update_job(self, job: EvaluationJob) -> None:
        """ジョブを更新"""
        async with self._lock:
            if job.job_id not in self._jobs:
                logger.warning(
                    f"[InMemoryJobStorage] Cannot update non-existent job: {job.job_id}"
                )
                return

            self._jobs[job.job_id] = job
            logger.debug(
                f"[InMemoryJobStorage] Job updated: {job.job_id}, "
                f"status: {job.status.value}, progress: {job.progress}%"
            )

    async def delete_job(self, job_id: str) -> bool:
        """ジョブを削除"""
        async with self._lock:
            if job_id in self._jobs:
                del self._jobs[job_id]
                logger.info(f"[InMemoryJobStorage] Job deleted: {job_id}")
                return True
            else:
                logger.warning(
                    f"[InMemoryJobStorage] Cannot delete non-existent job: {job_id}"
                )
                return False

    async def get_pending_jobs(self, limit: int = 10) -> List[EvaluationJob]:
        """処理待ちジョブを取得"""
        async with self._lock:
            pending_jobs = [
                job for job in self._jobs.values()
                if job.status == JobStatus.PENDING
            ]
            # 作成日時順（古い順）でソート
            pending_jobs.sort(key=lambda j: j.created_at or datetime.min)
            result = pending_jobs[:limit]
            logger.debug(
                f"[InMemoryJobStorage] Found {len(result)} pending jobs "
                f"(total pending: {len(pending_jobs)})"
            )
            return result

    async def get_jobs_by_tenant(
        self,
        tenant_id: str,
        limit: int = 100,
        status: Optional[JobStatus] = None
    ) -> List[EvaluationJob]:
        """テナントのジョブ一覧を取得"""
        async with self._lock:
            tenant_jobs = [
                job for job in self._jobs.values()
                if job.tenant_id == tenant_id
            ]

            if status:
                tenant_jobs = [j for j in tenant_jobs if j.status == status]

            # 作成日時順（新しい順）でソート
            tenant_jobs.sort(
                key=lambda j: j.created_at or datetime.min,
                reverse=True
            )

            result = tenant_jobs[:limit]
            logger.debug(
                f"[InMemoryJobStorage] Found {len(result)} jobs for tenant: {tenant_id}"
            )
            return result

    def get_stats(self) -> Dict:
        """統計情報を取得（デバッグ用）"""
        status_counts = {}
        for job in self._jobs.values():
            status = job.status.value
            status_counts[status] = status_counts.get(status, 0) + 1

        return {
            "total_jobs": len(self._jobs),
            "max_jobs": self._max_jobs,
            "status_counts": status_counts
        }


class InMemoryJobQueue(JobQueueBase):
    """
    インメモリジョブキュー

    メモリ内のリストでキューを管理します。
    FIFO（先入れ先出し）方式で動作します。
    """

    def __init__(self):
        self._queue: List[str] = []
        self._lock = asyncio.Lock()
        logger.info("[InMemoryJobQueue] Initialized")

    async def enqueue(self, job_id: str) -> None:
        """ジョブをキューに追加"""
        async with self._lock:
            self._queue.append(job_id)
            logger.debug(
                f"[InMemoryJobQueue] Job enqueued: {job_id}, "
                f"queue size: {len(self._queue)}"
            )

    async def dequeue(self) -> Optional[str]:
        """キューからジョブIDを取得"""
        async with self._lock:
            if self._queue:
                job_id = self._queue.pop(0)
                logger.debug(
                    f"[InMemoryJobQueue] Job dequeued: {job_id}, "
                    f"remaining: {len(self._queue)}"
                )
                return job_id
            return None

    async def peek(self) -> Optional[str]:
        """キューの先頭を確認（削除しない）"""
        async with self._lock:
            if self._queue:
                return self._queue[0]
            return None

    async def size(self) -> int:
        """キューのサイズを取得"""
        async with self._lock:
            return len(self._queue)

    async def clear(self) -> None:
        """キューをクリア"""
        async with self._lock:
            count = len(self._queue)
            self._queue.clear()
            logger.info(f"[InMemoryJobQueue] Cleared {count} jobs from queue")
