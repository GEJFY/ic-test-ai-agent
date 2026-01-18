"""
================================================================================
function_app.py - Azure Functions エントリーポイント
================================================================================

【概要】
内部統制テスト評価AIシステムのAzure Functions用APIエントリポイントです。
Excel VBAマクロからのリクエストを受け付け、AI評価結果を返します。

【エンドポイント】
1. POST /api/evaluate - テスト評価実行
2. GET /api/health - ヘルスチェック
3. GET /api/config - 設定状態確認

【処理フロー】
1. ExcelマクロからJSON形式でリクエストを受信
2. src/core/handlers.py の共通ハンドラーで処理
3. 評価結果をJSON形式で返却

【ディレクトリ構成】
ic-test-ai-agent/
├── src/                  # 共通コード（全プラットフォーム共有）
│   ├── core/             # ビジネスロジック
│   └── infrastructure/   # インフラ抽象化
└── platforms/
    └── azure/            # このファイル

【環境変数の設定方法】
- ローカル開発: プロジェクトルートの .env ファイル
- Azure上: Azure Functions の「アプリケーション設定」

================================================================================
"""
import sys
import os
import logging
import traceback

# =============================================================================
# パス設定 - src/ を Python パスに追加
# =============================================================================

# プロジェクトルートを取得（platforms/azure/ → ic-test-ai-agent/）
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))
_src_path = os.path.join(_project_root, "src")

# src/ をパスに追加
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# =============================================================================
# 環境変数の読み込み（.env ファイルから）
# =============================================================================
# ローカル開発時は .env ファイルから環境変数を読み込む
# Azure上ではアプリケーション設定から自動的に環境変数が設定される
from dotenv import load_dotenv

_env_path = os.path.join(_project_root, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

# =============================================================================
# Azure Functions インポート
# =============================================================================

import azure.functions as func

# =============================================================================
# ログ設定
# =============================================================================
# 新しいログモジュールを使用（ファイル出力、ローテーション対応）

try:
    from infrastructure.logging_config import setup_logging, get_logger
    setup_logging()  # ログ設定を初期化
    logger = get_logger(__name__)
    logger.info("[Azure Functions] ログモジュール初期化完了")
except ImportError:
    # フォールバック：標準のloggingモジュールを使用
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    )
    logger = logging.getLogger(__name__)
    logger.warning("[Azure Functions] logging_configが見つからないため、標準loggingを使用")

# Azure Functions アプリケーションを初期化
app = func.FunctionApp(http_auth_level=func.AuthLevel.FUNCTION)


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
    """
    from core.handlers import handle_evaluate, parse_request_body, create_json_response, create_error_response

    logger.info("=" * 60)
    logger.info("[API] /api/evaluate が呼び出されました")

    try:
        # リクエストボディを解析
        items, error = parse_request_body(req.get_body())

        if error:
            logger.error(f"[API] リクエスト解析エラー: {error}")
            resp = create_error_response(error, 400)
            return func.HttpResponse(
                body=resp["body"],
                mimetype=resp["content_type"],
                status_code=resp["status_code"]
            )

        logger.info(f"[API] 受信: {len(items)}件のテスト項目")

        # 共通ハンドラーで評価を実行
        response = await handle_evaluate(items)

        logger.info(f"[API] レスポンス送信: {len(response)}件")
        logger.info("=" * 60)

        resp = create_json_response(response)
        return func.HttpResponse(
            body=resp["body"],
            mimetype=resp["content_type"],
            status_code=resp["status_code"]
        )

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[API] 予期せぬエラー: {e}")
        logger.error(f"[API] トレースバック:\n{error_details}")

        resp = create_error_response(str(e), 500, error_details)
        return func.HttpResponse(
            body=resp["body"],
            mimetype=resp["content_type"],
            status_code=resp["status_code"]
        )


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/health - ヘルスチェックエンドポイント

    システムの稼働状態と設定状況を返します。
    """
    from core.handlers import handle_health, create_json_response

    logger.info("[API] /api/health が呼び出されました")

    status = handle_health()

    # Azure Functions固有の情報を追加
    status["platform"] = "Azure Functions"

    resp = create_json_response(status)
    return func.HttpResponse(
        body=resp["body"],
        mimetype=resp["content_type"],
        status_code=resp["status_code"]
    )


@app.route(route="config", methods=["GET"])
def config_status(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/config - 設定状態エンドポイント

    AI機能に必要な設定の状態を詳細に表示します。
    """
    from core.handlers import handle_config, create_json_response

    logger.info("[API] /api/config が呼び出されました")

    config = handle_config()

    # Azure Functions固有の情報を追加
    config["platform"] = {
        "name": "Azure Functions",
        "runtime": "python",
        "version": "v2"
    }

    resp = create_json_response(config)
    return func.HttpResponse(
        body=resp["body"],
        mimetype=resp["content_type"],
        status_code=resp["status_code"]
    )
