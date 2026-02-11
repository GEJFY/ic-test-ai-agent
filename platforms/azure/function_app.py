"""
================================================================================
function_app.py - Azure Functions エントリーポイント
================================================================================

【概要】
内部統制テスト評価AIシステムのAzure Functions用APIエントリポイントです。
Excel VBAマクロからのリクエストを受け付け、AI評価結果を返します。

【エンドポイント】
=== 同期API（asyncMode: false）===
1. POST /api/evaluate - テスト評価実行（同期処理、230秒でタイムアウト）

=== 非同期API（asyncMode: true、推奨）===
2. POST /api/evaluate/submit - ジョブ送信（即座にジョブIDを返却）
3. GET /api/evaluate/status/{job_id} - ステータス確認
4. GET /api/evaluate/results/{job_id} - 結果取得

=== 管理API ===
5. GET /api/health - ヘルスチェック
6. GET /api/config - 設定状態確認

【処理フロー（非同期）】
1. ExcelマクロからJSON形式でリクエストを受信
2. ジョブをTable Storageに登録、Queueに通知
3. 即座にジョブIDを返却
4. バックグラウンドワーカーが処理
5. クライアントがポーリングで完了を確認
6. 結果を取得

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

【必須環境変数】
- LLM_PROVIDER: LLMプロバイダー（AZURE_FOUNDRY, AZURE, GCP, AWS）
- AZURE_FOUNDRY_ENDPOINT / AZURE_OPENAI_ENDPOINT: LLMエンドポイント
- AZURE_FOUNDRY_API_KEY / AZURE_OPENAI_API_KEY: APIキー

【オプション環境変数】
- OCR_PROVIDER: OCRプロバイダー（AZURE, NONE）
- AZURE_DI_ENDPOINT / AZURE_DI_KEY: Document Intelligence
- AZURE_STORAGE_CONNECTION_STRING: 非同期モード用ストレージ

【バージョン】
2.4.0-multiplatform

================================================================================
"""
import sys
import os
import logging
import traceback

# =============================================================================
# パス設定
# =============================================================================
# Azure上: /home/site/wwwroot/src/ にsrc/がコピーされている前提
# ローカル: ../../src/ を参照

_current_dir = os.path.dirname(os.path.abspath(__file__))

# Azure上かローカルかを判定してパスを設定
_azure_src_path = os.path.join(_current_dir, "src")  # Azure上: platforms/azure/src/
_local_src_path = os.path.join(os.path.dirname(os.path.dirname(_current_dir)), "src")  # ローカル: ../../src/

if os.path.exists(_azure_src_path):
    # Azure上（src/がデプロイパッケージに含まれている）
    _src_path = _azure_src_path
else:
    # ローカル開発環境
    _src_path = _local_src_path

# src/ディレクトリをパスに追加
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# プロジェクトルートを設定（.env読み込み用）
_project_root = os.path.dirname(os.path.dirname(_current_dir))

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
# Azure Functions環境ではシンプルなログ設定を使用

# 標準のloggingモジュールを使用（Azure Functionsで安定動作）
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
)
logger = logging.getLogger(__name__)
logger.info("[Azure Functions] 標準loggingで初期化完了")

# Azure Functions アプリケーションを初期化
# 認証はAzure ADによるプラットフォームレベル認証を使用
# AuthLevel.ANONYMOUSに設定し、Azure ADで認可されたユーザーのみアクセス可能
app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


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
    from core.correlation import get_or_create_correlation_id

    logger.info("=" * 60)
    logger.info("[API] /api/evaluate が呼び出されました")

    # 相関ID抽出・設定
    headers = dict(req.headers)
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")

    try:
        # リクエストボディを解析
        items, error = parse_request_body(req.get_body())

        if error:
            logger.error(f"[API] リクエスト解析エラー: {error}")
            resp = create_error_response(error, 400)
            return func.HttpResponse(
                body=resp["body"],
                mimetype=resp["content_type"],
                status_code=resp["status_code"],
                headers={"X-Correlation-ID": correlation_id}
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
            status_code=resp["status_code"],
            headers={"X-Correlation-ID": correlation_id}
        )

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[API] 予期せぬエラー: {e}")
        logger.error(f"[API] トレースバック:\n{error_details}")

        resp = create_error_response(str(e), 500, error_details)
        return func.HttpResponse(
            body=resp["body"],
            mimetype=resp["content_type"],
            status_code=resp["status_code"],
            headers={"X-Correlation-ID": correlation_id}
        )


