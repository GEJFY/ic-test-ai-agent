# -*- coding: utf-8 -*-
"""
================================================================================
handlers.py - プラットフォーム非依存のリクエストハンドラー
================================================================================

【概要】
このモジュールは、内部統制テストAIシステムのコア処理を提供します。
Azure Functions、GCP Cloud Functions、AWS Lambda など、
どのクラウドプラットフォームからも呼び出せる共通ハンドラーです。

【設計思想】
- プラットフォーム非依存：クラウド固有のコードをこのモジュールから排除
- エラー耐性：どんなエラーが発生しても適切なレスポンスを返す
- 可観測性：詳細なログを出力し、デバッグを容易にする

【主な関数】
- handle_evaluate(): 内部統制テストの評価を実行
- handle_health(): ヘルスチェック
- handle_config(): 設定状態の確認

【使用例】
```python
# Azure Functions から
from core.handlers import handle_evaluate, handle_health
result = await handle_evaluate(items)

# GCP Cloud Functions から
from core.handlers import handle_evaluate
result = await handle_evaluate(items)

# AWS Lambda から
from core.handlers import handle_evaluate
result = await handle_evaluate(items)
```

【エラーハンドリング】
すべてのハンドラーは、エラーが発生しても必ず有効なレスポンスを返します。
評価エラーの場合でも、IDを含むレスポンスが返されるため、
呼び出し元で結果のマッピングが可能です。

================================================================================
"""

import os
import json
import asyncio
import traceback
import time
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

# =============================================================================
# ログ設定
# =============================================================================
# 新しいログモジュールを使用（ファイル出力、ローテーション対応）

try:
    from infrastructure.logging_config import get_logger, AuditLogger
except ImportError:
    # フォールバック：標準のloggingモジュールを使用
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    )
    def get_logger(name):
        return logging.getLogger(name)

    # AuditLoggerのダミー実装
    class AuditLogger:
        def __init__(self, logger):
            self.logger = logger
        def log_evaluation_start(self, *args, **kwargs):
            pass
        def log_evaluation_end(self, *args, **kwargs):
            pass
        def log_error(self, *args, **kwargs):
            pass

# このモジュール用のロガーを取得
logger = get_logger(__name__)

# 監査専用ロガー（評価処理の詳細記録用）
audit_logger = AuditLogger(logger)

# =============================================================================
# 相関ID・エラーハンドリング
# =============================================================================
# 相関IDとエラーハンドラーをインポート（Phase 1実装）

try:
    from core.correlation import get_correlation_id, get_correlation_id_for_logging
    _use_new_error_handler = True
except ImportError:
    # フォールバック：新しいモジュールが利用できない場合
    logger.warning("相関ID・エラーハンドラーモジュールが見つかりません。基本機能のみ使用します。")
    def get_correlation_id():
        return None
    def get_correlation_id_for_logging():
        return {}
    _use_new_error_handler = False


# =============================================================================
# 定数定義
# =============================================================================

# デフォルトのタイムアウト時間（秒）
DEFAULT_TIMEOUT_SECONDS = 300

# 同時実行する評価処理の最大数
# LLM APIのレート制限に依存。Azure AI Foundryは通常10-20リクエスト/分が安全
MAX_CONCURRENT_EVALUATIONS = 10

# APIバージョン
API_VERSION = "2.4.0-multiplatform"


# =============================================================================
# エラークラス定義
# =============================================================================

class EvaluationError(Exception):
    """
    評価処理で発生したエラーを表すカスタム例外クラス

    【使い方】
    特定の評価項目でエラーが発生した場合に、
    IDや詳細情報を含めてエラーを報告できます。

    【属性】
    - item_id: エラーが発生した評価項目のID
    - message: エラーメッセージ
    - original_error: 元のエラー（あれば）
    """

    def __init__(
        self,
        message: str,
        item_id: str = "unknown",
        original_error: Optional[Exception] = None
    ):
        """
        初期化

        Args:
            message: エラーメッセージ
            item_id: 評価項目ID
            original_error: 元の例外（オプション）
        """
        super().__init__(message)
        self.item_id = item_id
        self.message = message
        self.original_error = original_error

    def __str__(self) -> str:
        """
        文字列表現

        Returns:
            フォーマットされたエラーメッセージ
        """
        return f"[{self.item_id}] {self.message}"


