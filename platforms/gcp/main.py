"""
================================================================================
main.py - GCP Cloud Functions エントリーポイント
================================================================================

【概要】
内部統制テスト評価AIシステムのGCP Cloud Functions用APIエントリポイントです。
Excel VBAマクロからのリクエストを受け付け、AI評価結果を返します。

【エンドポイント】
=== 同期API（asyncMode: false）===
1. POST /evaluate - テスト評価実行（同期処理）

=== 非同期API（asyncMode: true、推奨）===
2. POST /evaluate/submit - ジョブ送信（即座にジョブIDを返却）
3. GET /evaluate/status/{job_id} - ステータス確認
4. GET /evaluate/results/{job_id} - 結果取得

=== 管理API ===
5. GET /health - ヘルスチェック
6. GET /config - 設定状態確認

【ディレクトリ構成】
ic-test-ai-agent/
├── src/                  # 共通コード（全プラットフォーム共有）
│   ├── core/             # ビジネスロジック
│   └── infrastructure/   # インフラ抽象化
└── platforms/
    └── gcp/              # このファイル

【デプロイ方法】
```bash
# 1. このディレクトリに移動
cd platforms/gcp

# 2. src/ ディレクトリをコピー（デプロイ用）
cp -r ../../src .

# 3. Cloud Functionsにデプロイ
gcloud functions deploy evaluate \\
  --runtime python311 \\
  --trigger-http \\
  --allow-unauthenticated \\
  --entry-point evaluate \\
  --timeout 540 \\
  --memory 1024MB \\
  --set-env-vars "LLM_PROVIDER=GCP,GCP_PROJECT_ID=your-project"

# 4. 他のエンドポイントも同様にデプロイ
gcloud functions deploy health --entry-point health ...
gcloud functions deploy config --entry-point config_status ...
```

【環境変数の設定方法】
- ローカル開発: プロジェクトルートの .env ファイル
- GCP上: --set-env-vars オプションまたは Secret Manager

================================================================================
"""
import sys
import os
import json
import logging
import asyncio
import traceback

# =============================================================================
# パス設定 - src/ を Python パスに追加
# =============================================================================

_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(os.path.dirname(_current_dir))

# デプロイ時: platforms/gcp/src/ がコピーされている場合
_local_src = os.path.join(_current_dir, "src")
if os.path.exists(_local_src):
    if _local_src not in sys.path:
        sys.path.insert(0, _local_src)
else:
    # 開発時: プロジェクトルートの src/ を参照
    _src_path = os.path.join(_project_root, "src")
    if _src_path not in sys.path:
        sys.path.insert(0, _src_path)

# =============================================================================
# 環境変数の読み込み（.env ファイルから）
# =============================================================================
# ローカル開発時は .env ファイルから環境変数を読み込む
# GCP上では --set-env-vars で設定された環境変数が使用される
from dotenv import load_dotenv

