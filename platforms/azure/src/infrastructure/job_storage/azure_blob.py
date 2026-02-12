# -*- coding: utf-8 -*-
"""
================================================================================
azure_blob.py - Azure Blob Storage証跡ファイルストレージ
================================================================================

【概要】
全ての証跡ファイル（Base64）をBlob Storageに保存するヘルパー。
Azure Table Storageの64KB制限を回避するために使用。

【重要】
Azure Table Storageは1エンティティあたり64KB制限があります。
複数の小さなファイル（例: 10KB × 10 = 100KB）でも合計で超過するため、
サイズに関わらず全ての証跡ファイルをBlob Storageに保存します。

【必要な環境変数】
- AZURE_STORAGE_CONNECTION_STRING: ストレージアカウント接続文字列
  または AzureWebJobsStorage

【Blob構造】
evidence-files/{job_id}/{item_id}/{index}_{fileName}

================================================================================
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Azure Blob Storage SDK
try:
    from azure.storage.blob import BlobServiceClient, ContainerClient
    from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
    AZURE_BLOB_AVAILABLE = True
    logger.info("[AzureBlobStorage] azure-storage-blob imported successfully")
except ImportError as e:
    AZURE_BLOB_AVAILABLE = False
    logger.error(
        f"[AzureBlobStorage] azure-storage-blob not installed: {e}. "
        "Run: pip install azure-storage-blob"
    )


class EvidenceBlobStorage:
    """
    証跡ファイル用Blob Storage

    全てのevidenceFilesをBlobに保存し、参照を返す。
    Azure Table Storageの64KB制限を確実に回避するため、
    サイズに関わらず全ファイルをBlobに保存する。
    """

    CONTAINER_NAME = "evidence-files"
    # 64KB制限対策: 全ての証跡ファイルをBlobに保存
    # Azure Table Storageは1エンティティ64KB制限があり、
    # 複数の小さなファイルの合計でも超過する可能性があるため
    MAX_INLINE_SIZE = 0  # 全ファイルをBlobに保存（0 = インライン保存しない）

    def __init__(self, connection_string: str = None):
        """
        Args:
            connection_string: ストレージ接続文字列
        """
        if not AZURE_BLOB_AVAILABLE:
            raise ImportError(
                "azure-storage-blob is required. "
                "Install it with: pip install azure-storage-blob"
            )

        self._connection_string = (
            connection_string or
            os.getenv("AZURE_STORAGE_CONNECTION_STRING") or
            os.getenv("AzureWebJobsStorage")
        )

        if not self._connection_string:
            raise ValueError(
                "Azure Storage connection string is required. "
                "Set AZURE_STORAGE_CONNECTION_STRING environment variable."
            )

        self._blob_service = BlobServiceClient.from_connection_string(
            self._connection_string
        )
        self._container_client = None
        self._ensure_container_exists()

        logger.info(f"[EvidenceBlobStorage] Initialized with container: {self.CONTAINER_NAME}")

    def _ensure_container_exists(self):
        """コンテナが存在することを確認"""
        try:
            self._container_client = self._blob_service.create_container(
                self.CONTAINER_NAME
            )
            logger.info(f"[EvidenceBlobStorage] Container created: {self.CONTAINER_NAME}")
        except ResourceExistsError:
            self._container_client = self._blob_service.get_container_client(
                self.CONTAINER_NAME
            )
            logger.debug(f"[EvidenceBlobStorage] Container already exists: {self.CONTAINER_NAME}")

    def store_evidence_files(
        self,
        job_id: str,
        item_id: str,
        evidence_files: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        証跡ファイルをBlobに保存

        Args:
            job_id: ジョブID
            item_id: アイテムID
            evidence_files: 証跡ファイルリスト

        Returns:
            参照情報に変換された証跡ファイルリスト
        """
        logger.info(
            f"[EvidenceBlobStorage] store_evidence_files called: "
            f"job_id={job_id}, item_id={item_id}, files={len(evidence_files)}"
        )

        if not evidence_files:
            return []

        result = []
        for i, ef in enumerate(evidence_files):
            base64_data = ef.get("base64", "")
            logger.info(f"[EvidenceBlobStorage] Processing file {i}: size={len(base64_data)} bytes")

            # 小さいファイルはそのまま
            if len(base64_data) <= self.MAX_INLINE_SIZE:
                logger.info(f"[EvidenceBlobStorage] File {i} is small ({len(base64_data)} <= {self.MAX_INLINE_SIZE}), keeping inline")
                result.append(ef)
                continue

            # 大きいファイルはBlobに保存
            blob_name = f"{job_id}/{item_id}/{i}_{ef.get('fileName', 'unknown')}"

            try:
                blob_client = self._container_client.get_blob_client(blob_name)
                blob_client.upload_blob(base64_data.encode('utf-8'), overwrite=True)

                # 参照情報に置換
                result.append({
                    "fileName": ef.get("fileName", ""),
                    "mimeType": ef.get("mimeType", ""),
                    "extension": ef.get("extension", ""),
                    "_blobRef": blob_name,  # Blob参照
                    "_originalSize": len(base64_data)
                })

                logger.debug(
                    f"[EvidenceBlobStorage] Stored evidence to blob: {blob_name}, "
                    f"size: {len(base64_data)}"
                )

            except Exception as e:
                logger.error(f"[EvidenceBlobStorage] Failed to store blob {blob_name}: {e}")
                # エラー時は空のbase64で続行
                result.append({
                    "fileName": ef.get("fileName", ""),
                    "mimeType": ef.get("mimeType", ""),
                    "extension": ef.get("extension", ""),
                    "base64": "",
                    "_error": str(e)
                })

        return result

    def restore_evidence_files(
        self,
        evidence_files: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Blobから証跡ファイルを復元

        Args:
            evidence_files: 参照情報を含む証跡ファイルリスト

        Returns:
            base64データを復元した証跡ファイルリスト
        """
        if not evidence_files:
            return []

        result = []
        for ef in evidence_files:
            blob_ref = ef.get("_blobRef")

            if not blob_ref:
                # Blob参照がない場合はそのまま
                result.append(ef)
                continue

            try:
                blob_client = self._container_client.get_blob_client(blob_ref)
                blob_data = blob_client.download_blob().readall()
                base64_data = blob_data.decode('utf-8')

                # 元の形式に復元
                result.append({
                    "fileName": ef.get("fileName", ""),
                    "mimeType": ef.get("mimeType", ""),
                    "extension": ef.get("extension", ""),
                    "base64": base64_data
                })

                logger.debug(
                    f"[EvidenceBlobStorage] Restored evidence from blob: {blob_ref}, "
                    f"size: {len(base64_data)}"
                )

            except ResourceNotFoundError:
                logger.warning(f"[EvidenceBlobStorage] Blob not found: {blob_ref}")
                result.append({
                    "fileName": ef.get("fileName", ""),
                    "mimeType": ef.get("mimeType", ""),
                    "extension": ef.get("extension", ""),
                    "base64": "",
                    "_error": "Blob not found"
                })
            except Exception as e:
                logger.error(f"[EvidenceBlobStorage] Failed to restore blob {blob_ref}: {e}")
                result.append({
                    "fileName": ef.get("fileName", ""),
                    "mimeType": ef.get("mimeType", ""),
                    "extension": ef.get("extension", ""),
                    "base64": "",
                    "_error": str(e)
                })

        return result

    def delete_evidence_files(self, job_id: str) -> bool:
        """
        ジョブの証跡ファイルを削除

        Args:
            job_id: ジョブID

        Returns:
            削除成功したらTrue
        """
        try:
            prefix = f"{job_id}/"
            blobs = self._container_client.list_blobs(name_starts_with=prefix)

            deleted_count = 0
            for blob in blobs:
                self._container_client.delete_blob(blob.name)
                deleted_count += 1

            if deleted_count > 0:
                logger.info(
                    f"[EvidenceBlobStorage] Deleted {deleted_count} blobs for job: {job_id}"
                )

            return True

        except Exception as e:
            logger.error(f"[EvidenceBlobStorage] Failed to delete blobs for job {job_id}: {e}")
            return False


# シングルトンインスタンス
_evidence_storage: Optional[EvidenceBlobStorage] = None


def get_evidence_storage() -> Optional[EvidenceBlobStorage]:
    """
    証跡ストレージのシングルトンインスタンスを取得

    Returns:
        EvidenceBlobStorage（利用不可の場合はNone）
    """
    global _evidence_storage

    if _evidence_storage is not None:
        logger.info("[EvidenceBlobStorage] Returning cached instance")
        return _evidence_storage

    logger.info(f"[EvidenceBlobStorage] AZURE_BLOB_AVAILABLE = {AZURE_BLOB_AVAILABLE}")

    if not AZURE_BLOB_AVAILABLE:
        logger.error("[EvidenceBlobStorage] azure-storage-blob not installed!")
        return None

    try:
        logger.info("[EvidenceBlobStorage] Creating new instance...")
        _evidence_storage = EvidenceBlobStorage()
        logger.info("[EvidenceBlobStorage] Instance created successfully")
        return _evidence_storage
    except Exception as e:
        logger.error(f"[EvidenceBlobStorage] Failed to initialize: {e}", exc_info=True)
        return None