class LLMConfigurationError(Exception):
    """
    LLM設定に関するエラー

    LLMが正しく設定されていない場合に発生します。
    """
    pass


# =============================================================================
# LLM初期化
# =============================================================================

def get_llm_instances() -> Tuple[Any, Any]:
    """
    LLMインスタンスを取得する

    【処理の流れ】
    1. LLMFactoryから設定状態を確認
    2. 設定が完了していれば、テキスト用と画像用のLLMを作成
    3. エラーや未設定の場合は(None, None)を返す

    【環境変数】
    LLMの設定には以下の環境変数が必要です（プロバイダーにより異なる）：
    - AZURE_FOUNDRY_*: Azure AI Foundry用
    - AZURE_OPENAI_*: Azure OpenAI用
    - GCP_VERTEX_*: Google Vertex AI用
    - AWS_BEDROCK_*: AWS Bedrock用

    Returns:
        tuple: (llm, vision_llm)
            - llm: テキスト処理用のChatModel（LangChain）
            - vision_llm: 画像処理用のVision対応ChatModel
            - 未設定の場合は (None, None)

    【エラー時の動作】
    エラーが発生しても例外を投げず、(None, None)を返します。
    これにより、呼び出し元でモック評価にフォールバックできます。
    """
    logger.debug("LLMインスタンスの取得を開始")

    try:
        # LLMファクトリーをインポート
        from infrastructure.llm_factory import LLMFactory

        # 設定状態を確認
        status = LLMFactory.get_config_status()
        logger.debug(f"LLM設定状態: {status}")

        # 設定が不完全な場合
        if not status["configured"]:
            missing = status.get('missing_vars', [])
            logger.warning(
                f"[LLM] 設定が不完全です。不足している環境変数: {missing}"
            )
            logger.info(
                "[LLM] LLMが未設定のため、モック評価モードで動作します"
            )
            return None, None

        # LLMインスタンスを作成
        logger.info(f"[LLM] プロバイダー '{status['provider']}' でLLMを初期化中...")

        # テキスト処理用LLM（temperature=0.0で決定論的な出力）
        llm = LLMFactory.create_chat_model(temperature=0.0)
        logger.debug("[LLM] テキスト処理用LLM: 作成完了")

        # 画像処理用LLM（Vision対応モデル）
        vision_llm = LLMFactory.create_vision_model(temperature=0.0)
        logger.debug("[LLM] 画像処理用LLM: 作成完了")

        logger.info(
            f"[LLM] 初期化完了: プロバイダー = {status['provider']}, "
            f"モデル = {status.get('model', 'default')}"
        )
        return llm, vision_llm

    except ImportError as e:
        # LangChainがインストールされていない場合
        logger.warning(
            f"[LLM] 必要なモジュールがインストールされていません: {e}"
        )
        logger.info(
            "[LLM] pip install langchain langchain-openai でインストールしてください"
        )
        return None, None

    except Exception as e:
        # その他のエラー
        logger.error(
            f"[LLM] 初期化中にエラーが発生しました: {type(e).__name__}: {e}"
        )
        logger.error(f"[LLM] トレースバック:\n{traceback.format_exc()}")
        return None, None


# =============================================================================
# オーケストレーター取得
# =============================================================================

def get_orchestrator(llm: Any, vision_llm: Any) -> Any:
    """
    評価処理を実行するオーケストレーターを取得する

    【オーケストレーターとは】
    複数のAIタスクを順序立てて実行し、最終的な評価結果を生成する
    コンポーネントです。

    GraphAuditOrchestrator:
    - LangGraphベースの実装
    - セルフリフレクション機能を搭載
    - 評価結果の品質が高い

    Args:
        llm: テキスト処理用LLM
        vision_llm: 画像処理用LLM

    Returns:
        GraphAuditOrchestratorインスタンス

    Raises:
        ImportError: オーケストレーターモジュールが見つからない場合
    """
    from core.graph_orchestrator import GraphAuditOrchestrator

    logger.info(
        "[オーケストレーター] LangGraphベースを使用 "
        "(セルフリフレクション: 有効)"
    )
    return GraphAuditOrchestrator(llm=llm, vision_llm=vision_llm)


# =============================================================================
# 評価処理（単一項目）
# =============================================================================

