"""
================================================================================
job_storage - ジョブストレージモジュール
================================================================================

【概要】
非同期ジョブの永続化を担当するストレージ実装を提供します。

【提供する実装】
- InMemoryJobStorage: ローカル開発/テスト用（メモリ内）
- AzureCosmosJobStorage: Azure Cosmos DB
- AWSDynamoDBJobStorage: AWS DynamoDB
- GCPFirestoreJobStorage: GCP Firestore

【使用方法】
環境変数 JOB_STORAGE_PROVIDER で使用するストレージを選択：
- MEMORY: インメモリ（開発用）
- AZURE: Azure Cosmos DB
- AWS: AWS DynamoDB
- GCP: GCP Firestore

================================================================================
"""

from core.async_job_manager import JobStorageBase, JobQueueBase
from infrastructure.job_storage.memory import InMemoryJobStorage, InMemoryJobQueue

__all__ = [
    "JobStorageBase",
    "JobQueueBase",
    "InMemoryJobStorage",
    "InMemoryJobQueue",
    "get_job_storage",
    "get_job_queue",
]


def get_job_storage(provider: str = None) -> JobStorageBase:
    """
    環境設定に基づいてジョブストレージを取得

    Args:
        provider: ストレージプロバイダー（MEMORY/AZURE/AWS/GCP）
                  Noneの場合は環境変数から取得

    Returns:
        JobStorageBase実装
    """
    import os

    if provider is None:
        provider = os.getenv("JOB_STORAGE_PROVIDER", "MEMORY").upper()

    if provider == "MEMORY":
        return InMemoryJobStorage()

    elif provider == "AZURE":
        from infrastructure.job_storage.azure_table import AzureTableJobStorage
        return AzureTableJobStorage()

    elif provider == "AWS":
        from infrastructure.job_storage.aws_dynamodb import AWSDynamoDBJobStorage
        return AWSDynamoDBJobStorage()

    elif provider == "GCP":
        from infrastructure.job_storage.gcp_firestore import GCPFirestoreJobStorage
        return GCPFirestoreJobStorage()

    else:
        raise ValueError(f"Unknown job storage provider: {provider}")


def get_job_queue(provider: str = None) -> JobQueueBase:
    """
    環境設定に基づいてジョブキューを取得

    Args:
        provider: キュープロバイダー（MEMORY/AZURE/AWS/GCP）
                  Noneの場合は環境変数から取得

    Returns:
        JobQueueBase実装
    """
    import os

    if provider is None:
        provider = os.getenv("JOB_QUEUE_PROVIDER", "MEMORY").upper()

    if provider == "MEMORY":
        return InMemoryJobQueue()

    elif provider == "AZURE":
        from infrastructure.job_storage.azure_queue import AzureQueueJobQueue
        return AzureQueueJobQueue()

    elif provider == "AWS":
        from infrastructure.job_storage.aws_sqs import AWSSQSJobQueue
        return AWSSQSJobQueue()

    elif provider == "GCP":
        from infrastructure.job_storage.gcp_tasks import GCPCloudTasksJobQueue
        return GCPCloudTasksJobQueue()

    else:
        raise ValueError(f"Unknown job queue provider: {provider}")
