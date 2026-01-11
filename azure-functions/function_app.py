"""
================================================================================
function_app.py - Azure Functions メインエントリポイント
================================================================================

【概要】
内部統制テスト評価AIシステムのAPIエントリポイントです。
Excel VBAマクロからのリクエストを受け付け、AI評価結果を返します。

【エンドポイント】
1. POST /api/evaluate - テスト評価実行
2. GET /api/health - ヘルスチェック
3. GET /api/config - 設定状態確認

【処理フロー】
1. ExcelマクロからJSON形式でリクエストを受信
2. LLMインスタンスを初期化
3. AuditOrchestratorで各テスト項目を評価
4. 評価結果をJSON形式で返却

【リクエスト形式】
```json
[
    {
        "ID": "CLC-01",
        "ControlDescription": "統制記述...",
        "TestProcedure": "テスト手続き...",
        "EvidenceLink": "C:/path/to/evidence",
        "EvidenceFiles": [
            {"fileName": "doc.pdf", "extension": ".pdf",
             "mimeType": "application/pdf", "base64": "..."}
        ]
    }
]
```

【レスポンス形式】
```json
[
    {
        "ID": "CLC-01",
        "evaluationResult": true,
        "judgmentBasis": "判断根拠...",
        "documentReference": "参照文書...",
        "fileName": "doc.pdf",
        "_debug": {...}
    }
]
```

【環境変数】
- LLM_PROVIDER: LLMプロバイダー（AZURE/OPENAI/GCP/AWS）
- AZURE_OPENAI_API_KEY, AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_DEPLOYMENT_NAME
- AZURE_DI_ENDPOINT, AZURE_DI_KEY（Document Intelligence用）

================================================================================
"""
import os
import json
import logging
import asyncio
from typing import List

import azure.functions as func

# =============================================================================
# ログ設定
# =============================================================================

# ログフォーマットを設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Azure Functions アプリケーションを初期化
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


# =============================================================================
# LLM初期化
# =============================================================================

def get_llm_instances():
    """
    LLMインスタンスを取得

    環境変数の設定に基づいてLLMを初期化します。
    設定がない場合はNoneを返します（モック評価にフォールバック）。

    Returns:
        tuple: (llm, vision_llm)
            - llm: テキスト処理用のChatModel
            - vision_llm: 画像処理用のVision対応ChatModel
            - 未設定の場合は (None, None)

    Note:
        - LLM_PROVIDER環境変数でプロバイダーを選択
        - 対応プロバイダー: AZURE, OPENAI, GCP, AWS
    """
    try:
        from infrastructure.llm_factory import LLMFactory, LLMConfigError

        # LLM設定状態を確認
        status = LLMFactory.get_config_status()

        if not status["configured"]:
            logger.warning(
                f"[LLM] 未設定: 不足している環境変数 = {status['missing_vars']}"
            )
            return None, None

        # LLMインスタンスを作成
        llm = LLMFactory.create_chat_model(temperature=0.0)
        vision_llm = LLMFactory.create_vision_model(temperature=0.0)

        logger.info(f"[LLM] 初期化完了: プロバイダー = {status['provider']}")
        return llm, vision_llm

    except ImportError as e:
        logger.warning(f"[LLM] LangChainが利用できません: {e}")
        return None, None

    except Exception as e:
        logger.error(f"[LLM] 初期化エラー: {e}")
        return None, None


# =============================================================================
# 評価処理
# =============================================================================

async def evaluate_single_item(orchestrator, item: dict, timeout_seconds: int = 60) -> dict:
    """
    単一のテスト項目を評価

    タイムアウト付きで1件のテスト項目を評価します。
    タイムアウトまたはエラー時はエラー情報を含む結果を返します。

    Args:
        orchestrator (AuditOrchestrator): 評価オーケストレーター
        item (dict): テスト項目データ
        timeout_seconds (int): タイムアウト秒数（デフォルト: 60秒）

    Returns:
        dict: 評価結果
            - ID: テスト項目ID
            - evaluationResult: 評価結果（True/False）
            - judgmentBasis: 判断根拠
            - documentReference: 参照文書
            - fileName: 証跡ファイル名
            - _debug: デバッグ情報
    """
    from core.tasks.base_task import AuditContext

    item_id = item.get("ID", "unknown")
    logger.info(f"[評価] 開始: {item_id}")

    try:
        # コンテキストを作成
        context = AuditContext.from_request(item)

        # タイムアウト付きで評価を実行
        result = await asyncio.wait_for(
            orchestrator.evaluate(context),
            timeout=timeout_seconds
        )

        logger.info(f"[評価] 完了: {item_id} "
                   f"(結果: {'有効' if result.evaluation_result else '要確認'})")

        return result.to_response_dict()

    except asyncio.TimeoutError:
        logger.warning(f"[評価] タイムアウト: {item_id} ({timeout_seconds}秒超過)")
        return {
            "ID": item_id,
            "evaluationResult": False,
            "judgmentBasis": f"評価タイムアウト: {timeout_seconds}秒以内に処理が完了しませんでした。"
                            "証跡ファイルのサイズが大きい場合は分割をご検討ください。",
            "documentReference": "",
            "fileName": "",
            "_debug": {
                "error": "timeout",
                "timeout_seconds": timeout_seconds
            }
        }

    except Exception as e:
        logger.error(f"[評価] エラー: {item_id} - {e}")
        return {
            "ID": item_id,
            "evaluationResult": False,
            "judgmentBasis": f"評価エラー: {str(e)}",
            "documentReference": "",
            "fileName": "",
            "_debug": {"error": str(e)}
        }