@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/health - ヘルスチェックエンドポイント

    システムの稼働状態と設定状況を返します。
    """
    from core.handlers import handle_health, create_json_response
    from core.correlation import get_or_create_correlation_id

    logger.info("[API] /api/health が呼び出されました")

    # 相関ID抽出・設定
    headers = dict(req.headers)
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")

    status = handle_health()

    # Azure Functions固有の情報を追加
    status["platform"] = "Azure Functions"

    resp = create_json_response(status)
    return func.HttpResponse(
        body=resp["body"],
        mimetype=resp["content_type"],
        status_code=resp["status_code"],
        headers={"X-Correlation-ID": correlation_id}
    )


@app.route(route="config", methods=["GET"])
def config_status(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/config - 設定状態エンドポイント

    AI機能に必要な設定の状態を詳細に表示します。
    """
    from core.handlers import handle_config, create_json_response
    from core.correlation import get_or_create_correlation_id

    logger.info("[API] /api/config が呼び出されました")

    # 相関ID抽出・設定
    headers = dict(req.headers)
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")

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
        status_code=resp["status_code"],
        headers={"X-Correlation-ID": correlation_id}
    )


# =============================================================================
# 非同期APIエンドポイント（504タイムアウト対策）
# =============================================================================

@app.route(route="evaluate/submit", methods=["POST"])
async def evaluate_submit(req: func.HttpRequest) -> func.HttpResponse:
    """
    POST /api/evaluate/submit - 非同期ジョブ送信エンドポイント

    評価ジョブを登録し、即座にジョブIDを返却します。
    実際の処理はバックグラウンドワーカーが実行します。

    リクエスト形式:
        - Content-Type: application/json; charset=utf-8
        - Body: テスト項目の配列（JSON）

    レスポンス:
        - 202: ジョブ受付完了
            {
                "job_id": "xxx-xxx-xxx",
                "status": "pending",
                "estimated_time": 180,
                "message": "Job submitted successfully"
            }
        - 400: JSONパースエラー
        - 500: 内部エラー
    """
    from core.handlers import parse_request_body, create_json_response, create_error_response
    from core.async_handlers import handle_submit
    from core.correlation import get_or_create_correlation_id

    logger.info("=" * 60)
    logger.info("[API] /api/evaluate/submit が呼び出されました")

    # 相関ID抽出・設定
    headers = dict(req.headers)
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")

    try:
        # リクエストボディを解析
        items, error = parse_request_body(req.get_body())

        if error:
            logger.error(f"[API] リクエスト解析エラー: {error}")
            resp = create_error_response(error, 400)
            return func.HttpResponse(
                body=resp["body"],
                mimetype=resp["content_type"],
                status_code=resp["status_code"],
                headers={"X-Correlation-ID": correlation_id}
            )

        logger.info(f"[API] 受信: {len(items)}件のテスト項目")

        # テナントIDを取得（将来のマルチテナント対応用）
        tenant_id = req.headers.get("X-Tenant-ID", "default")

        # 非同期ハンドラーでジョブを送信
        response = await handle_submit(items=items, tenant_id=tenant_id)

        if response.get("error"):
            logger.error(f"[API] ジョブ送信エラー: {response.get('message')}")
            resp = create_json_response(response)
            return func.HttpResponse(
                body=resp["body"],
                mimetype=resp["content_type"],
                status_code=500,
                headers={"X-Correlation-ID": correlation_id}
            )

        logger.info(f"[API] ジョブ送信完了: {response.get('job_id')}")
        logger.info("=" * 60)

        resp = create_json_response(response)
        return func.HttpResponse(
            body=resp["body"],
            mimetype=resp["content_type"],
            status_code=202,  # Accepted
            headers={"X-Correlation-ID": correlation_id}
        )

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[API] 予期せぬエラー: {e}")
        logger.error(f"[API] トレースバック:\n{error_details}")

        resp = create_error_response(str(e), 500, error_details)
        return func.HttpResponse(
            body=resp["body"],
            mimetype=resp["content_type"],
            status_code=resp["status_code"],
            headers={"X-Correlation-ID": correlation_id}
        )


