"""
================================================================================
lambda_handler.py - AWS Lambda エントリーポイント
================================================================================

【概要】
内部統制テスト評価AIシステムのAWS Lambda用APIエントリポイントです。
API Gateway経由でExcel VBAマクロからのリクエストを受け付け、AI評価結果を返します。

【エンドポイント】（API Gateway設定）
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
    └── aws/              # このファイル

【デプロイ方法】
```bash
# 1. Lambda用パッケージを作成
cd platforms/aws
mkdir -p package
pip install -r requirements.txt -t package/
cp -r ../../src/* package/
cp lambda_handler.py package/

# 2. ZIPファイルを作成
cd package && zip -r ../deployment.zip . && cd ..

# 3. Lambda関数を作成
aws lambda create-function \\
  --function-name ic-test-evaluate \\
  --runtime python3.11 \\
  --handler lambda_handler.handler \\
  --zip-file fileb://deployment.zip \\
  --role arn:aws:iam::ACCOUNT_ID:role/lambda-role \\
  --timeout 300 \\
  --memory-size 1024 \\
  --environment Variables='{
    "LLM_PROVIDER":"AWS",
    "AWS_REGION":"ap-northeast-1",
    "OCR_PROVIDER":"AWS"
  }'

# 4. 更新（2回目以降）
aws lambda update-function-code \\
  --function-name ic-test-evaluate \\
  --zip-file fileb://deployment.zip

# 5. API Gatewayを設定してLambdaに接続
```

【環境変数の設定方法】
- ローカル開発: プロジェクトルートの .env ファイル
- AWS上: Lambda の環境変数設定または Secrets Manager

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

# デプロイ時: Lambda パッケージ内に core/, infrastructure/ が直接存在
# cp -r ../../src/* package/ でコピーすると、package/core/, package/infrastructure/ になる
if os.path.exists(os.path.join(_current_dir, "core")):
    if _current_dir not in sys.path:
        sys.path.insert(0, _current_dir)
else:
    # 開発時: プロジェクトルートの src/ を参照
    _src_path = os.path.join(_project_root, "src")
    if _src_path not in sys.path:
        sys.path.insert(0, _src_path)

# =============================================================================
# 環境変数の読み込み（.env ファイルから）
# =============================================================================
# ローカル開発時は .env ファイルから環境変数を読み込む
# Lambda上では環境変数設定から自動的に設定される
from dotenv import load_dotenv

_env_path = os.path.join(_project_root, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

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


def create_response(body, status_code=200, extra_headers=None):
    """API Gateway用レスポンスを作成"""
    headers = {
        "Content-Type": "application/json; charset=utf-8",
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Correlation-ID",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
    }
    if extra_headers:
        headers.update(extra_headers)

    return {
        "statusCode": status_code,
        "headers": headers,
        "body": json.dumps(body, ensure_ascii=False)
    }


def create_error_response(message, status_code=500, tb=None, extra_headers=None):
    """エラーレスポンスを作成"""
    error_data = {"error": True, "message": message}
    if tb:
        error_data["traceback"] = tb
    return create_response(error_data, status_code, extra_headers)


def get_path(event):
    """リクエストパスを取得"""
    # API Gateway v2 (HTTP API)
    if "rawPath" in event:
        return event["rawPath"]
    # API Gateway v1 (REST API)
    if "path" in event:
        return event["path"]
    # ALB
    if "requestContext" in event and "path" in event["requestContext"]:
        return event["requestContext"]["path"]
    return "/"


def get_method(event):
    """HTTPメソッドを取得"""
    # API Gateway v2
    if "requestContext" in event and "http" in event["requestContext"]:
        return event["requestContext"]["http"]["method"]
    # API Gateway v1
    if "httpMethod" in event:
        return event["httpMethod"]
    return "GET"


def get_body(event):
    """リクエストボディを取得"""
    body = event.get("body", "")
    if not body:
        return b""

    # Base64エンコードされている場合
    if event.get("isBase64Encoded", False):
        import base64
        return base64.b64decode(body)

    return body.encode('utf-8') if isinstance(body, str) else body


# =============================================================================
# Lambda ハンドラー
# =============================================================================

def handler(event, context):
    """
    AWS Lambda メインハンドラー

    API Gatewayからのリクエストをルーティングして処理します。

    Args:
        event: API Gatewayイベント
        context: Lambda実行コンテキスト

    Returns:
        dict: API Gatewayレスポンス形式
    """
    path = get_path(event)
    method = get_method(event)

    logger.info(f"[AWS Lambda] {method} {path}")

    # OPTIONSリクエスト（CORS preflight）
    if method == "OPTIONS":
        return create_response({})

    # ルーティング（より具体的なパスを先にマッチ）
    if "/evaluate/submit" in path:
        return handle_evaluate_submit_request(event)
    elif "/evaluate/status" in path:
        return handle_evaluate_status_request(event)
    elif "/evaluate/results" in path:
        return handle_evaluate_results_request(event)
    elif "/evaluate" in path:
        return handle_evaluate_request(event)
    elif "/health" in path:
        return handle_health_request(event)
    elif "/config" in path:
        return handle_config_request(event)
    else:
        return create_error_response(f"Not found: {path}", 404)


def handle_evaluate_request(event):
    """
    POST /evaluate - テスト評価エンドポイント
    """
    from core.handlers import handle_evaluate, parse_request_body
    from core.correlation import get_or_create_correlation_id

    logger.info("=" * 60)
    logger.info("[AWS Lambda] /evaluate が呼び出されました")

    # 相関ID抽出・設定
    headers = event.get("headers", {}) or {}
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")
    correlation_headers = {"X-Correlation-ID": correlation_id}

    method = get_method(event)
    if method != "POST":
        return create_error_response("Method not allowed", 405, extra_headers=correlation_headers)

    try:
        # リクエストボディを解析
        body = get_body(event)
        items, error = parse_request_body(body)

        if error:
            logger.error(f"[AWS Lambda] リクエスト解析エラー: {error}")
            return create_error_response(error, 400, extra_headers=correlation_headers)

        logger.info(f"[AWS Lambda] 受信: {len(items)}件のテスト項目")

        # 共通ハンドラーで評価を実行
        response = run_async(handle_evaluate(items))

        logger.info(f"[AWS Lambda] レスポンス送信: {len(response)}件")
        logger.info("=" * 60)

        return create_response(response, extra_headers=correlation_headers)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[AWS Lambda] 予期せぬエラー: {e}")
        logger.error(f"[AWS Lambda] トレースバック:\n{error_details}")
        return create_error_response(str(e), 500, error_details, extra_headers=correlation_headers)


def handle_health_request(event):
    """
    GET /health - ヘルスチェックエンドポイント
    """
    from core.handlers import handle_health
    from core.correlation import get_or_create_correlation_id

    logger.info("[AWS Lambda] /health が呼び出されました")

    # 相関ID抽出・設定
    headers = event.get("headers", {}) or {}
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")

    status = handle_health()
    status["platform"] = "AWS Lambda"

    return create_response(status, extra_headers={"X-Correlation-ID": correlation_id})


def handle_config_request(event):
    """
    GET /config - 設定状態エンドポイント
    """
    from core.handlers import handle_config
    from core.correlation import get_or_create_correlation_id

    logger.info("[AWS Lambda] /config が呼び出されました")

    # 相関ID抽出・設定
    headers = event.get("headers", {}) or {}
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")

    config = handle_config()
    config["platform"] = {
        "name": "AWS Lambda",
        "runtime": "python3.11",
        "framework": "API Gateway"
    }

    return create_response(config, extra_headers={"X-Correlation-ID": correlation_id})


# =============================================================================
# 非同期APIエンドポイント（504タイムアウト対策）
# =============================================================================

def handle_evaluate_submit_request(event):
    """
    POST /evaluate/submit - 非同期ジョブ送信エンドポイント
    """
    from core.handlers import parse_request_body
    from core.async_handlers import handle_submit
    from core.correlation import get_or_create_correlation_id

    logger.info("=" * 60)
    logger.info("[AWS Lambda] /evaluate/submit が呼び出されました")

    # 相関ID抽出・設定
    headers = event.get("headers", {}) or {}
    correlation_id = get_or_create_correlation_id(headers)
    logger.info(f"[Correlation ID] {correlation_id}")
    correlation_headers = {"X-Correlation-ID": correlation_id}

    method = get_method(event)
    if method != "POST":
        return create_error_response("Method not allowed", 405, extra_headers=correlation_headers)

    try:
        body = get_body(event)
        items, error = parse_request_body(body)

        if error:
            logger.error(f"[AWS Lambda] リクエスト解析エラー: {error}")
            return create_error_response(error, 400, extra_headers=correlation_headers)

        logger.info(f"[AWS Lambda] 受信: {len(items)}件のテスト項目")

        # テナントIDを取得
        tenant_id = headers.get("x-tenant-id", headers.get("X-Tenant-ID", "default"))

        response = run_async(handle_submit(items=items, tenant_id=tenant_id))

        if response.get("error"):
            logger.error(f"[AWS Lambda] ジョブ送信エラー: {response.get('message')}")
            return create_response(response, 500, extra_headers=correlation_headers)

        logger.info(f"[AWS Lambda] ジョブ送信完了: {response.get('job_id')}")
        return create_response(response, 202, extra_headers=correlation_headers)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[AWS Lambda] 予期せぬエラー: {e}")
        return create_error_response(str(e), 500, error_details, extra_headers=correlation_headers)


def handle_evaluate_status_request(event):
    """
    GET /evaluate/status/{job_id} - ジョブステータス確認エンドポイント
    """
    from core.async_handlers import handle_status
    from core.correlation import get_or_create_correlation_id

    # 相関ID抽出・設定
    headers = event.get("headers", {}) or {}
    correlation_id = get_or_create_correlation_id(headers)
    correlation_headers = {"X-Correlation-ID": correlation_id}

    path = get_path(event)
    # パスからjob_idを抽出: /evaluate/status/{job_id}
    parts = path.split("/")
    job_id = parts[-1] if len(parts) > 0 else None

    if not job_id or job_id == "status":
        # クエリパラメータから取得を試みる
        query_params = event.get("queryStringParameters", {}) or {}
        job_id = query_params.get("job_id")

    if not job_id:
        return create_error_response("job_id is required", 400, extra_headers=correlation_headers)

    logger.debug(f"[AWS Lambda] /evaluate/status/{job_id} が呼び出されました")
    logger.debug(f"[Correlation ID] {correlation_id}")

    try:
        response = run_async(handle_status(job_id))

        if response.get("status") == "not_found":
            return create_error_response(f"Job not found: {job_id}", 404, extra_headers=correlation_headers)

        return create_response(response, extra_headers=correlation_headers)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[AWS Lambda] 予期せぬエラー: {e}")
        return create_error_response(str(e), 500, error_details, extra_headers=correlation_headers)


def handle_evaluate_results_request(event):
    """
    GET /evaluate/results/{job_id} - ジョブ結果取得エンドポイント
    """
    from core.async_handlers import handle_results
    from core.correlation import get_or_create_correlation_id

    # 相関ID抽出・設定
    headers = event.get("headers", {}) or {}
    correlation_id = get_or_create_correlation_id(headers)
    correlation_headers = {"X-Correlation-ID": correlation_id}

    path = get_path(event)
    # パスからjob_idを抽出: /evaluate/results/{job_id}
    parts = path.split("/")
    job_id = parts[-1] if len(parts) > 0 else None

    if not job_id or job_id == "results":
        query_params = event.get("queryStringParameters", {}) or {}
        job_id = query_params.get("job_id")

    if not job_id:
        return create_error_response("job_id is required", 400, extra_headers=correlation_headers)

    logger.info(f"[AWS Lambda] /evaluate/results/{job_id} が呼び出されました")
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

        logger.info(f"[AWS Lambda] 結果返却: {len(response.get('results', []))}件")
        return create_response(response, extra_headers=correlation_headers)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[AWS Lambda] 予期せぬエラー: {e}")
        return create_error_response(str(e), 500, error_details, extra_headers=correlation_headers)


# =============================================================================
# ローカルテスト用
# =============================================================================

if __name__ == "__main__":
    # ローカルテスト: 簡易HTTPサーバーで起動
    from http.server import HTTPServer, BaseHTTPRequestHandler

    class LocalHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._handle_request("GET")

        def do_POST(self):
            self._handle_request("POST")

        def do_OPTIONS(self):
            self._handle_request("OPTIONS")

        def _handle_request(self, method):
            # リクエストボディを読み込み
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else ""

            # Lambda形式のイベントを作成
            event = {
                "path": self.path,
                "httpMethod": method,
                "body": body,
                "headers": dict(self.headers),
                "isBase64Encoded": False
            }

            # Lambda handlerを呼び出し
            result = handler(event, None)

            # レスポンスを送信
            self.send_response(result["statusCode"])
            for key, value in result.get("headers", {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(result["body"].encode('utf-8'))

    print("AWS Lambda ローカルサーバー起動: http://localhost:8080")
    server = HTTPServer(('localhost', 8080), LocalHandler)
    server.serve_forever()