async def evaluate_with_ai(items: List[dict]) -> List[dict]:
    """
    AI評価を実行

    複数のテスト項目を並行処理で評価します。
    LLMが設定されていない場合はモック評価にフォールバックします。

    Args:
        items (List[dict]): テスト項目のリスト

    Returns:
        List[dict]: 評価結果のリスト

    Note:
        - 同時実行数は3に制限（LLM API負荷軽減のため）
        - 各項目のタイムアウトは180秒
    """
    logger.info(f"=== AI評価開始: {len(items)}件 ===")

    # LLMインスタンスを取得
    llm, vision_llm = get_llm_instances()

    if llm is None:
        logger.info("[評価] LLM未設定のため、モック評価を実行します")
        return mock_evaluate(items)

    try:
        from core.auditor_agent import AuditOrchestrator

        # オーケストレーターを作成
        orchestrator = AuditOrchestrator(llm=llm, vision_llm=vision_llm)
        logger.debug("[評価] AuditOrchestratorを初期化しました")

        # 同時実行数を制限するセマフォ
        # LLM APIへの負荷を軽減するため、最大3件まで同時処理
        semaphore = asyncio.Semaphore(3)

        async def evaluate_with_semaphore(item):
            """セマフォで同時実行数を制限"""
            async with semaphore:
                return await evaluate_single_item(
                    orchestrator, item,
                    timeout_seconds=180  # 3分
                )

        # 並行処理で評価を実行
        logger.info(f"[評価] 並行処理開始: {len(items)}件")
        tasks = [evaluate_with_semaphore(item) for item in items]
        results = await asyncio.gather(*tasks)

        logger.info(f"=== AI評価完了: {len(results)}件 ===")
        return list(results)

    except Exception as e:
        logger.error(f"[評価] AI評価失敗: {e}")
        logger.info("[評価] モック評価にフォールバック")
        return mock_evaluate(items)


def mock_evaluate(items: List[dict]) -> List[dict]:
    """
    モック評価（テスト用）

    LLMが設定されていない場合のダミー評価です。
    開発・テスト時に使用します。

    Args:
        items (List[dict]): テスト項目のリスト

    Returns:
        List[dict]: モック評価結果のリスト

    Note:
        全ての項目を「有効」と判定します。
    """
    logger.info(f"[モック評価] {len(items)}件を処理")

    response = []
    for item in items:
        item_id = item.get("ID", "unknown")
        evidence_files = item.get("EvidenceFiles", [])

        # 最初の証跡ファイル名を取得
        first_file_name = ""
        if evidence_files and len(evidence_files) > 0:
            first_file_name = evidence_files[0].get("fileName", "")

        response.append({
            "ID": item_id,
            "evaluationResult": True,
            "judgmentBasis": (
                f"【モック評価】\n"
                f"ID: {item_id}\n"
                f"エビデンスファイル数: {len(evidence_files)}\n"
                f"※ LLMが設定されていないため、実際の評価は行われていません。"
            ),
            "documentReference": "内部統制規程（モック）",
            "fileName": first_file_name
        })

    return response


# =============================================================================
# APIエンドポイント
# =============================================================================