async def evaluate_single_item(
    orchestrator: Any,
    item: Dict[str, Any],
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> Dict[str, Any]:
    """
    単一のテスト項目を評価する

    【処理の流れ】
    1. リクエストデータからAuditContextを作成
    2. オーケストレーターで評価を実行（タイムアウト付き）
    3. 評価結果をレスポンス形式に変換して返す

    【タイムアウト】
    評価処理が指定時間内に完了しない場合、タイムアウトエラーを返します。
    デフォルトは300秒（5分）です。

    Args:
        orchestrator: 評価オーケストレーター
        item: テスト項目データ（ID、統制記述、テスト手続き、証跡ファイル等）
        timeout_seconds: タイムアウト秒数（デフォルト: 300秒）

    Returns:
        dict: 評価結果
            - ID: 評価項目ID
            - evaluationResult: 評価結果（True=有効、False=要確認/無効）
            - judgmentBasis: 判断根拠の説明文
            - documentReference: 参照した文書
            - fileName: 主に参照したファイル名
            - evidenceFiles: 検証した証跡ファイルのリスト
            - _debug: デバッグ情報（オプション）

    【エラー時の動作】
    エラーが発生しても、必ずIDを含むレスポンスを返します。
    これにより、VBA側で結果をマッピングできます。
    """
    # 基本情報を取得
    item_id = item.get("ID", "unknown")
    control_desc = item.get("ControlDescription", "")[:100]  # 最初の100文字
    evidence_files = item.get("EvidenceFiles", [])

    # 開始ログ
    start_time = time.time()
    audit_logger.log_evaluation_start(
        item_id=item_id,
        control_description=control_desc,
        evidence_count=len(evidence_files)
    )

    try:
        # AuditContextを作成（リクエストデータから評価用コンテキストを生成）
        from core.tasks.base_task import AuditContext
        context = AuditContext.from_request(item)
        logger.debug(f"[{item_id}] AuditContext作成完了")

        # 証跡ファイルの情報をログ
        if evidence_files:
            for i, ef in enumerate(evidence_files[:3]):  # 最初の3件のみ
                logger.debug(
                    f"[{item_id}] 証跡{i+1}: {ef.get('fileName', 'N/A')} "
                    f"({len(ef.get('content', ''))} bytes)"
                )
            if len(evidence_files) > 3:
                logger.debug(f"[{item_id}] ... 他 {len(evidence_files) - 3} 件")

        # 評価を実行（タイムアウト付き）
        logger.info(f"[{item_id}] 評価を開始（タイムアウト: {timeout_seconds}秒）")

        result = await asyncio.wait_for(
            orchestrator.evaluate(context),
            timeout=timeout_seconds
        )

        # 完了ログ
        elapsed_time = time.time() - start_time
        evaluation_result = "有効" if result.evaluation_result else "要確認/無効"

        audit_logger.log_evaluation_end(
            item_id=item_id,
            result=evaluation_result,
            elapsed_time=elapsed_time
        )

        logger.info(
            f"[{item_id}] 評価完了: {evaluation_result} "
            f"(処理時間: {elapsed_time:.1f}秒)"
        )

        # レスポンスを返す
        return result.to_response_dict()

    except asyncio.TimeoutError:
        # タイムアウトエラー
        elapsed_time = time.time() - start_time
        logger.warning(
            f"[{item_id}] タイムアウト: {timeout_seconds}秒を超過しました "
            f"(経過時間: {elapsed_time:.1f}秒)"
        )

        audit_logger.log_error(
            item_id=item_id,
            error_type="Timeout",
            error_message=f"{timeout_seconds}秒以内に処理が完了しませんでした"
        )

        return _create_error_result(
            item_id=item_id,
            error_type="timeout",
            message=f"評価タイムアウト: {timeout_seconds}秒以内に処理が完了しませんでした。",
            details={"timeout_seconds": timeout_seconds, "elapsed": elapsed_time}
        )

    except Exception as e:
        # その他のエラー
        elapsed_time = time.time() - start_time
        error_type = type(e).__name__
        error_message = str(e)

        logger.error(
            f"[{item_id}] 評価エラー: {error_type}: {error_message}"
        )
        logger.debug(f"[{item_id}] トレースバック:\n{traceback.format_exc()}")

        audit_logger.log_error(
            item_id=item_id,
            error_type=error_type,
            error_message=error_message,
            context={"control_description": control_desc[:50]}
        )

        return _create_error_result(
            item_id=item_id,
            error_type="evaluation_error",
            message=f"評価エラー: {error_message}",
            details={"error_type": error_type, "elapsed": elapsed_time}
        )


def _create_error_result(
    item_id: str,
    error_type: str,
    message: str,
    details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    エラー時の評価結果を作成する（内部関数）

    Args:
        item_id: 評価項目ID
        error_type: エラーの種類
        message: ユーザー向けメッセージ
        details: デバッグ用詳細情報

    Returns:
        dict: エラー結果（評価結果の形式に準拠）
    """
    # 相関IDを取得（利用可能な場合）
    correlation_id = get_correlation_id() if _use_new_error_handler else None

    result = {
        "ID": item_id,
        "evaluationResult": False,
        "judgmentBasis": message,
        "documentReference": "",
        "fileName": "",
        "evidenceFiles": [],
        "_debug": {
            "error": error_type,
            "timestamp": datetime.now().isoformat()
        }
    }

    # 相関IDを含める
    if correlation_id:
        result["_debug"]["correlation_id"] = correlation_id

    if details:
        result["_debug"].update(details)

    return result


# =============================================================================
# モック評価（テスト用）
# =============================================================================

def mock_evaluate(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    モック評価を実行する（LLM未設定時のテスト用）

    LLMが設定されていない場合に、ダミーの評価結果を返します。
    これにより、API全体の動作確認やVBA連携のテストが可能です。

    Args:
        items: テスト項目のリスト

    Returns:
        List[dict]: モック評価結果のリスト

    【注意】
    この結果は実際の評価ではありません。
    必ずLLMを設定して本番運用してください。
    """
    logger.info(f"[モック評価] {len(items)}件を処理開始")
    logger.warning(
        "[モック評価] LLMが未設定です。実際の評価は行われません。"
    )

    response = []
    for item in items:
        item_id = item.get("ID", "unknown")
        evidence_files = item.get("EvidenceFiles", [])

        # 最初の証跡ファイル名を取得
        first_file_name = ""
        if evidence_files:
            first_file_name = evidence_files[0].get("fileName", "")

        # モック結果を作成
        mock_result = {
            "ID": item_id,
            "evaluationResult": True,  # モックでは常に有効
            "judgmentBasis": (
                f"【モック評価 - 実際の評価ではありません】\n\n"
                f"ID: {item_id}\n"
                f"エビデンスファイル数: {len(evidence_files)}\n\n"
                f"※ LLMが設定されていないため、実際の評価は行われていません。\n"
                f"※ setting.jsonを確認し、LLMプロバイダーを設定してください。"
            ),
            "documentReference": "モック評価（参照文書なし）",
            "fileName": first_file_name,
            "_debug": {"mock": True}
        }

        response.append(mock_result)
        logger.debug(f"[モック評価] {item_id}: 完了")

    logger.info(f"[モック評価] {len(items)}件の処理完了")
    return response


# =============================================================================
# メインハンドラー：評価
# =============================================================================

async def handle_evaluate(
    items: List[Dict[str, Any]],
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
) -> List[Dict[str, Any]]:
    """
    評価リクエストを処理する（プラットフォーム非依存）

    複数のテスト項目を並列で評価し、結果をリストで返します。
    同時実行数は制限されており、サーバーの負荷を抑えます。

    【処理の流れ】
    1. LLMインスタンスを取得
    2. LLM未設定の場合はモック評価を実行
    3. オーケストレーターを作成
    4. 各項目を並列で評価（同時実行数制限あり）
    5. 結果をリストで返す

    Args:
        items: テスト項目のリスト
        timeout_seconds: 各項目のタイムアウト秒数

    Returns:
        List[dict]: 評価結果のリスト（入力と同じ順序）

    【エラーハンドリング】
    - 個別のエラーは各項目のレスポンスに含まれる
    - 全体的なエラーの場合はモック評価にフォールバック
    """
    # 開始ログ
    total_start_time = time.time()
    logger.info("=" * 70)
    logger.info(f"[評価API] リクエスト受信: {len(items)}件")
    logger.info(f"[評価API] タイムアウト設定: {timeout_seconds}秒/項目")
    logger.info("=" * 70)

    # 入力検証
    if not items:
        logger.warning("[評価API] 評価対象が空です")
        return []

    # 項目IDをログ
    item_ids = [item.get("ID", "unknown") for item in items]
    logger.info(f"[評価API] 評価対象ID: {item_ids}")

    # LLMインスタンスを取得
    llm, vision_llm = get_llm_instances()

    # LLM未設定の場合はモック評価
    if llm is None:
        logger.info("[評価API] LLM未設定 → モック評価を実行")
        return mock_evaluate(items)

    try:
        # オーケストレーターを取得
        orchestrator = get_orchestrator(llm, vision_llm)

        # 同時実行数を制限するセマフォ
        # セマフォ: 同時にアクセスできるリソース数を制限する仕組み
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_EVALUATIONS)
        logger.info(f"[評価API] 同時実行数制限: {MAX_CONCURRENT_EVALUATIONS}")

        async def evaluate_with_semaphore(item: Dict[str, Any]) -> Dict[str, Any]:
            """
            セマフォで制限された評価処理

            async withブロック内でセマフォを取得し、
            処理完了後に自動的に解放します。
            """
            async with semaphore:
                item_id = item.get("ID", "unknown")
                logger.debug(f"[{item_id}] セマフォ取得、評価開始")

                result = await evaluate_single_item(
                    orchestrator,
                    item,
                    timeout_seconds
                )

                logger.debug(f"[{item_id}] セマフォ解放")
                return result

        # すべての項目を並列で評価
        logger.info("[評価API] 並列評価を開始...")
        tasks = [evaluate_with_semaphore(item) for item in items]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 例外を含む結果を処理
        processed_results = []
        for i, result in enumerate(results):
            item_id = items[i].get("ID", "unknown")

            if isinstance(result, Exception):
                # gather中に発生した例外を処理
                logger.error(f"[{item_id}] 未処理の例外: {result}")
                processed_results.append(_create_error_result(
                    item_id=item_id,
                    error_type="unhandled_exception",
                    message=f"予期せぬエラー: {str(result)}"
                ))
            else:
                processed_results.append(result)

        # 完了ログ
        total_elapsed = time.time() - total_start_time
        success_count = sum(
            1 for r in processed_results
            if r.get("evaluationResult") and "_debug" not in r
        )

        logger.info("=" * 70)
        logger.info(f"[評価API] 評価完了: {len(processed_results)}件")
        logger.info(f"[評価API] 成功: {success_count}件, 失敗: {len(processed_results) - success_count}件")
        logger.info(f"[評価API] 総処理時間: {total_elapsed:.1f}秒")
        logger.info("=" * 70)

        return processed_results

    except Exception as e:
        # 全体的なエラーの場合
        logger.error(f"[評価API] 評価処理全体でエラー: {type(e).__name__}: {e}")
        logger.debug(f"[評価API] トレースバック:\n{traceback.format_exc()}")

        # モック評価にフォールバック
        logger.info("[評価API] モック評価にフォールバック")
        return mock_evaluate(items)


# =============================================================================
# メインハンドラー：ヘルスチェック
# =============================================================================

def handle_health() -> Dict[str, Any]:
    """
    ヘルスチェックを処理する（プラットフォーム非依存）

    システムの状態と設定を確認し、JSON形式で返します。
    このエンドポイントは、ロードバランサーや監視システムから
    定期的に呼び出されることを想定しています。

    Returns:
        dict: ヘルスチェック結果
            - status: "healthy" または "unhealthy"
            - version: APIバージョン
            - llm: LLM設定状態
            - ocr: OCR設定状態
            - document_processor: 文書処理設定状態
            - features: 有効な機能
            - platform: 実行プラットフォーム名
    """
    logger.info("[API] ヘルスチェック呼び出し")
    start_time = time.time()

    # LLM設定状態を取得
    try:
        from infrastructure.llm_factory import LLMFactory
        llm_status = LLMFactory.get_config_status()
        logger.debug(f"[ヘルス] LLM状態: {llm_status.get('provider', 'N/A')}")
    except ImportError:
        llm_status = {
            "provider": "NOT_AVAILABLE",
            "configured": False,
            "missing_vars": ["LLMFactory module not found"]
        }
        logger.warning("[ヘルス] LLMFactoryモジュールが見つかりません")

    # Document Processor設定状態を取得
    try:
        from core.document_processor import DocumentProcessor
        dp_status = DocumentProcessor.get_config_status()
        logger.debug(f"[ヘルス] DocumentProcessor状態: OCR={dp_status.get('ocr_configured', False)}")
    except ImportError:
        dp_status = {
            "ocr_configured": False,
            "error": "DocumentProcessor module not found"
        }
        logger.warning("[ヘルス] DocumentProcessorモジュールが見つかりません")

    # OCR設定状態を取得
    try:
        from infrastructure.ocr_factory import OCRFactory
        ocr_status = OCRFactory.get_config_status()
        logger.debug(f"[ヘルス] OCR状態: {ocr_status.get('provider', 'N/A')}")
    except ImportError:
        ocr_status = {
            "provider": "NONE",
            "configured": False,
            "missing_vars": ["OCRFactory module not found"]
        }
        logger.warning("[ヘルス] OCRFactoryモジュールが見つかりません")

    # プラットフォームを判定
    platform = _detect_platform()

    # レスポンスを構築
    response = {
        "status": "healthy",
        "version": API_VERSION,
        "llm": llm_status,
        "ocr": ocr_status,
        "document_processor": dp_status,
        "features": {
            "self_reflection": True,
            "multi_cloud_ocr": True,
            "multi_cloud_llm": True,
        },
        "platform": platform
    }

    elapsed = time.time() - start_time
    logger.info(f"[API] ヘルスチェック完了 ({elapsed*1000:.1f}ms)")
    logger.debug(f"[API] ヘルス詳細: {json.dumps(response, ensure_ascii=False)[:200]}...")

    return response


def _detect_platform() -> str:
    """
    実行プラットフォームを検出する（内部関数）

    環境変数から実行環境を判定します。

    Returns:
        str: プラットフォーム名
    """
    if os.environ.get("FUNCTIONS_WORKER_RUNTIME"):
        return "Azure Functions"
    elif os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return "AWS Lambda"
    elif os.environ.get("FUNCTION_TARGET"):
        return "GCP Cloud Functions"
    else:
        return "Local/Unknown"


# =============================================================================
# メインハンドラー：設定状態
# =============================================================================

def handle_config() -> Dict[str, Any]:
    """
    設定状態を取得する（プラットフォーム非依存）

    システムの詳細な設定状態を返します。
    デバッグや設定確認に使用します。

    Returns:
        dict: 設定状態の詳細
            - llm: LLM設定の詳細
            - ocr: OCR設定の詳細
            - orchestrator: オーケストレーター設定
    """
    logger.info("[API] 設定状態確認呼び出し")

    result = {
        "llm": {},
        "ocr": {},
        "orchestrator": {}
    }

    # LLM設定の詳細
    try:
        from infrastructure.llm_factory import LLMFactory
        result["llm"] = {
            "status": LLMFactory.get_config_status(),
            "providers": LLMFactory.get_provider_info()
        }
        logger.debug("[設定] LLM情報取得完了")
    except ImportError as e:
        result["llm"] = {"error": f"モジュールが見つかりません: {str(e)}"}
        logger.warning(f"[設定] LLM情報取得失敗: {e}")

    # OCR設定の詳細
    try:
        from infrastructure.ocr_factory import OCRFactory
        result["ocr"] = {
            "status": OCRFactory.get_config_status(),
            "providers": OCRFactory.get_provider_info()
        }
        logger.debug("[設定] OCR情報取得完了")
    except ImportError as e:
        result["ocr"] = {"error": f"モジュールが見つかりません: {str(e)}"}
        logger.warning(f"[設定] OCR情報取得失敗: {e}")

    # オーケストレーター設定
    result["orchestrator"] = {
        "type": "GraphAuditOrchestrator",
        "self_reflection_enabled": True,
        "max_concurrent_evaluations": MAX_CONCURRENT_EVALUATIONS,
        "default_timeout_seconds": DEFAULT_TIMEOUT_SECONDS
    }
    logger.debug("[設定] オーケストレーター情報設定完了")

    logger.info("[API] 設定状態確認完了")
    return result


# =============================================================================
# ユーティリティ関数
# =============================================================================

def parse_request_body(body: bytes) -> Tuple[Optional[List[Dict[str, Any]]], Optional[str]]:
    """
    リクエストボディをパースする

    HTTPリクエストのボディ（バイト列）をJSONとして解析し、
    テスト項目のリストを取得します。

    Args:
        body: リクエストボディのバイト列

    Returns:
        tuple: (items, error_message)
            - 成功時: (items_list, None)
            - 失敗時: (None, error_message)

    【エラーケース】
    - JSONの構文エラー
    - 配列形式でないデータ
    - UTF-8でエンコードされていない
    """
    logger.debug(f"[パース] リクエストボディを解析中 ({len(body)} bytes)")

    try:
        # UTF-8としてデコード
        body_str = body.decode('utf-8')
        logger.debug(f"[パース] デコード成功 ({len(body_str)} chars)")

        # JSONとしてパース
        data = json.loads(body_str)

        # 配列形式であることを確認
        if not isinstance(data, list):
            error_msg = "リクエストは配列形式である必要があります"
            logger.warning(f"[パース] 形式エラー: {error_msg}")
            return None, error_msg

        logger.info(f"[パース] 成功: {len(data)}件の項目を取得")

        # 各項目のIDをログ
        ids = [item.get("ID", "N/A") for item in data[:5]]
        if len(data) > 5:
            ids.append(f"... 他{len(data) - 5}件")
        logger.debug(f"[パース] 項目ID: {ids}")

        return data, None

    except json.JSONDecodeError as e:
        error_msg = f"JSONパースエラー: {str(e)}"
        logger.error(f"[パース] {error_msg}")
        logger.debug(f"[パース] 問題のボディ先頭100文字: {body[:100]}")
        return None, error_msg

    except UnicodeDecodeError as e:
        error_msg = f"文字エンコーディングエラー: {str(e)}"
        logger.error(f"[パース] {error_msg}")
        return None, error_msg

    except Exception as e:
        error_msg = f"リクエスト解析エラー: {type(e).__name__}: {str(e)}"
        logger.error(f"[パース] {error_msg}")
        return None, error_msg


def create_json_response(
    data: Any,
    status_code: int = 200
) -> Dict[str, Any]:
    """
    JSONレスポンスを作成する

    データをJSON形式に変換し、適切なHTTPレスポンス情報を付与します。

    Args:
        data: レスポンスデータ（dict, list, str など）
        status_code: HTTPステータスコード（デフォルト: 200）

    Returns:
        dict: レスポンス情報
            - body: JSON文字列（UTF-8エンコード済みバイト列）
            - status_code: ステータスコード
            - content_type: Content-Typeヘッダー値
    """
    # JSONに変換（日本語はそのまま保持）
    json_str = json.dumps(data, ensure_ascii=False, indent=None)

    logger.debug(f"[レスポンス] JSONレスポンス作成: {status_code}, {len(json_str)} chars")

    return {
        "body": json_str.encode('utf-8'),
        "status_code": status_code,
        "content_type": "application/json; charset=utf-8"
    }


def create_error_response(
    message: str,
    status_code: int = 500,
    error_traceback: Optional[str] = None
) -> Dict[str, Any]:
    """
    エラーレスポンスを作成する

    エラー情報を含むJSONレスポンスを生成します。

    Args:
        message: エラーメッセージ
        status_code: HTTPステータスコード（デフォルト: 500）
        error_traceback: トレースバック文字列（オプション）

    Returns:
        dict: エラーレスポンス情報

    【注意】
    error_tracebackは開発環境でのみ含めることを推奨します。
    本番環境では詳細なエラー情報を公開しないでください。
    """
    logger.error(f"[レスポンス] エラーレスポンス作成: {status_code} - {message}")

    # 相関IDを取得
    correlation_id = get_correlation_id() if _use_new_error_handler else None

    error_data = {
        "error": True,
        "message": message,
        "timestamp": datetime.now().isoformat()
    }

    # 相関IDを含める
    if correlation_id:
        error_data["correlation_id"] = correlation_id

    # トレースバックは開発環境でのみ含める
    if error_traceback and os.environ.get("DEBUG", "").lower() == "true":
        error_data["traceback"] = error_traceback
        logger.debug(f"[レスポンス] トレースバック含む")

    return create_json_response(error_data, status_code)


# =============================================================================
# モジュール情報
# =============================================================================

__all__ = [
    # メインハンドラー
    "handle_evaluate",
    "handle_health",
    "handle_config",
    # ユーティリティ
    "parse_request_body",
    "create_json_response",
    "create_error_response",
    # 例外クラス
    "EvaluationError",
    "LLMConfigurationError",
    # 定数
    "API_VERSION",
    "DEFAULT_TIMEOUT_SECONDS",
]