@app.route(route="evaluate/status/{job_id}", methods=["GET"])
async def evaluate_status(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/evaluate/status/{job_id} - ジョブステータス確認エンドポイント

    ジョブの現在の状態を返却します。
    クライアントはこのエンドポイントをポーリングして完了を待ちます。

    レスポンス:
        - 200: ステータス取得成功
            {
                "job_id": "xxx-xxx-xxx",
                "status": "running" | "completed" | "failed",
                "progress": 50,
                "message": "3/6 items processed"
            }
        - 404: ジョブが見つからない
    """
    from core.handlers import create_json_response, create_error_response
    from core.async_handlers import handle_status
    from core.correlation import get_or_create_correlation_id

    job_id = req.route_params.get("job_id")
    logger.debug(f"[API] /api/evaluate/status/{job_id} が呼び出されました")

    # 相関ID抽出・設定
    headers = dict(req.headers)
    correlation_id = get_or_create_correlation_id(headers)
    logger.debug(f"[Correlation ID] {correlation_id}")

    try:
        response = await handle_status(job_id)

        if response.get("status") == "not_found":
            resp = create_error_response(f"Job not found: {job_id}", 404)
            return func.HttpResponse(
                body=resp["body"],
                mimetype=resp["content_type"],
                status_code=404,
                headers={"X-Correlation-ID": correlation_id}
            )

        resp = create_json_response(response)
        return func.HttpResponse(
            body=resp["body"],
            mimetype=resp["content_type"],
            status_code=200,
            headers={"X-Correlation-ID": correlation_id}
        )

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[API] 予期せぬエラー: {e}")

        resp = create_error_response(str(e), 500, error_details)
        return func.HttpResponse(
            body=resp["body"],
            mimetype=resp["content_type"],
            status_code=resp["status_code"],
            headers={"X-Correlation-ID": correlation_id}
        )


@app.route(route="evaluate/results/{job_id}", methods=["GET"])
async def evaluate_results(req: func.HttpRequest) -> func.HttpResponse:
    """
    GET /api/evaluate/results/{job_id} - ジョブ結果取得エンドポイント

    完了したジョブの評価結果を返却します。

    レスポンス:
        - 200: 結果取得成功
            {
                "job_id": "xxx-xxx-xxx",
                "status": "completed",
                "results": [...]
            }
        - 404: ジョブが見つからない
        - 202: ジョブがまだ完了していない
    """
    from core.handlers import create_json_response, create_error_response
    from core.async_handlers import handle_results
    from core.correlation import get_or_create_correlation_id

    job_id = req.route_params.get("job_id")
    logger.info(f"[API] /api/evaluate/results/{job_id} が呼び出されました")

    # 相関ID抽出・設定
    headers = dict(req.headers)
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")

    try:
        response = await handle_results(job_id)

        if response.get("status") == "not_found":
            resp = create_error_response(f"Job not found: {job_id}", 404)
            return func.HttpResponse(
                body=resp["body"],
                mimetype=resp["content_type"],
                status_code=404,
                headers={"X-Correlation-ID": correlation_id}
            )

        if response.get("status") not in ["completed", "failed"]:
            # まだ完了していない
            resp = create_json_response({
                "job_id": job_id,
                "status": response.get("status"),
                "message": "Job not completed yet. Please check status endpoint."
            })
            return func.HttpResponse(
                body=resp["body"],
                mimetype=resp["content_type"],
                status_code=202,  # Accepted (still processing)
                headers={"X-Correlation-ID": correlation_id}
            )

        logger.info(f"[API] 結果返却: {len(response.get('results', []))}件")

        resp = create_json_response(response)
        return func.HttpResponse(
            body=resp["body"],
            mimetype=resp["content_type"],
            status_code=200,
            headers={"X-Correlation-ID": correlation_id}
        )

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[API] 予期せぬエラー: {e}")

        resp = create_error_response(str(e), 500, error_details)
        return func.HttpResponse(
            body=resp["body"],
            mimetype=resp["content_type"],
            status_code=resp["status_code"],
            headers={"X-Correlation-ID": correlation_id}
        )


# =============================================================================
# キュートリガー（バックグラウンドワーカー）
# =============================================================================

# Queue triggerはAzure Storageが設定されている場合のみ有効
# ローカルテスト時（MEMORY mode）はスキップ
_enable_queue_trigger = os.getenv("AzureWebJobsStorage", "") != ""

if _enable_queue_trigger:
    @app.queue_trigger(
        arg_name="msg",
        queue_name="evaluation-jobs",
        connection="AzureWebJobsStorage"
    )
    async def process_evaluation_job(msg: func.QueueMessage) -> None:
        """
        キュートリガー - バックグラウンドジョブ処理

        Queue Storageにメッセージが追加されると自動的に起動し、
        評価ジョブを処理します。

        メッセージ形式:
            {"job_id": "xxx-xxx-xxx", "action": "process"}
        """
        logger.info("=" * 60)
        logger.info("[Worker] キュートリガー起動")

        try:
            # import文をtryブロック内に移動（インポートエラーをキャッチするため）
            from core.async_handlers import process_job_by_id
            from infrastructure.job_storage.azure_queue import parse_queue_message

            # メッセージからジョブIDを取得
            message_content = msg.get_body().decode('utf-8')
            job_id = parse_queue_message(message_content)

            if not job_id:
                logger.error(f"[Worker] 無効なメッセージ: {message_content}")
                return

            logger.info(f"[Worker] ジョブ処理開始: {job_id}")

            # ジョブを処理
            success = await process_job_by_id(job_id)

            if success:
                logger.info(f"[Worker] ジョブ処理完了: {job_id}")
            else:
                logger.warning(f"[Worker] ジョブ処理スキップ: {job_id}")

        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"[Worker] 予期せぬエラー: {e}")
            logger.error(f"[Worker] トレースバック:\n{error_details}")
            # エラーでもメッセージは削除される（再試行はAzure Functionsの設定に依存）

        logger.info("=" * 60)
else:
    logger.info("[Azure Functions] Queue trigger disabled (AzureWebJobsStorage not configured)")
