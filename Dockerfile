# =============================================================================
# Dockerfile - 内部統制テスト評価AIシステム
# =============================================================================
# 用途: ローカルサーバー / Cloud Run / Container Apps
#
# ビルド:
#   docker build -t ic-test-ai-agent:latest .
#
# 実行:
#   docker run -p 8080:8080 --env-file .env ic-test-ai-agent:latest
#
# =============================================================================

# -----------------------------------------------------------------------------
# Stage 1: Builder (依存関係インストール)
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS builder

WORKDIR /app

# システム依存関係（ビルド用）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Python依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# -----------------------------------------------------------------------------
# Stage 2: Runtime (実行環境)
# -----------------------------------------------------------------------------
FROM python:3.11-slim AS runtime

WORKDIR /app

# 実行時に必要なシステムパッケージ
# - tesseract-ocr: ローカルOCR用（OCR_PROVIDER=TESSERACT時）
# - tesseract-ocr-jpn: 日本語OCR用
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-jpn \
    tesseract-ocr-eng \
    && rm -rf /var/lib/apt/lists/*

# 非rootユーザー作成（セキュリティ）
RUN useradd --create-home --shell /bin/bash appuser

# Builderからpipパッケージをコピー
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# アプリケーションコードをコピー
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser platforms/local/main.py ./main.py

# ユーザー切り替え
USER appuser

# 環境変数デフォルト
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    HOST=0.0.0.0 \
    # デフォルトプロバイダー（環境変数で上書き可能）
    LLM_PROVIDER=AZURE_FOUNDRY \
    OCR_PROVIDER=TESSERACT \
    # ログ設定
    LOG_LEVEL=INFO \
    LOG_TO_FILE=false

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT}/health')" || exit 1

# ポート公開
EXPOSE ${PORT}

# 起動コマンド
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
