"""
================================================================================
lambda_handler.py - AWS Lambda エントリーポイント
================================================================================

【概要】
内部統制テスト評価AIシステムのAWS Lambda用APIエントリポイントです。
API Gateway経由でExcel VBAマクロからのリクエストを受け付け、AI評価結果を返します。

【エンドポイント】（API Gateway設定）
1. POST /evaluate - テスト評価実行
2. GET /health - ヘルスチェック
3. GET /config - 設定状態確認

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
    "OCR_PROVIDER":"AWS",
    "USE_GRAPH_ORCHESTRATOR":"true"
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


def create_response(body, status_code=200):
    """API Gateway用レスポンスを作成"""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json; charset=utf-8",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS"
        },
        "body": json.dumps(body, ensure_ascii=False)
    }


def create_error_response(message, status_code=500, tb=None):
    """エラーレスポンスを作成"""
    error_data = {"error": True, "message": message}
    if tb:
        error_data["traceback"] = tb
    return create_response(error_data, status_code)


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

    # ルーティング
    if "/evaluate" in path:
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

    logger.info("=" * 60)
    logger.info("[AWS Lambda] /evaluate が呼び出されました")

    method = get_method(event)
    if method != "POST":
        return create_error_response("Method not allowed", 405)

    try:
        # リクエストボディを解析
        body = get_body(event)
        items, error = parse_request_body(body)

        if error:
            logger.error(f"[AWS Lambda] リクエスト解析エラー: {error}")
            return create_error_response(error, 400)

        logger.info(f"[AWS Lambda] 受信: {len(items)}件のテスト項目")

        # 共通ハンドラーで評価を実行
        response = run_async(handle_evaluate(items))

        logger.info(f"[AWS Lambda] レスポンス送信: {len(response)}件")
        logger.info("=" * 60)

        return create_response(response)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[AWS Lambda] 予期せぬエラー: {e}")
        logger.error(f"[AWS Lambda] トレースバック:\n{error_details}")
        return create_error_response(str(e), 500, error_details)


def handle_health_request(event):
    """
    GET /health - ヘルスチェックエンドポイント
    """
    from core.handlers import handle_health

    logger.info("[AWS Lambda] /health が呼び出されました")

    status = handle_health()
    status["platform"] = "AWS Lambda"

    return create_response(status)


def handle_config_request(event):
    """
    GET /config - 設定状態エンドポイント
    """
    from core.handlers import handle_config

    logger.info("[AWS Lambda] /config が呼び出されました")

    config = handle_config()
    config["platform"] = {
        "name": "AWS Lambda",
        "runtime": "python3.11",
        "framework": "API Gateway"
    }

    return create_response(config)


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
