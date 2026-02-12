"""
================================================================================
async_handlers.py - 非同期APIハンドラー
================================================================================

【概要】
非同期ジョブ処理のためのAPIハンドラーを提供します。
504 Gateway Timeout問題を解決するため、処理を非同期化します。

【設計思想】
Azure Functions/AWS Lambda等のサーバーレス環境では、タイムアウト制限
（通常230秒）があります。複数のテスト項目を評価する場合、この制限を
超える可能性があります。本モジュールは、ジョブを即座に登録して処理を
非同期化することで、クライアント側のタイムアウトを回避します。

【処理フロー】
1. クライアント → submit → ジョブID即時返却
2. バックグラウンドワーカー → 実際の評価処理を実行
3. クライアント → status → 進捗確認（ポーリング）
4. クライアント → results → 完了後に結果取得

【提供するハンドラー】
- handle_submit: ジョブ送信（即座にジョブIDを返却）
- handle_status: ステータス確認（ポーリング用）
- handle_results: 結果取得
- handle_cancel: ジョブキャンセル
- process_pending_jobs: バックグラウンド処理（タイマートリガー用）
- process_job_by_id: 特定ジョブ処理（キュートリガー用）

【APIエンドポイント対応】
- POST /api/evaluate/submit → handle_submit
- GET  /api/evaluate/status/{job_id} → handle_status
- GET  /api/evaluate/results/{job_id} → handle_results
- POST /api/evaluate/cancel/{job_id} → handle_cancel

【環境変数】
- JOB_STORAGE_TYPE: ジョブストレージタイプ（azure_table, memory等）
- AZURE_STORAGE_CONNECTION_STRING: Azure Table Storage接続文字列

【使用例】
```python
# 非同期モードでジョブを送信
response = await handle_submit(items, tenant_id="default")
job_id = response["job_id"]

# ポーリングでステータスを確認
while True:
    status = await handle_status(job_id)
    if status["status"] in ["completed", "failed"]:
        break
    await asyncio.sleep(5)

# 結果を取得
results = await handle_results(job_id)
```

================================================================================
"""

import os
import logging
import time
import traceback
from typing import List, Dict, Any, Optional
from datetime import datetime

from core.async_job_manager import (
    AsyncJobManager,
    JobStorageBase,
    JobQueueBase,
    EvaluationJob,
    JobStatus,
)
from core.handlers import handle_evaluate

logger = logging.getLogger(__name__)


# =============================================================================
# グローバル変数（シングルトン）
# =============================================================================

_job_manager: Optional[AsyncJobManager] = None


def get_job_manager() -> AsyncJobManager:
    """
    ジョブマネージャーのシングルトンインスタンスを取得

    【シングルトンパターン】
    アプリケーション全体で1つのAsyncJobManagerインスタンスを共有します。
    これにより、ストレージ接続の再利用とリソースの効率的な管理が可能です。

    【初期化処理】
    初回呼び出し時に以下を実行:
    1. ジョブストレージ（Azure Table Storage等）の初期化
    2. ジョブキュー（Azure Queue Storage等）の初期化（オプション）
    3. AsyncJobManagerインスタンスの作成

    Returns:
        AsyncJobManager: ジョブ管理のシングルトンインスタンス

    Raises:
        ValueError: ストレージの設定が不正な場合
        ImportError: 必要なパッケージがインストールされていない場合
    """
    global _job_manager

    if _job_manager is None:
        logger.info("[AsyncHandlers] JobManager初期化開始...")
        init_start = time.time()

        try:
            from infrastructure.job_storage import get_job_storage, get_job_queue

            # ストレージを初期化（Azure Table Storage / メモリ等）
            storage = get_job_storage()
            storage_type = type(storage).__name__
            logger.info(f"[AsyncHandlers] ストレージ初期化完了: {storage_type}")

            # キューを初期化（オプション、None可）
            queue = get_job_queue()
            queue_type = type(queue).__name__ if queue else "None"
            logger.debug(f"[AsyncHandlers] キュー初期化完了: {queue_type}")

            # ジョブマネージャーを作成
            _job_manager = AsyncJobManager(storage=storage, queue=queue)

            init_elapsed = time.time() - init_start
            logger.info(
                f"[AsyncHandlers] JobManager初期化完了 "
                f"(ストレージ: {storage_type}, キュー: {queue_type}, "
                f"所要時間: {init_elapsed:.2f}秒)"
            )

        except Exception as e:
            logger.error(
                f"[AsyncHandlers] JobManager初期化エラー: {type(e).__name__}: {e}",
                exc_info=True
            )
            raise

    return _job_manager


def set_job_manager(manager: AsyncJobManager) -> None:
    """
    ジョブマネージャーを設定（テスト用）

    Args:
        manager: 設定するAsyncJobManager
    """
    global _job_manager
    _job_manager = manager