_env_path = os.path.join(_project_root, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

# =============================================================================
# GCP Cloud Functions インポート
# =============================================================================

import functions_framework
from flask import Request, make_response

# =============================================================================
# ログ設定
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# ヘルパー関数
# =============================================================================

def run_async(coro):
    """非同期関数を同期的に実行"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def create_response(data, status_code=200, extra_headers=None):
    """JSONレスポンスを作成"""
    response = make_response(
        json.dumps(data, ensure_ascii=False),
        status_code
    )
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    if extra_headers:
        for key, value in extra_headers.items():
            response.headers[key] = value
    return response


def create_error_response(message, status_code=500, tb=None, extra_headers=None):
    """エラーレスポンスを作成"""
    error_data = {"error": True, "message": message}
    if tb:
        error_data["traceback"] = tb
    return create_response(error_data, status_code, extra_headers)


# =============================================================================
# Cloud Functions エントリポイント
# =============================================================================

@functions_framework.http
def evaluate(request: Request):
    """
    POST /evaluate - テスト評価エンドポイント

    内部統制テスト項目をAIで評価し、結果を返します。
    """
    from core.handlers import handle_evaluate, parse_request_body
    from core.correlation import get_or_create_correlation_id

    logger.info("=" * 60)
    logger.info("[GCP] /evaluate が呼び出されました")

    # 相関ID抽出・設定
    headers = dict(request.headers)
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")
    correlation_headers = {"X-Correlation-ID": correlation_id}

    # POSTメソッドのみ許可
    if request.method != 'POST':
        return create_error_response("Method not allowed", 405, extra_headers=correlation_headers)

    try:
        # リクエストボディを解析
        items, error = parse_request_body(request.get_data())

        if error:
            logger.error(f"[GCP] リクエスト解析エラー: {error}")
            return create_error_response(error, 400, extra_headers=correlation_headers)

        logger.info(f"[GCP] 受信: {len(items)}件のテスト項目")

        # 共通ハンドラーで評価を実行（非同期を同期的に実行）
        response = run_async(handle_evaluate(items))

        logger.info(f"[GCP] レスポンス送信: {len(response)}件")
        logger.info("=" * 60)

        return create_response(response, extra_headers=correlation_headers)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[GCP] 予期せぬエラー: {e}")
        logger.error(f"[GCP] トレースバック:\n{error_details}")
        return create_error_response(str(e), 500, error_details, extra_headers=correlation_headers)


@functions_framework.http
def health(request: Request):
    """
    GET /health - ヘルスチェックエンドポイント

    システムの稼働状態と設定状況を返します。
    """
    from core.handlers import handle_health
    from core.correlation import get_or_create_correlation_id

    logger.info("[GCP] /health が呼び出されました")

    # 相関ID抽出・設定
    headers = dict(request.headers)
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")

    status = handle_health()
    status["platform"] = "GCP Cloud Functions"

    return create_response(status, extra_headers={"X-Correlation-ID": correlation_id})


@functions_framework.http
def config_status(request: Request):
    """
    GET /config - 設定状態エンドポイント

    AI機能に必要な設定の状態を詳細に表示します。
    """
    from core.handlers import handle_config
    from core.correlation import get_or_create_correlation_id

    logger.info("[GCP] /config が呼び出されました")

    # 相関ID抽出・設定
    headers = dict(request.headers)
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")

    config = handle_config()
    config["platform"] = {
        "name": "GCP Cloud Functions",
        "runtime": "python311",
        "framework": "functions-framework"
    }

    return create_response(config, extra_headers={"X-Correlation-ID": correlation_id})


# =============================================================================
# 非同期APIエンドポイント（504タイムアウト対策）
# =============================================================================

@functions_framework.http
def evaluate_submit(request: Request):
    """
    POST /evaluate/submit - 非同期ジョブ送信エンドポイント

    評価ジョブを登録し、即座にジョブIDを返却します。
    """
    from core.handlers import parse_request_body
    from core.async_handlers import handle_submit
    from core.correlation import get_or_create_correlation_id

    logger.info("=" * 60)
    logger.info("[GCP] /evaluate/submit が呼び出されました")

    # 相関ID抽出・設定
    headers = dict(request.headers)
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")
    correlation_headers = {"X-Correlation-ID": correlation_id}

    if request.method != 'POST':
        return create_error_response("Method not allowed", 405, extra_headers=correlation_headers)

    try:
        items, error = parse_request_body(request.get_data())

        if error:
            logger.error(f"[GCP] リクエスト解析エラー: {error}")
            return create_error_response(error, 400, extra_headers=correlation_headers)

        logger.info(f"[GCP] 受信: {len(items)}件のテスト項目")

        tenant_id = request.headers.get("X-Tenant-ID", "default")
        response = run_async(handle_submit(items=items, tenant_id=tenant_id))

        if response.get("error"):
            logger.error(f"[GCP] ジョブ送信エラー: {response.get('message')}")
            return create_response(response, 500, extra_headers=correlation_headers)

        logger.info(f"[GCP] ジョブ送信完了: {response.get('job_id')}")
        return create_response(response, 202, extra_headers=correlation_headers)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[GCP] 予期せぬエラー: {e}")
        return create_error_response(str(e), 500, error_details, extra_headers=correlation_headers)


@functions_framework.http
def evaluate_status(request: Request):
    """
    GET /evaluate/status/{job_id} - ジョブステータス確認エンドポイント
    """
    from core.async_handlers import handle_status
    from core.correlation import get_or_create_correlation_id

    # 相関ID抽出・設定
    headers = dict(request.headers)
    correlation_id = get_or_create_correlation_id(headers)
    correlation_headers = {"X-Correlation-ID": correlation_id}

    # パスからjob_idを抽出
    path = request.path
    job_id = path.split("/")[-1] if "/status/" in path else request.args.get("job_id")

    if not job_id:
        return create_error_response("job_id is required", 400, extra_headers=correlation_headers)

    logger.debug(f"[GCP] /evaluate/status/{job_id} が呼び出されました")
    logger.debug(f"[Correlation ID] {correlation_id}")

    try:
        response = run_async(handle_status(job_id))

        if response.get("status") == "not_found":
            return create_error_response(f"Job not found: {job_id}", 404, extra_headers=correlation_headers)

        return create_response(response, extra_headers=correlation_headers)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[GCP] 予期せぬエラー: {e}")
        return create_error_response(str(e), 500, error_details, extra_headers=correlation_headers)


@functions_framework.http
def evaluate_results(request: Request):
    """
    GET /evaluate/results/{job_id} - ジョブ結果取得エンドポイント
    """
    from core.async_handlers import handle_results
    from core.correlation import get_or_create_correlation_id

    # 相関ID抽出・設定
    headers = dict(request.headers)
    correlation_id = get_or_create_correlation_id(headers)
    correlation_headers = {"X-Correlation-ID": correlation_id}

    # パスからjob_idを抽出
    path = request.path
    job_id = path.split("/")[-1] if "/results/" in path else request.args.get("job_id")

    if not job_id:
        return create_error_response("job_id is required", 400, extra_headers=correlation_headers)

    logger.info(f"[GCP] /evaluate/results/{job_id} が呼び出されました")
    logger.info(f"[Correlation ID] {correlation_id}")

    try:
        response = run_async(handle_results(job_id))

        if response.get("status") == "not_found":
            return create_error_response(f"Job not found: {job_id}", 404, extra_headers=correlation_headers)

        if response.get("status") not in ["completed", "failed"]:
            return create_response({
                "job_id": job_id,
                "status": response.get("status"),
                "message": "Job not completed yet. Please check status endpoint."
            }, 202, extra_headers=correlation_headers)

        logger.info(f"[GCP] 結果返却: {len(response.get('results', []))}件")
        return create_response(response, extra_headers=correlation_headers)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[GCP] 予期せぬエラー: {e}")
        return create_error_response(str(e), 500, error_details, extra_headers=correlation_headers)


# =============================================================================
# ローカルテスト用
# =============================================================================

if __name__ == "__main__":
    # ローカルテスト用: Flask開発サーバーで起動
    from flask import Flask
    app = Flask(__name__)

    @app.route('/evaluate', methods=['POST'])
    def local_evaluate():
        from flask import request
        return evaluate(request)

    @app.route('/evaluate/submit', methods=['POST'])
    def local_evaluate_submit():
        from flask import request
        return evaluate_submit(request)

    @app.route('/evaluate/status/<job_id>', methods=['GET'])
    def local_evaluate_status(job_id):
        from flask import request
        return evaluate_status(request)

    @app.route('/evaluate/results/<job_id>', methods=['GET'])
    def local_evaluate_results(job_id):
        from flask import request
        return evaluate_results(request)

    @app.route('/health', methods=['GET'])
    def local_health():
        from flask import request
        return health(request)

    @app.route('/config', methods=['GET'])
    def local_config():
        from flask import request
        return config_status(request)

    print("GCP Cloud Functions ローカルサーバー起動: http://localhost:8080")
    app.run(host='0.0.0.0', port=8080, debug=True)
