"""
================================================================================
async_job_manager.py - 非同期ジョブ管理モジュール
================================================================================

【概要】
内部統制テスト評価の非同期処理を管理するためのジョブ管理モジュールです。
504 Gateway Timeout問題を解決するため、処理を非同期化します。

【処理フロー】
1. クライアント（VBA/PowerShell）がジョブを送信
2. 即座にジョブIDを返却（タイムアウト回避）
3. バックグラウンドワーカーがジョブを処理
4. クライアントがステータスをポーリング
5. 完了後、結果を取得

【マルチクラウド対応】
- Azure: Cosmos DB + Queue Storage
- AWS: DynamoDB + SQS
- GCP: Firestore + Cloud Tasks

================================================================================
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)


# =============================================================================
# ジョブステータス定義
# =============================================================================

class JobStatus(Enum):
    """ジョブの状態を表す列挙型"""
    PENDING = "pending"      # 処理待ち
    RUNNING = "running"      # 処理中
    COMPLETED = "completed"  # 完了
    FAILED = "failed"        # 失敗
    CANCELLED = "cancelled"  # キャンセル


# =============================================================================
# データクラス定義
# =============================================================================

@dataclass
class EvaluationJob:
    """
    評価ジョブを表すデータクラス

    Attributes:
        job_id: ジョブの一意識別子（UUID）
        tenant_id: テナント識別子（マルチテナント対応）
        status: ジョブの状態
        items: 評価対象の項目リスト
        results: 評価結果（完了時のみ）
        progress: 進捗率（0-100）
        message: 現在の状態メッセージ
        created_at: ジョブ作成日時
        started_at: 処理開始日時
        completed_at: 処理完了日時
        error_message: エラーメッセージ（失敗時のみ）
        metadata: 追加メタデータ
    """
    job_id: str
    tenant_id: str
    status: JobStatus
    items: List[Dict[str, Any]]
    results: Optional[List[Dict[str, Any]]] = None
    progress: int = 0
    message: str = ""
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """初期化後の処理"""
        if self.created_at is None:
            self.created_at = datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        """辞書形式に変換（シリアライズ用）"""
        return {
            "job_id": self.job_id,
            "tenant_id": self.tenant_id,
            "status": self.status.value,
            "items": self.items,
            "results": self.results,
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error_message": self.error_message,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "EvaluationJob":
        """辞書形式から復元（デシリアライズ用）"""
        return cls(
            job_id=data["job_id"],
            tenant_id=data["tenant_id"],
            status=JobStatus(data["status"]),
            items=data["items"],
            results=data.get("results"),
            progress=data.get("progress", 0),
            message=data.get("message", ""),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else None,
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error_message=data.get("error_message", ""),
            metadata=data.get("metadata", {})
        )


@dataclass
class JobSubmitResponse:
    """ジョブ送信レスポンス"""
    job_id: str
    status: str
    estimated_time: int  # 推定処理時間（秒）
    message: str = "Job submitted successfully"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "estimated_time": self.estimated_time,
            "message": self.message
        }


@dataclass
class JobStatusResponse:
    """ジョブステータスレスポンス"""
    job_id: str
    status: str
    progress: int
    message: str
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "job_id": self.job_id,
            "status": self.status,
            "progress": self.progress,
            "message": self.message
        }
        if self.error_message:
            result["error_message"] = self.error_message
        return result


@dataclass
class JobResultsResponse:
    """ジョブ結果レスポンス"""
    job_id: str
    status: str
    results: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status,
            "results": self.results
        }


# =============================================================================
# ジョブストレージ抽象クラス
# =============================================================================

class JobStorageBase(ABC):
    """
    ジョブストレージの抽象基底クラス

    各クラウドプロバイダー用の実装クラスはこのクラスを継承します。
    - Azure: AzureCosmosJobStorage
    - AWS: AWSDynamoDBJobStorage
    - GCP: GCPFirestoreJobStorage
    """

    @abstractmethod
    async def create_job(self, tenant_id: str, items: List[Dict[str, Any]]) -> EvaluationJob:
        """
        新規ジョブを作成

        Args:
            tenant_id: テナント識別子
            items: 評価対象項目のリスト

        Returns:
            作成されたEvaluationJob
        """
        pass

    @abstractmethod
    async def get_job(self, job_id: str) -> Optional[EvaluationJob]:
        """
        ジョブを取得

        Args:
            job_id: ジョブID

        Returns:
            EvaluationJob（存在しない場合はNone）
        """
        pass

    @abstractmethod
    async def update_job(self, job: EvaluationJob) -> None:
        """
        ジョブを更新

        Args:
            job: 更新するEvaluationJob
        """
        pass

    @abstractmethod
    async def delete_job(self, job_id: str) -> bool:
        """
        ジョブを削除

        Args:
            job_id: ジョブID

        Returns:
            削除成功したらTrue
        """
        pass

    @abstractmethod
    async def get_pending_jobs(self, limit: int = 10) -> List[EvaluationJob]:
        """
        処理待ちジョブを取得

        Args:
            limit: 取得する最大件数

        Returns:
            処理待ちジョブのリスト
        """
        pass

    @abstractmethod
    async def get_jobs_by_tenant(
        self,
        tenant_id: str,
        limit: int = 100,
        status: Optional[JobStatus] = None
    ) -> List[EvaluationJob]:
        """
        テナントのジョブ一覧を取得

        Args:
            tenant_id: テナント識別子
            limit: 取得する最大件数
            status: フィルタするステータス（Noneの場合は全て）

        Returns:
            ジョブのリスト
        """
        pass


# =============================================================================
# ジョブキュー抽象クラス
# =============================================================================

class JobQueueBase(ABC):
    """
    ジョブキューの抽象基底クラス

    バックグラウンドワーカーへのジョブ通知を管理します。
    - Azure: Azure Queue Storage
    - AWS: Amazon SQS
    - GCP: Cloud Tasks
    """

    @abstractmethod
    async def enqueue(self, job_id: str) -> None:
        """
        ジョブをキューに追加

        Args:
            job_id: キューに追加するジョブID
        """
        pass

    @abstractmethod
    async def dequeue(self) -> Optional[str]:
        """
        キューからジョブIDを取得

        Returns:
            ジョブID（キューが空の場合はNone）
        """
        pass


# =============================================================================
# ジョブマネージャー
# =============================================================================

class AsyncJobManager:
    """
    非同期ジョブ管理クラス

    ジョブの作成、ステータス取得、結果取得などの操作を提供します。
    """

    # 1項目あたりの推定処理時間（秒）
    ESTIMATED_TIME_PER_ITEM = 60

    def __init__(self, storage: JobStorageBase, queue: Optional[JobQueueBase] = None):
        """
        Args:
            storage: ジョブストレージ実装
            queue: ジョブキュー実装（オプション）
        """
        self.storage = storage
        self.queue = queue
        logger.info("[AsyncJobManager] Initialized")

    async def submit_job(
        self,
        tenant_id: str,
        items: List[Dict[str, Any]]
    ) -> JobSubmitResponse:
        """
        新規ジョブを送信

        Args:
            tenant_id: テナント識別子
            items: 評価対象項目のリスト

        Returns:
            JobSubmitResponse
        """
        # ジョブを作成
        job = await self.storage.create_job(tenant_id, items)

        logger.info(
            f"[AsyncJobManager] Job submitted: {job.job_id}, "
            f"tenant: {tenant_id}, items: {len(items)}"
        )

        # キューに追加（設定されている場合）
        if self.queue:
            await self.queue.enqueue(job.job_id)
            logger.info(f"[AsyncJobManager] Job enqueued: {job.job_id}")

        # 推定処理時間を計算
        estimated_time = len(items) * self.ESTIMATED_TIME_PER_ITEM

        return JobSubmitResponse(
            job_id=job.job_id,
            status=job.status.value,
            estimated_time=estimated_time
        )

    async def get_status(self, job_id: str) -> JobStatusResponse:
        """
        ジョブのステータスを取得

        Args:
            job_id: ジョブID

        Returns:
            JobStatusResponse
        """
        job = await self.storage.get_job(job_id)

        if not job:
            logger.warning(f"[AsyncJobManager] Job not found: {job_id}")
            return JobStatusResponse(
                job_id=job_id,
                status="not_found",
                progress=0,
                message="Job not found",
                error_message="The specified job does not exist"
            )

        return JobStatusResponse(
            job_id=job.job_id,
            status=job.status.value,
            progress=job.progress,
            message=job.message,
            error_message=job.error_message
        )

    async def get_results(self, job_id: str) -> JobResultsResponse:
        """
        ジョブの結果を取得

        Args:
            job_id: ジョブID

        Returns:
            JobResultsResponse
        """
        job = await self.storage.get_job(job_id)

        if not job:
            logger.warning(f"[AsyncJobManager] Job not found: {job_id}")
            return JobResultsResponse(
                job_id=job_id,
                status="not_found",
                results=[]
            )

        if job.status != JobStatus.COMPLETED:
            logger.info(
                f"[AsyncJobManager] Job not completed: {job_id}, "
                f"status: {job.status.value}"
            )
            return JobResultsResponse(
                job_id=job.job_id,
                status=job.status.value,
                results=[]
            )

        return JobResultsResponse(
            job_id=job.job_id,
            status=job.status.value,
            results=job.results or []
        )

    async def cancel_job(self, job_id: str) -> bool:
        """
        ジョブをキャンセル

        Args:
            job_id: ジョブID

        Returns:
            キャンセル成功したらTrue
        """
        job = await self.storage.get_job(job_id)

        if not job:
            return False

        # 実行中または待機中のジョブのみキャンセル可能
        if job.status not in [JobStatus.PENDING, JobStatus.RUNNING]:
            return False

        job.status = JobStatus.CANCELLED
        job.message = "Job cancelled by user"
        job.completed_at = datetime.utcnow()

        await self.storage.update_job(job)
        logger.info(f"[AsyncJobManager] Job cancelled: {job_id}")

        return True


# =============================================================================
# ユーティリティ関数
# =============================================================================

def generate_job_id() -> str:
    """新しいジョブIDを生成"""
    return str(uuid.uuid4())


def calculate_estimated_time(item_count: int, time_per_item: int = 60) -> int:
    """推定処理時間を計算"""
    return item_count * time_per_item