# =============================================================================
# APIハンドラー
# =============================================================================

async def handle_submit(items: List[Dict[str, Any]], tenant_id: str = "default") -> Dict[str, Any]:
    """
    ジョブ送信ハンドラー

    評価ジョブを登録し、即座にジョブIDを返却します。
    実際の処理はバックグラウンドワーカーが実行します。

    Args:
        items: 評価対象項目のリスト
        tenant_id: テナント識別子

    Returns:
        {
            "job_id": "xxx-xxx-xxx",
            "status": "pending",
            "estimated_time": 180,
            "message": "Job submitted successfully"
        }
    """
    logger.info(f"[AsyncHandlers] Submit request: {len(items)} items, tenant: {tenant_id}")

    try:
        manager = get_job_manager()
        response = await manager.submit_job(tenant_id=tenant_id, items=items)

        logger.info(
            f"[AsyncHandlers] Job submitted: {response.job_id}, "
            f"estimated_time: {response.estimated_time}s"
        )

        return response.to_dict()

    except Exception as e:
        logger.error(f"[AsyncHandlers] Submit error: {e}", exc_info=True)
        return {
            "error": True,
            "message": f"Failed to submit job: {str(e)}"
        }


async def handle_status(job_id: str) -> Dict[str, Any]:
    """
    ステータス確認ハンドラー

    ジョブの現在の状態を返却します。
    クライアントはこのエンドポイントをポーリングして完了を待ちます。

    Args:
        job_id: ジョブID

    Returns:
        {
            "job_id": "xxx-xxx-xxx",
            "status": "running",
            "progress": 50,
            "message": "3/6 items processed"
        }
    """
    logger.debug(f"[AsyncHandlers] Status request: {job_id}")

    try:
        manager = get_job_manager()
        response = await manager.get_status(job_id)

        return response.to_dict()

    except Exception as e:
        logger.error(f"[AsyncHandlers] Status error: {e}", exc_info=True)
        return {
            "job_id": job_id,
            "status": "error",
            "progress": 0,
            "message": f"Failed to get status: {str(e)}",
            "error_message": str(e)
        }


async def handle_results(job_id: str) -> Dict[str, Any]:
    """
    結果取得ハンドラー

    完了したジョブの評価結果を返却します。

    Args:
        job_id: ジョブID

    Returns:
        {
            "job_id": "xxx-xxx-xxx",
            "status": "completed",
            "results": [...]
        }
    """
    logger.info(f"[AsyncHandlers] Results request: {job_id}")

    try:
        manager = get_job_manager()
        response = await manager.get_results(job_id)

        result_count = len(response.results) if response.results else 0
        logger.info(f"[AsyncHandlers] Results returned: {result_count} items")

        return response.to_dict()

    except Exception as e:
        logger.error(f"[AsyncHandlers] Results error: {e}", exc_info=True)
        return {
            "job_id": job_id,
            "status": "error",
            "results": [],
            "error": True,
            "message": f"Failed to get results: {str(e)}"
        }


async def handle_cancel(job_id: str) -> Dict[str, Any]:
    """
    ジョブキャンセルハンドラー

    Args:
        job_id: ジョブID

    Returns:
        {
            "job_id": "xxx-xxx-xxx",
            "cancelled": true,
            "message": "Job cancelled successfully"
        }
    """
    logger.info(f"[AsyncHandlers] Cancel request: {job_id}")

    try:
        manager = get_job_manager()
        success = await manager.cancel_job(job_id)

        if success:
            return {
                "job_id": job_id,
                "cancelled": True,
                "message": "Job cancelled successfully"
            }
        else:
            return {
                "job_id": job_id,
                "cancelled": False,
                "message": "Job could not be cancelled (not found or already completed)"
            }

    except Exception as e:
        logger.error(f"[AsyncHandlers] Cancel error: {e}", exc_info=True)
        return {
            "job_id": job_id,
            "cancelled": False,
            "error": True,
            "message": f"Failed to cancel job: {str(e)}"
        }


# =============================================================================
# バックグラウンド処理
# =============================================================================

def _restore_evidence_from_blob(
    items: List[Dict[str, Any]],
    storage: JobStorageBase
) -> List[Dict[str, Any]]:
    """
    Blob Storageから証跡ファイルを復元

    Args:
        items: アイテムリスト
        storage: ジョブストレージ

    Returns:
        証跡ファイルが復元されたアイテムリスト
    """
    # AzureTableJobStorageの場合のみ復元処理を行う
    if hasattr(storage, '_restore_evidence_files'):
        try:
            restored = storage._restore_evidence_files(items)
            logger.info(f"[AsyncHandlers] Restored evidence files from blob storage")
            return restored
        except Exception as e:
            logger.warning(f"[AsyncHandlers] Failed to restore evidence from blob: {e}")
            return items
    return items


