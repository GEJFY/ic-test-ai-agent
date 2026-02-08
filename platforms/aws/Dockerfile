# ==============================================================================
# AWS Lambda Dockerfile - Tesseract OCR対応版
# ==============================================================================
#
# 【概要】
# Tesseract OCRを含むAWS Lambda Docker イメージ
# タイ語、オランダ語、日本語、英語のOCRに対応
#
# 【ビルドコマンド】
# docker build -t ic-test-lambda .
#
# 【ローカルテスト】
# docker run -p 9000:8080 \
#   -e AWS_REGION=ap-northeast-1 \
#   -e LLM_PROVIDER=AWS \
#   -e OCR_PROVIDER=TESSERACT \
#   -e TESSERACT_LANG=jpn+eng+tha+nld \
#   ic-test-lambda
#
# curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" \
#   -d '{"path":"/health","httpMethod":"GET"}'
#
# 【ECRへのプッシュ】
# aws ecr get-login-password --region ap-northeast-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.ap-northeast-1.amazonaws.com
# docker tag ic-test-lambda:latest <account>.dkr.ecr.ap-northeast-1.amazonaws.com/ic-test-lambda:latest
# docker push <account>.dkr.ecr.ap-northeast-1.amazonaws.com/ic-test-lambda:latest
#
# ==============================================================================

FROM public.ecr.aws/lambda/python:3.11

# ==============================================================================
# Tesseract OCR インストール
# ==============================================================================

# 必要なパッケージをインストール
RUN dnf install -y \
    tesseract \
    tesseract-langpack-jpn \
    tesseract-langpack-tha \
    tesseract-langpack-nld \
    tesseract-langpack-eng \
    # PDF処理用（pdf2image）
    poppler-utils \
    # 画像処理
    libjpeg-turbo \
    libpng \
    && dnf clean all \
    && rm -rf /var/cache/dnf

# Tesseractの動作確認
RUN tesseract --version && tesseract --list-langs

# ==============================================================================
# Python依存関係
# ==============================================================================

# requirements.txtをコピーしてインストール
COPY requirements.txt ${LAMBDA_TASK_ROOT}/
RUN pip install --no-cache-dir -r ${LAMBDA_TASK_ROOT}/requirements.txt

# ==============================================================================
# アプリケーションコード
# ==============================================================================

# プロジェクトルートから src/ ディレクトリをコピー
# ビルド時に `docker build -f platforms/aws/Dockerfile .` を使用
COPY src/core/ ${LAMBDA_TASK_ROOT}/core/
COPY src/infrastructure/ ${LAMBDA_TASK_ROOT}/infrastructure/

# Lambda ハンドラーをコピー
COPY platforms/aws/lambda_handler.py ${LAMBDA_TASK_ROOT}/

# ==============================================================================
# 環境変数
# ==============================================================================

# Tesseract設定
ENV TESSERACT_CMD=/usr/bin/tesseract
ENV TESSERACT_LANG=jpn+eng+tha+nld

# OCRプロバイダー（デフォルト: Tesseract）
ENV OCR_PROVIDER=TESSERACT

# Lambda設定
ENV LAMBDA_TASK_ROOT=/var/task

# ==============================================================================
# エントリポイント
# ==============================================================================

CMD ["lambda_handler.handler"]
