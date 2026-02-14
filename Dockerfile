# =============================================================================
# Dockerfile - 内部統制テスト評価AIシステム
# =============================================================================
# 用途: ローカルサーバー / Cloud Run / Container Apps / App Runner
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
# - curl: ヘルスチェック用
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-jpn \
    tesseract-ocr-eng \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 非rootユーザー作成（セキュリティ）
RUN useradd --create-home --shell /bin/bash --uid 1000 appuser

# Builderからpipパッケージをコピー
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# アプリケーションコードをコピー
COPY --chown=appuser:appuser src/ ./src/
COPY --chown=appuser:appuser platforms/local/main.py ./main.py

# ファイルパーミッションを明示的に設定
RUN chmod -R 755 /app/src && \
    chmod 755 /app/main.py

# ユーザー切り替え
USER appuser

# 環境変数デフォルト
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    HOST=0.0.0.0 \
    LLM_PROVIDER=AZURE \
    OCR_PROVIDER=TESSERACT \
    LOG_LEVEL=INFO \
    LOG_TO_FILE=false

# ヘルスチェック（curl使用で信頼性向上、start-periodを延長）
HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# ポート公開
EXPOSE ${PORT}

# 起動コマンド
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080}"]