async def process_single_job(job: EvaluationJob, storage: JobStorageBase) -> None:
    """
    単一のジョブを処理

    【処理フロー】
    1. ジョブステータスを「実行中」に更新
    2. 証跡ファイルをBlob Storageから復元（64KB制限対策）
    3. 各項目を順次評価（キャンセルチェック付き）
    4. 進捗をリアルタイムで更新
    5. 完了/失敗ステータスを更新

    【エラーハンドリング】
    - 項目単位のエラー: エラー結果として記録し、処理を継続
    - ジョブ全体のエラー: ジョブステータスをFAILEDに更新

    【キャンセル対応】
    各項目処理前にキャンセル状態をチェックし、
    キャンセルされていた場合は処理を中断

    Args:
        job: 処理するEvaluationJobオブジェクト
        storage: ジョブストレージ（進捗更新用）

    Note:
        この関数はバックグラウンドワーカーから呼び出されます。
        直接呼び出さず、process_pending_jobs または process_job_by_id を使用してください。
    """
    job_start_time = time.time()
    logger.info("=" * 60)
    logger.info(f"[AsyncHandlers] ジョブ処理開始: {job.job_id}")
    logger.info(f"[AsyncHandlers] テナント: {job.tenant_id}, 項目数: {len(job.items)}")
    logger.info("=" * 60)

    # ステータスを「実行中」に更新
    job.status = JobStatus.RUNNING
    job.started_at = datetime.utcnow()
    job.message = "Processing started"
    await storage.update_job(job)
    logger.debug(f"[AsyncHandlers] ステータス更新: RUNNING")

    # Blobから証跡ファイルを復元（64KB制限対策）
    # Azure Table Storageは1エンティティ64KB制限があるため、
    # 大きな証跡ファイルはBlob Storageに分離して保存している
    items_to_process = _restore_evidence_from_blob(job.items, storage)
    logger.debug(f"[AsyncHandlers] 証跡ファイル復元完了: {len(items_to_process)}項目")

    try:
        total = len(items_to_process)
        results = []

        for i, item in enumerate(items_to_process):
            item_start_time = time.time()
            item_id = item.get('ID', 'unknown')

            # キャンセルチェック（各項目処理前に確認）
            current_job = await storage.get_job(job.job_id)
            if current_job and current_job.status == JobStatus.CANCELLED:
                logger.warning(f"[AsyncHandlers] ジョブがキャンセルされました: {job.job_id}")
                logger.info(f"[AsyncHandlers] 処理済み: {i}/{total}項目")
                return

            # 項目処理開始
            logger.info("-" * 40)
            logger.info(f"[AsyncHandlers] 項目処理 [{i + 1}/{total}]: ID={item_id}")

            try:
                # 既存のhandle_evaluateを使用して評価を実行
                result = await handle_evaluate([item])
                results.extend(result)

                item_elapsed = time.time() - item_start_time
                eval_result = result[0].get("evaluationResult", False) if result else False
                logger.info(
                    f"[AsyncHandlers] 項目完了: ID={item_id}, "
                    f"結果={'有効' if eval_result else '要確認'}, "
                    f"処理時間={item_elapsed:.1f}秒"
                )

            except Exception as item_error:
                # 項目単位のエラーは結果に含め、処理を継続
                item_elapsed = time.time() - item_start_time
                error_msg = f"{type(item_error).__name__}: {str(item_error)}"

                logger.error(
                    f"[AsyncHandlers] 項目エラー: ID={item_id}, "
                    f"エラー={error_msg}, 処理時間={item_elapsed:.1f}秒"
                )
                logger.debug(f"[AsyncHandlers] トレースバック:\n{traceback.format_exc()}")

                # エラー結果を記録
                results.append({
                    "ID": item_id,
                    "evaluationResult": False,
                    "judgmentBasis": f"評価エラー: {error_msg}",
                    "documentReference": "",
                    "fileName": "",
                    "evidenceFiles": [],
                    "_error": True,
                    "_error_type": type(item_error).__name__
                })

            # 進捗更新（ストレージに保存）
            job.progress = int((i + 1) / total * 100)
            job.message = f"{i + 1}/{total} items processed"
            await storage.update_job(job)

            logger.debug(f"[AsyncHandlers] 進捗更新: {job.progress}%")

        # 全項目処理完了
        job.status = JobStatus.COMPLETED
        job.results = results
        job.completed_at = datetime.utcnow()
        job.message = f"All {total} items processed successfully"
        job.progress = 100

        # 成功/エラー件数を集計
        success_count = sum(1 for r in results if r.get("evaluationResult") and not r.get("_error"))
        error_count = sum(1 for r in results if r.get("_error"))
        job_elapsed = time.time() - job_start_time

        logger.info("=" * 60)
        logger.info(f"[AsyncHandlers] ジョブ完了: {job.job_id}")
        logger.info(f"[AsyncHandlers] 結果: 成功={success_count}, エラー={error_count}, 合計={total}")
        logger.info(f"[AsyncHandlers] 総処理時間: {job_elapsed:.1f}秒")
        logger.info("=" * 60)

    except Exception as e:
        # ジョブ全体のエラー（予期せぬ例外）
        job.status = JobStatus.FAILED
        job.error_message = f"{type(e).__name__}: {str(e)}"
        job.completed_at = datetime.utcnow()
        job.message = "Job failed due to unexpected error"

        job_elapsed = time.time() - job_start_time
        logger.error("=" * 60)
        logger.error(f"[AsyncHandlers] ジョブ失敗: {job.job_id}")
        logger.error(f"[AsyncHandlers] エラー: {type(e).__name__}: {e}")
        logger.error(f"[AsyncHandlers] 処理時間: {job_elapsed:.1f}秒")
        logger.error("=" * 60)
        logger.debug(f"[AsyncHandlers] トレースバック:\n{traceback.format_exc()}")

    # 最終ステータスを保存
    await storage.update_job(job)


