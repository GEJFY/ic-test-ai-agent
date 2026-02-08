"""
================================================================================
main.py - ローカル/オンプレミス サーバーエントリーポイント
================================================================================

【概要】
内部統制テスト評価AIシステムのローカル/オンプレミス用APIサーバーです。
FastAPIを使用し、クラウドに依存しない環境で動作します。

【特徴】
- オフライン動作: ネットワーク接続不要
- プライバシー: データが外部に送信されない
- カスタマイズ: ローカルLLM/OCRを使用
- 低コスト: クラウドAPIの利用料金が不要

【エンドポイント】
=== 同期API ===
1. POST /evaluate - テスト評価実行

=== 非同期API ===
2. POST /evaluate/submit - ジョブ送信
3. GET /evaluate/status/{job_id} - ステータス確認
4. GET /evaluate/results/{job_id} - 結果取得

=== 管理API ===
5. GET /health - ヘルスチェック
6. GET /config - 設定状態確認

【必要条件】
- Ollama がインストール・起動していること
- 使用するモデルがpullされていること
  例: ollama pull llama3.1:8b

【起動方法】
```bash
# 開発サーバー
cd platforms/local
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# 本番サーバー（Gunicorn + Uvicorn Worker）
gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

【環境変数】
- LLM_PROVIDER=LOCAL (必須)
- OCR_PROVIDER=TESSERACT (オプション、デフォルト: NONE)
- OLLAMA_BASE_URL=http://localhost:11434 (オプション)
- OLLAMA_MODEL=llama3.1:8b (オプション)
- TESSERACT_LANG=jpn+eng (オプション)

================================================================================
"""
import sys
import os
import logging
import traceback
from typing import List, Dict, Any, Optional
from contextlib import asynccontextmanager

# =============================================================================
# パス設定
# =============================================================================

_current_dir = os.path.dirname(os.path.abspath(__file__))

# Docker環境: main.pyは/appに配置、srcは/app/srcにある
# ローカル環境: main.pyはplatforms/local/に配置、srcはプロジェクトルート/srcにある
_docker_src_path = os.path.join(_current_dir, "src")
_local_src_path = os.path.join(os.path.dirname(os.path.dirname(_current_dir)), "src")

if os.path.exists(_docker_src_path):
    # Docker環境
    _src_path = _docker_src_path
    _project_root = _current_dir
else:
    # ローカル環境
    _src_path = _local_src_path
    _project_root = os.path.dirname(os.path.dirname(_current_dir))

if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# =============================================================================
# 環境変数の読み込み
# =============================================================================

from dotenv import load_dotenv

_env_path = os.path.join(_project_root, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)

# ローカルモードのデフォルト設定
if not os.getenv("LLM_PROVIDER"):
    os.environ["LLM_PROVIDER"] = "LOCAL"
if not os.getenv("OCR_PROVIDER"):
    os.environ["OCR_PROVIDER"] = "TESSERACT"

# =============================================================================
# FastAPI インポート
# =============================================================================

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# =============================================================================
# ログ設定
# =============================================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# =============================================================================
# Pydantic モデル
# =============================================================================

class EvaluationItem(BaseModel):
    """評価項目"""
    ID: str
    controlDescription: str
    evidenceFiles: Optional[List[Dict[str, Any]]] = []
    testProcedures: Optional[str] = ""


class EvaluationRequest(BaseModel):
    """評価リクエスト"""
    items: List[Dict[str, Any]]


class JobSubmitResponse(BaseModel):
    """ジョブ送信レスポンス"""
    job_id: str
    status: str
    estimated_time: int
    message: str


class JobStatusResponse(BaseModel):
    """ジョブステータスレスポンス"""
    job_id: str
    status: str
    progress: int
    message: str
    error_message: Optional[str] = None


# =============================================================================
# FastAPI アプリケーション
# =============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """アプリケーションのライフサイクル管理"""
    # 起動時
    logger.info("=" * 60)
    logger.info("[Local Server] 起動開始")
    logger.info(f"[Local Server] LLM_PROVIDER: {os.getenv('LLM_PROVIDER')}")
    logger.info(f"[Local Server] OCR_PROVIDER: {os.getenv('OCR_PROVIDER')}")
    logger.info(f"[Local Server] OLLAMA_BASE_URL: {os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}")
    logger.info("=" * 60)

    yield

    # 終了時
    logger.info("[Local Server] シャットダウン")


app = FastAPI(
    title="内部統制テスト評価AI - ローカルサーバー",
    description="オンプレミス/ローカル環境で動作する内部統制テスト評価AIシステム",
    version="1.0.0",
    lifespan=lifespan
)

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# ヘルパー関数
# =============================================================================

def create_json_response(data: Any, status_code: int = 200) -> JSONResponse:
    """JSONレスポンスを作成"""
    return JSONResponse(content=data, status_code=status_code)


def create_error_response(message: str, status_code: int = 500, details: str = None) -> JSONResponse:
    """エラーレスポンスを作成"""
    error_data = {"error": True, "message": message}
    if details:
        error_data["details"] = details
    return JSONResponse(content=error_data, status_code=status_code)


# =============================================================================
# APIエンドポイント
# =============================================================================

@app.get("/health")
async def health():
    """
    GET /health - ヘルスチェックエンドポイント
    """
    from core.handlers import handle_health

    logger.info("[Local Server] /health が呼び出されました")

    status = handle_health()
    status["platform"] = "Local (FastAPI + Ollama)"

    # Ollamaの接続状態を確認
    ollama_status = await check_ollama_connection()
    status["ollama"] = ollama_status

    return status


