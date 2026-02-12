"""
================================================================================
azure_table.py - Azure Table Storageジョブストレージ実装
================================================================================

【概要】
Azure Table Storageを使用したジョブストレージ実装です。
Cosmos DBよりシンプルでコスト効率が良く、本ユースケースに適しています。

【必要な環境変数】
- AZURE_STORAGE_CONNECTION_STRING: ストレージアカウント接続文字列
  または
- AZURE_STORAGE_ACCOUNT_NAME: ストレージアカウント名
- AZURE_STORAGE_ACCOUNT_KEY: ストレージアカウントキー

【テーブル構造】
- PartitionKey: tenant_id（テナント分離）
- RowKey: job_id
- その他のプロパティ: status, items, results, progress, etc.

【必要なパッケージ】
pip install azure-data-tables

================================================================================
"""

import os
import json
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

# Azure Table Storage SDK
try:
    from azure.data.tables import TableServiceClient, TableClient
    from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
    AZURE_TABLES_AVAILABLE = True
except ImportError:
    AZURE_TABLES_AVAILABLE = False
    logger.warning(
        "[AzureTableStorage] azure-data-tables not installed. "
        "Run: pip install azure-data-tables"
    )



class AzureTableJobStorage(JobStorageBase):
    """
    Azure Table Storageジョブストレージ

    Azure Table Storageを使用してジョブを永続化します。
    """

    TABLE_NAME = "EvaluationJobs"

    def __init__(
        self,
        connection_string: str = None,
        account_name: str = None,
        account_key: str = None,
        table_name: str = None
    ):
        """
        Args:
            connection_string: ストレージ接続文字列
            account_name: ストレージアカウント名
            account_key: ストレージアカウントキー
            table_name: テーブル名（デフォルト: EvaluationJobs）
        """
        if not AZURE_TABLES_AVAILABLE:
            raise ImportError(
                "azure-data-tables is required. "
                "Install it with: pip install azure-data-tables"
            )

        # 接続情報の取得
        self._connection_string = (
            connection_string or
            os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        )

        if not self._connection_string:
            account_name = account_name or os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
            account_key = account_key or os.getenv("AZURE_STORAGE_ACCOUNT_KEY")

            if account_name and account_key:
                self._connection_string = (
                    f"DefaultEndpointsProtocol=https;"
                    f"AccountName={account_name};"
                    f"AccountKey={account_key};"
                    f"EndpointSuffix=core.windows.net"
                )

        if not self._connection_string:
            raise ValueError(
                "Azure Storage connection string is required. "
                "Set AZURE_STORAGE_CONNECTION_STRING environment variable."
            )

        self._table_name = table_name or self.TABLE_NAME

        # テーブルクライアントを初期化
        self._table_client = TableClient.from_connection_string(
            conn_str=self._connection_string,
            table_name=self._table_name
        )

        # テーブルを作成（存在しない場合）
        self._ensure_table_exists()

        logger.info(f"[AzureTableStorage] Initialized with table: {self._table_name}")

    def _ensure_table_exists(self):
        """テーブルが存在することを確認"""
        try:
            self._table_client.create_table()
            logger.info(f"[AzureTableStorage] Table created: {self._table_name}")
        except ResourceExistsError:
            logger.debug(f"[AzureTableStorage] Table already exists: {self._table_name}")

    def _job_to_entity(self, job: EvaluationJob) -> Dict[str, Any]:
        """EvaluationJobをTable Entityに変換"""
        return {
            "PartitionKey": job.tenant_id,
            "RowKey": job.job_id,
            "status": job.status.value,
            "items": json.dumps(job.items, ensure_ascii=False),
            "results": json.dumps(job.results, ensure_ascii=False) if job.results else "",
            "progress": job.progress,
            "message": job.message,
            "created_at": job.created_at.isoformat() if job.created_at else "",
            "started_at": job.started_at.isoformat() if job.started_at else "",
            "completed_at": job.completed_at.isoformat() if job.completed_at else "",
            "error_message": job.error_message,
            "metadata": json.dumps(job.metadata, ensure_ascii=False) if job.metadata else "{}"
        }

    def _entity_to_job(self, entity: Dict[str, Any]) -> EvaluationJob:
        """Table EntityをEvaluationJobに変換"""
        return EvaluationJob(
            job_id=entity["RowKey"],
            tenant_id=entity["PartitionKey"],
            status=JobStatus(entity["status"]),
            items=json.loads(entity["items"]) if entity.get("items") else [],
            results=json.loads(entity["results"]) if entity.get("results") else None,
            progress=entity.get("progress", 0),
            message=entity.get("message", ""),
            created_at=datetime.fromisoformat(entity["created_at"]) if entity.get("created_at") else None,
            started_at=datetime.fromisoformat(entity["started_at"]) if entity.get("started_at") else None,
            completed_at=datetime.fromisoformat(entity["completed_at"]) if entity.get("completed_at") else None,
            error_message=entity.get("error_message", ""),
            metadata=json.loads(entity["metadata"]) if entity.get("metadata") else {}
        )

    async def create_job(
        self,
        tenant_id: str,
        items: List[Dict[str, Any]]
    ) -> EvaluationJob:
        """新規ジョブを作成"""
        job_id = generate_job_id()

        # 大きな証跡ファイルをBlobに分離（64KB制限対策）
        processed_items = self._extract_large_evidence(job_id, items)

        job = EvaluationJob(
            job_id=job_id,
            tenant_id=tenant_id,
            status=JobStatus.PENDING,
            items=processed_items,
            created_at=datetime.utcnow(),
            message="Job created, waiting for processing"
        )

        entity = self._job_to_entity(job)
        self._table_client.create_entity(entity=entity)

        logger.info(
            f"[AzureTableStorage] Job created: {job_id}, "
            f"tenant: {tenant_id}, items: {len(items)}"
        )

        return job

    def _extract_large_evidence(
        self,
        job_id: str,
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        大きな証跡ファイルをBlob Storageに分離

        Args:
            job_id: ジョブID
            items: アイテムリスト

        Returns:
            証跡ファイルが参照に置換されたアイテムリスト
        """
        logger.info(f"[AzureTableStorage] _extract_large_evidence called for job {job_id}")

        try:
            from infrastructure.job_storage.azure_blob import get_evidence_storage
            logger.info("[AzureTableStorage] azure_blob module imported successfully")
            evidence_storage = get_evidence_storage()
            logger.info(f"[AzureTableStorage] get_evidence_storage returned: {evidence_storage}")
        except Exception as e:
            logger.error(f"[AzureTableStorage] Blob storage import/init failed: {e}", exc_info=True)
            evidence_storage = None

        if not evidence_storage:
            logger.warning("[AzureTableStorage] Blob storage not available, keeping evidence inline - this may cause 64KB limit errors!")
            return items

        processed = []
        for item in items:
            item_id = item.get("ID", "unknown")
            # Handle both "EvidenceFiles" (from PowerShell) and "evidenceFiles" (from Python tests)
            evidence_files = item.get("EvidenceFiles") or item.get("evidenceFiles") or []
            logger.info(f"[AzureTableStorage] Item {item_id}: found {len(evidence_files)} evidence files")

            if evidence_files:
                # Blobに保存して参照に置換
                processed_evidence = evidence_storage.store_evidence_files(
                    job_id=job_id,
                    item_id=item_id,
                    evidence_files=evidence_files
                )
                item_copy = dict(item)
                # Normalize to "EvidenceFiles" (matching PowerShell convention)
                # Remove old key if different
                item_copy.pop("evidenceFiles", None)
                item_copy["EvidenceFiles"] = processed_evidence
                processed.append(item_copy)
            else:
                processed.append(item)

        return processed

    def _restore_evidence_files(
        self,
        items: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Blobから証跡ファイルを復元

        Args:
            items: アイテムリスト

        Returns:
            証跡ファイルが復元されたアイテムリスト
        """
        try:
            from infrastructure.job_storage.azure_blob import get_evidence_storage
            evidence_storage = get_evidence_storage()
        except Exception as e:
            logger.debug(f"[AzureTableStorage] Blob storage not available for restore: {e}")
            return items

        if not evidence_storage:
            return items

        restored = []
        for item in items:
            # Handle both "EvidenceFiles" and "evidenceFiles"
            evidence_files = item.get("EvidenceFiles") or item.get("evidenceFiles") or []

            # Blob参照があるかチェック
            has_blob_ref = any(ef.get("_blobRef") for ef in evidence_files)

            if has_blob_ref:
                restored_evidence = evidence_storage.restore_evidence_files(evidence_files)
                item_copy = dict(item)
                # Normalize to "EvidenceFiles" (matching PowerShell convention)
                item_copy.pop("evidenceFiles", None)
                item_copy["EvidenceFiles"] = restored_evidence
                restored.append(item_copy)
            else:
                restored.append(item)

        return restored

    async def get_job(self, job_id: str) -> Optional[EvaluationJob]:
        """ジョブを取得"""
        try:
            # job_idだけでは取得できないため、全テナントを検索
            # 効率化のため、job_idをPartitionKeyにする設計も検討可能
            filter_query = f"RowKey eq '{job_id}'"
            entities = list(self._table_client.query_entities(filter_query))

            if entities:
                job = self._entity_to_job(entities[0])
                logger.debug(f"[AzureTableStorage] Job retrieved: {job_id}")
                return job
            else:
                logger.debug(f"[AzureTableStorage] Job not found: {job_id}")
                return None

        except Exception as e:
            logger.error(f"[AzureTableStorage] Error getting job {job_id}: {e}")
            return None

    async def update_job(self, job: EvaluationJob) -> None:
        """ジョブを更新"""
        try:
            entity = self._job_to_entity(job)
            self._table_client.update_entity(entity=entity, mode="merge")

            logger.debug(
                f"[AzureTableStorage] Job updated: {job.job_id}, "
                f"status: {job.status.value}, progress: {job.progress}%"
            )

        except Exception as e:
            logger.error(f"[AzureTableStorage] Error updating job {job.job_id}: {e}")
            raise

    async def delete_job(self, job_id: str) -> bool:
        """ジョブを削除"""
        try:
            # まずジョブを取得してPartitionKeyを確認
            job = await self.get_job(job_id)
            if not job:
                return False

            self._table_client.delete_entity(
                partition_key=job.tenant_id,
                row_key=job_id
            )

            logger.info(f"[AzureTableStorage] Job deleted: {job_id}")
            return True

        except ResourceNotFoundError:
            logger.warning(f"[AzureTableStorage] Job not found for deletion: {job_id}")
            return False
        except Exception as e:
            logger.error(f"[AzureTableStorage] Error deleting job {job_id}: {e}")
            return False

    async def get_pending_jobs(self, limit: int = 10) -> List[EvaluationJob]:
        """処理待ちジョブを取得"""
        try:
            filter_query = f"status eq 'pending'"
            entities = list(self._table_client.query_entities(filter_query))

            jobs = [self._entity_to_job(e) for e in entities]
            # 作成日時順（古い順）でソート
            jobs.sort(key=lambda j: j.created_at or datetime.min)

            result = jobs[:limit]
            logger.debug(
                f"[AzureTableStorage] Found {len(result)} pending jobs "
                f"(total pending: {len(jobs)})"
            )
            return result

        except Exception as e:
            logger.error(f"[AzureTableStorage] Error getting pending jobs: {e}")
            return []

    async def get_jobs_by_tenant(
        self,
        tenant_id: str,
        limit: int = 100,
        status: Optional[JobStatus] = None
    ) -> List[EvaluationJob]:
        """テナントのジョブ一覧を取得"""
        try:
            filter_query = f"PartitionKey eq '{tenant_id}'"
            if status:
                filter_query += f" and status eq '{status.value}'"

            entities = list(self._table_client.query_entities(filter_query))

            jobs = [self._entity_to_job(e) for e in entities]
            # 作成日時順（新しい順）でソート
            jobs.sort(key=lambda j: j.created_at or datetime.min, reverse=True)

            result = jobs[:limit]
            logger.debug(
                f"[AzureTableStorage] Found {len(result)} jobs for tenant: {tenant_id}"
            )
            return result

        except Exception as e:
            logger.error(
                f"[AzureTableStorage] Error getting jobs for tenant {tenant_id}: {e}"
            )
            return []


# エイリアス（互換性のため）
AzureCosmosJobStorage = AzureTableJobStorage