async def process_pending_jobs(max_jobs: int = 1) -> int:
    """
    待機中のジョブを処理

    バックグラウンドワーカーから定期的に呼び出されます。

    Args:
        max_jobs: 一度に処理する最大ジョブ数

    Returns:
        処理したジョブ数
    """
    logger.debug(f"[AsyncHandlers] Checking for pending jobs (max: {max_jobs})")

    manager = get_job_manager()
    storage = manager.storage

    # 待機中のジョブを取得
    pending_jobs = await storage.get_pending_jobs(limit=max_jobs)

    if not pending_jobs:
        logger.debug("[AsyncHandlers] No pending jobs found")
        return 0

    logger.info(f"[AsyncHandlers] Found {len(pending_jobs)} pending jobs")

    processed = 0
    for job in pending_jobs:
        await process_single_job(job, storage)
        processed += 1

    logger.info(f"[AsyncHandlers] Processed {processed} jobs")
    return processed


async def process_job_by_id(job_id: str) -> bool:
    """
    指定されたジョブIDを処理

    キュートリガーから呼び出されます。

    Args:
        job_id: 処理するジョブID

    Returns:
        処理成功したらTrue
    """
    logger.info(f"[AsyncHandlers] Processing job by ID: {job_id}")

    manager = get_job_manager()
    storage = manager.storage

    job = await storage.get_job(job_id)

    if not job:
        logger.warning(f"[AsyncHandlers] Job not found: {job_id}")
        return False

    if job.status != JobStatus.PENDING:
        logger.warning(
            f"[AsyncHandlers] Job not pending: {job_id}, "
            f"status: {job.status.value}"
        )
        return False

    await process_single_job(job, storage)
    return True


# =============================================================================
# ユーティリティ
# =============================================================================

def create_json_response(data: Dict[str, Any], status_code: int = 200) -> Dict[str, Any]:
    """
    JSONレスポンスを作成

    Args:
        data: レスポンスデータ
        status_code: HTTPステータスコード

    Returns:
        プラットフォーム共通のレスポンス形式
    """
    import json
    return {
        "body": json.dumps(data, ensure_ascii=False, default=str),
        "content_type": "application/json; charset=utf-8",
        "status_code": status_code
    }


def create_error_response(
    message: str,
    status_code: int = 500,
    details: str = None
) -> Dict[str, Any]:
    """
    エラーレスポンスを作成

    Args:
        message: エラーメッセージ
        status_code: HTTPステータスコード
        details: 詳細情報（トレースバック等）

    Returns:
        プラットフォーム共通のエラーレスポンス形式
        {
            "body": JSON文字列,
            "content_type": "application/json; charset=utf-8",
            "status_code": ステータスコード
        }

    【注意】
    details にトレースバック等を含める場合は、
    本番環境では機密情報が漏洩しないよう注意してください。
    """
    logger.warning(f"[AsyncHandlers] エラーレスポンス生成: {status_code} - {message}")

    error_data = {
        "error": True,
        "message": message,
        "timestamp": datetime.utcnow().isoformat()
    }
    if details:
        error_data["details"] = details

    return create_json_response(error_data, status_code)


# =============================================================================
# モジュール情報
# =============================================================================

__all__ = [
    # APIハンドラー
    "handle_submit",
    "handle_status",
    "handle_results",
    "handle_cancel",
    # バックグラウンド処理
    "process_pending_jobs",
    "process_job_by_id",
    "process_single_job",
    # ユーティリティ
    "create_json_response",
    "create_error_response",
    # ジョブマネージャー
    "get_job_manager",
    "set_job_manager",
]