@app.get("/config")
async def config_status():
    """
    GET /config - 設定状態エンドポイント
    """
    from core.handlers import handle_config

    logger.info("[Local Server] /config が呼び出されました")

    config = handle_config()
    config["platform"] = {
        "name": "Local Server",
        "runtime": "python",
        "framework": "FastAPI",
        "llm_backend": "Ollama"
    }

    # Ollama固有の設定情報
    config["ollama"] = {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        "model": os.getenv("OLLAMA_MODEL", "llama3.1:8b"),
        "vision_model": os.getenv("OLLAMA_VISION_MODEL", "llava:13b"),
    }

    # Tesseract固有の設定情報
    if os.getenv("OCR_PROVIDER", "").upper() == "TESSERACT":
        config["tesseract"] = {
            "lang": os.getenv("TESSERACT_LANG", "jpn+eng"),
            "cmd": os.getenv("TESSERACT_CMD", "auto-detect"),
        }

    return config


@app.post("/evaluate")
async def evaluate(request: Request):
    """
    POST /evaluate - テスト評価エンドポイント（同期）
    """
    from core.handlers import handle_evaluate, parse_request_body

    logger.info("=" * 60)
    logger.info("[Local Server] /evaluate が呼び出されました")

    try:
        # リクエストボディを解析
        body = await request.body()
        items, error = parse_request_body(body)

        if error:
            logger.error(f"[Local Server] リクエスト解析エラー: {error}")
            return create_error_response(error, 400)

        logger.info(f"[Local Server] 受信: {len(items)}件のテスト項目")

        # 共通ハンドラーで評価を実行
        response = await handle_evaluate(items)

        logger.info(f"[Local Server] レスポンス送信: {len(response)}件")
        logger.info("=" * 60)

        return response

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[Local Server] 予期せぬエラー: {e}")
        logger.error(f"[Local Server] トレースバック:\n{error_details}")
        return create_error_response(str(e), 500, error_details)


@app.post("/evaluate/submit")
async def evaluate_submit(request: Request):
    """
    POST /evaluate/submit - 非同期ジョブ送信エンドポイント
    """
    from core.handlers import parse_request_body
    from core.async_handlers import handle_submit

    logger.info("=" * 60)
    logger.info("[Local Server] /evaluate/submit が呼び出されました")

    try:
        body = await request.body()
        items, error = parse_request_body(body)

        if error:
            logger.error(f"[Local Server] リクエスト解析エラー: {error}")
            return create_error_response(error, 400)

        logger.info(f"[Local Server] 受信: {len(items)}件のテスト項目")

        tenant_id = request.headers.get("X-Tenant-ID", "default")
        response = await handle_submit(items=items, tenant_id=tenant_id)

        if response.get("error"):
            logger.error(f"[Local Server] ジョブ送信エラー: {response.get('message')}")
            return create_json_response(response, 500)

        logger.info(f"[Local Server] ジョブ送信完了: {response.get('job_id')}")
        return create_json_response(response, 202)

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[Local Server] 予期せぬエラー: {e}")
        return create_error_response(str(e), 500, error_details)


@app.get("/evaluate/status/{job_id}")
async def evaluate_status(job_id: str):
    """
    GET /evaluate/status/{job_id} - ジョブステータス確認エンドポイント
    """
    from core.async_handlers import handle_status

    logger.debug(f"[Local Server] /evaluate/status/{job_id} が呼び出されました")

    try:
        response = await handle_status(job_id)

        if response.get("status") == "not_found":
            return create_error_response(f"Job not found: {job_id}", 404)

        return response

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[Local Server] 予期せぬエラー: {e}")
        return create_error_response(str(e), 500, error_details)


@app.get("/evaluate/results/{job_id}")
async def evaluate_results(job_id: str):
    """
    GET /evaluate/results/{job_id} - ジョブ結果取得エンドポイント
    """
    from core.async_handlers import handle_results

    logger.info(f"[Local Server] /evaluate/results/{job_id} が呼び出されました")

    try:
        response = await handle_results(job_id)

        if response.get("status") == "not_found":
            return create_error_response(f"Job not found: {job_id}", 404)

        if response.get("status") not in ["completed", "failed"]:
            return create_json_response({
                "job_id": job_id,
                "status": response.get("status"),
                "message": "Job not completed yet. Please check status endpoint."
            }, 202)

        logger.info(f"[Local Server] 結果返却: {len(response.get('results', []))}件")
        return response

    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"[Local Server] 予期せぬエラー: {e}")
        return create_error_response(str(e), 500, error_details)


# =============================================================================
# ユーティリティ
# =============================================================================

async def check_ollama_connection() -> dict:
    """Ollamaの接続状態を確認"""
    import httpx

    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{base_url}/api/tags")

            if response.status_code == 200:
                data = response.json()
                models = [m.get("name") for m in data.get("models", [])]
                return {
                    "connected": True,
                    "base_url": base_url,
                    "available_models": models[:10],  # 最大10件
                    "model_count": len(models)
                }
            else:
                return {
                    "connected": False,
                    "base_url": base_url,
                    "error": f"HTTP {response.status_code}"
                }
    except Exception as e:
        return {
            "connected": False,
            "base_url": base_url,
            "error": str(e)
        }


# =============================================================================
# メイン（開発用）
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    print("=" * 60)
    print("内部統制テスト評価AI - ローカルサーバー")
    print("=" * 60)
    print(f"LLM Provider: {os.getenv('LLM_PROVIDER', 'LOCAL')}")
    print(f"OCR Provider: {os.getenv('OCR_PROVIDER', 'TESSERACT')}")
    print(f"Ollama URL: {os.getenv('OLLAMA_BASE_URL', 'http://localhost:11434')}")
    print("=" * 60)
    print("起動中: http://localhost:8000")
    print("API ドキュメント: http://localhost:8000/docs")
    print("=" * 60)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