@app.route(route="evaluate", methods=["POST"])
async def evaluate(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/evaluate - テスト評価エンドポイント

    内部統制テスト項目をAIで評価し、結果を返します。

    リクエスト形式:
        - Content-Type: application/json; charset=utf-8
        - Body: テスト項目の配列（JSON）

    レスポンス:
        - 200: 評価成功（結果配列）
        - 400: JSONパースエラー
        - 500: 内部エラー

    Example:
        >>> curl -X POST /api/evaluate \\
        ...   -H "Content-Type: application/json" \\
        ...   -H "x-functions-key: YOUR_KEY" \\
        ...   -d '[{"ID": "CLC-01", ...}]'
    """
    logger.info("=" * 60)
    logger.info("[API] /api/evaluate が呼び出されました")

    try:
        # --------------------------------------------------
        # リクエストボディを解析
        # --------------------------------------------------
        req_body = req.get_json()

        if not isinstance(req_body, list):
            logger.error("[API] リクエストが配列形式ではありません")
            raise ValueError("リクエストは配列形式である必要があります")

        logger.info(f"[API] 受信: {len(req_body)}件のテスト項目")

        # --------------------------------------------------
        # AI評価を実行
        # --------------------------------------------------
        response = await evaluate_with_ai(req_body)

        # --------------------------------------------------
        # レスポンスを返却
        # --------------------------------------------------
        response_json = json.dumps(response, ensure_ascii=False)

        logger.info(f"[API] レスポンス送信: {len(response)}件")
        logger.info("=" * 60)

        return func.HttpResponse(
            body=response_json.encode('utf-8'),
            mimetype="application/json; charset=utf-8",
            status_code=200
        )

    except ValueError as e:
        logger.error(f"[API] JSONパースエラー: {e}")
        error_response = json.dumps({
            "error": True,
            "message": "Invalid JSON format"
        }, ensure_ascii=False)
        return func.HttpResponse(
            body=error_response.encode('utf-8'),
            mimetype="application/json; charset=utf-8",
            status_code=400
        )

    except Exception as e:
        import traceback
        error_details = traceback.format_exc()

        logger.error(f"[API] 予期せぬエラー: {e}")
        logger.error(f"[API] トレースバック:\n{error_details}")

        error_response = json.dumps({
            "error": True,
            "message": str(e),
            "traceback": error_details
        }, ensure_ascii=False)

        return func.HttpResponse(
            body=error_response.encode('utf-8'),
            mimetype="application/json; charset=utf-8",
            status_code=500
        )


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/health - ヘルスチェックエンドポイント

    システムの稼働状態と設定状況を返します。

    レスポンス:
        - status: "healthy"
        - version: APIバージョン
        - llm: LLM設定状態
        - document_intelligence: Document Intelligence設定状態
        - features: 利用可能な機能一覧

    Example:
        >>> curl /api/health
        {"status": "healthy", "version": "2.1.0-ai", ...}
    """
    logger.info("[API] /api/health が呼び出されました")

    # LLM設定状態を取得
    try:
        from infrastructure.llm_factory import LLMFactory
        llm_status = LLMFactory.get_config_status()
    except ImportError:
        llm_status = {
            "provider": "NOT_AVAILABLE",
            "configured": False
        }

    # Document Intelligence設定状態を取得
    try:
        from core.document_processor import DocumentProcessor
        di_status = DocumentProcessor.get_config_status()
    except ImportError:
        di_status = {
            "document_intelligence_configured": False
        }

    # ステータス情報を構築
    status = {
        "status": "healthy",
        "version": "2.1.0-ai",
        "llm": llm_status,
        "document_intelligence": di_status,
        "features": {
            "a1_semantic_search": True,
            "a2_image_recognition": True,
            "a3_data_extraction": True,
            "a4_stepwise_reasoning": True,
            "a5_semantic_reasoning": True,
            "a6_multi_document": True,
            "a7_pattern_analysis": True,
            "a8_sod_detection": True,
            "pdf_coordinate_extraction": di_status.get(
                "document_intelligence_configured", False
            ),
        }
    }

    response_json = json.dumps(status, ensure_ascii=False)
    return func.HttpResponse(
        body=response_json.encode('utf-8'),
        mimetype="application/json; charset=utf-8",
        status_code=200
    )


@app.route(route="config", methods=["GET"])
def config_status(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/config - 設定状態エンドポイント

    AI機能に必要な設定の状態を詳細に表示します。
    トラブルシューティング時に使用します。

    レスポンス:
        - current_status: 現在の設定状態
        - supported_providers: 対応プロバイダー情報

    Example:
        >>> curl /api/config
        {"current_status": {...}, "supported_providers": {...}}
    """
    logger.info("[API] /api/config が呼び出されました")

    try:
        from infrastructure.llm_factory import LLMFactory

        current_status = LLMFactory.get_config_status()
        provider_info = LLMFactory.get_provider_info()

        config_guide = {
            "current_status": current_status,
            "supported_providers": provider_info
        }

        response_json = json.dumps(config_guide, ensure_ascii=False, indent=2)
        return func.HttpResponse(
            body=response_json.encode('utf-8'),
            mimetype="application/json; charset=utf-8",
            status_code=200
        )

    except ImportError:
        error = {
            "error": True,
            "message": (
                "LangChain依存パッケージがインストールされていません。\n"
                "以下を実行してください:\n"
                "pip install langchain langchain-openai "
                "langchain-google-vertexai langchain-aws"
            )
        }
        return func.HttpResponse(
            body=json.dumps(error, ensure_ascii=False).encode('utf-8'),
            mimetype="application/json; charset=utf-8",
            status_code=500
        )
