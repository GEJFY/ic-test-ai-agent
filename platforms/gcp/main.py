"""
================================================================================
main.py - GCP Cloud Functions エントリーポイント
================================================================================

【概要】
内部統制テスト評価AIシステムのGCP Cloud Functions用APIエントリポイントです。
Excel VBAマクロからのリクエストを受け付け、AI評価結果を返します。

【エンドポイント】
1. POST /evaluate - テスト評価実行
2. GET /health - ヘルスチェック
3. GET /config - 設定状態確認

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


def create_response(data, status_code=200):
    """JSONレスポンスを作成"""
    response = make_response(
        json.dumps(data, ensure_ascii=False),
        status_code
    )
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response


def create_error_response(message, status_code=500, tb=None):
    """エラーレスポンスを作成"""
    error_data = {"error": True, "message": message}
    if tb:
        error_data["traceback"] = tb
    return create_response(error_data, status_code)


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

    logger.info("=" * 60)
    logger.info("[GCP] /evaluate が呼び出されました")

    # POSTメソッドのみ許可
    if request.method != 'POST':
        return create_error_response("Method not allowed", 405)

    try:
        # リクエストボディを解析
        items, error = parse_request_body(request.get_data())

        if error:
            logger.error(f"[GCP] リクエスト解析エラー: {error}")
            return create_error_response(error, 400)

        logger.info(f"[GCP] 受信: {len(items)}件のテスト項目")

        # 共通ハンドラーで評価を実行（非同期を同期的に実行）
        response = run_async(handle_evaluate(items))

        logger.info(f"[GCP] レスポンス送信: {len(response)}件")
        logger.info("=" * 60)

        return create_response(response)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[GCP] 予期せぬエラー: {e}")
        logger.error(f"[GCP] トレースバック:\n{error_details}")
        return create_error_response(str(e), 500, error_details)


@functions_framework.http
def health(request: Request):
    """
    GET /health - ヘルスチェックエンドポイント

    システムの稼働状態と設定状況を返します。
    """
    from core.handlers import handle_health

    logger.info("[GCP] /health が呼び出されました")

    status = handle_health()
    status["platform"] = "GCP Cloud Functions"

    return create_response(status)


@functions_framework.http
def config_status(request: Request):
    """
    GET /config - 設定状態エンドポイント

    AI機能に必要な設定の状態を詳細に表示します。
    """
    from core.handlers import handle_config

    logger.info("[GCP] /config が呼び出されました")

    config = handle_config()
    config["platform"] = {
        "name": "GCP Cloud Functions",
        "runtime": "python311",
        "framework": "functions-framework"
    }

    return create_response(config)


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
