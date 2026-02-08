# ローカル/オンプレミス プラットフォーム

## 概要

クラウドサービスを使用せずに、内部統制テスト評価AIシステムをローカル環境で運用するためのプラットフォームです。

### 特徴

- **完全オフライン動作**: インターネット接続なしで動作可能
- **データセキュリティ**: データが外部サーバーに送信されない
- **ランニングコストゼロ**: クラウドAPI利用料が発生しない
- **カスタマイズ可能**: 任意のOllamaモデルを使用可能

### コンポーネント

| コンポーネント | 役割 | デフォルト |
|--------------|------|-----------|
| **Ollama** | ローカルLLMサーバー | llama3.1:8b |
| **Tesseract** | ローカルOCR | jpn+eng |
| **FastAPI** | APIサーバー | port 8000 |

---

## クイックスタート

### 1. 前提条件

- Python 3.11以上
- Ollama インストール済み
- Tesseract インストール済み（OCR機能を使用する場合）

### 2. セットアップ

```powershell
# プロジェクトルートから
cd platforms/local

# 依存関係のインストール
pip install -r requirements.txt

# Ollamaモデルのダウンロード
ollama pull llama3.1:8b
ollama pull llava:13b  # Vision機能用（任意）
```

### 3. 起動

```powershell
# PowerShellスクリプトを使用
.\start.ps1

# または直接起動
python main.py
```

### 4. 動作確認

```powershell
# ヘルスチェック
curl http://localhost:8000/health

# 設定確認
curl http://localhost:8000/config
```

---

## インストール詳細

### Ollama のインストール

#### Windows

```powershell
# winget を使用
winget install Ollama.Ollama

# または公式サイトからダウンロード
# https://ollama.ai/download/windows
```

#### macOS

```bash
brew install ollama
```

#### Linux

```bash
curl -fsSL https://ollama.ai/install.sh | sh
```

### Tesseract のインストール

#### Windows

```powershell
# Chocolatey を使用
choco install tesseract

# 日本語言語パック
choco install tesseract-lang
```

または [UB-Mannheim](https://github.com/UB-Mannheim/tesseract/wiki) からインストーラーをダウンロード

#### macOS

```bash
brew install tesseract tesseract-lang
```

#### Linux

```bash
sudo apt-get install tesseract-ocr tesseract-ocr-jpn tesseract-ocr-eng
```

---

## 環境変数

すべての環境変数は任意です（デフォルト値があります）。

| 環境変数 | 説明 | デフォルト |
|---------|------|-----------|
| `LLM_PROVIDER` | LLMプロバイダー | `LOCAL` |
| `OCR_PROVIDER` | OCRプロバイダー | `TESSERACT` |
| `OLLAMA_BASE_URL` | OllamaサーバーURL | `http://localhost:11434` |
| `OLLAMA_MODEL` | テキスト処理用モデル | `llama3.1:8b` |
| `OLLAMA_VISION_MODEL` | 画像認識用モデル | `llava:13b` |
| `TESSERACT_LANG` | OCR認識言語 | `jpn+eng` |
| `TESSERACT_CMD` | Tesseract実行パス | システムPATHから検索 |

### .env ファイルの例

```ini
# ローカル/オンプレミス設定
LLM_PROVIDER=LOCAL
OCR_PROVIDER=TESSERACT

# Ollama設定（任意）
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_VISION_MODEL=llava:13b

# Tesseract設定（任意）
TESSERACT_LANG=jpn+eng
```

---

## API エンドポイント

### ヘルスチェック

```http
GET /health
```

レスポンス例:
```json
{
  "status": "healthy",
  "llm_configured": true,
  "platform": "Local/On-Premise (FastAPI)",
  "ollama_status": "connected"
}
```

### 設定確認

```http
GET /config
```

### 同期評価

```http
POST /evaluate
Content-Type: application/json

[
  {
    "id": "IC-001",
    "controlDescription": "月次で売上レポートを作成し、マネージャーが承認する",
    "testProcedure": "承認済みのレポートを確認する",
    "evidenceText": "承認印と日付が記載されたレポートを確認"
  }
]
```

### 非同期評価（推奨）

```http
# ジョブ送信
POST /evaluate/submit
Content-Type: application/json

# ステータス確認
GET /evaluate/status/{job_id}

# 結果取得
GET /evaluate/results/{job_id}
```

---

## ハードウェア要件

### 最小要件

| コンポーネント | 要件 |
|--------------|------|
| CPU | 4コア |
| RAM | 8GB |
| ストレージ | 20GB |

### 推奨要件

| コンポーネント | 要件 |
|--------------|------|
| CPU | 8コア以上 |
| RAM | 16GB以上 |
| GPU | NVIDIA GPU (VRAM 6GB以上) |
| ストレージ | 50GB SSD |

> **注意**: GPU がない場合は CPU で動作しますが、処理速度が大幅に低下します。

---

## モデル選択ガイド

### テキスト処理用モデル

| モデル | サイズ | VRAM | 特徴 |
|-------|-------|------|------|
| `llama3.1:8b` | 4.7GB | 6GB | バランス型（推奨） |
| `llama3.1:70b` | 40GB | 48GB | 高精度 |
| `mistral:7b` | 4.1GB | 5GB | 軽量・高速 |
| `gemma2:9b` | 5.5GB | 7GB | Google製 |

### Vision（画像認識）用モデル

| モデル | サイズ | VRAM | 特徴 |
|-------|-------|------|------|
| `llava:13b` | 8GB | 10GB | 高精度（推奨） |
| `llava:7b` | 4.5GB | 6GB | 軽量 |

### モデルのダウンロード

```bash
# テキスト処理用
ollama pull llama3.1:8b

# Vision用
ollama pull llava:13b

# インストール済みモデルの確認
ollama list
```

---

## トラブルシューティング

### Ollama に接続できない

```bash
# Ollamaが起動しているか確認
ollama list

# サービスを起動
ollama serve

# Windows: サービスが自動起動しているか確認
Get-Service -Name "Ollama" -ErrorAction SilentlyContinue
```

### モデルが見つからない

```bash
# インストール済みモデルを確認
ollama list

# モデルを再ダウンロード
ollama pull llama3.1:8b
```

### メモリ不足エラー

```bash
# より小さいモデルを使用
ollama pull mistral:7b
export OLLAMA_MODEL=mistral:7b
```

### Tesseract が見つからない

```bash
# パスを確認
tesseract --version

# Windowsの場合、環境変数を設定
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

### 日本語OCRの精度が低い

```bash
# 日本語言語パックがインストールされているか確認
tesseract --list-langs

# 日本語パックをインストール（Linux）
sudo apt-get install tesseract-ocr-jpn
```

---

## パフォーマンスチューニング

### GPU アクセラレーション

Ollama は NVIDIA GPU を自動検出します。

```bash
# GPU使用状況を確認
nvidia-smi
```

### 並列処理

```bash
# 複数リクエストを同時に処理
uvicorn main:app --workers 4
```

### モデルのプリロード

```bash
# サーバー起動前にモデルをメモリにロード
ollama run llama3.1:8b "Hello"
```

---

## ファイル構成

```
platforms/local/
├── main.py           # FastAPI エントリポイント
├── requirements.txt  # Python依存関係
├── start.ps1         # Windows起動スクリプト
└── README.md         # このファイル
```

---

## 関連ドキュメント

- [メインREADME](../../README.md) - プロジェクト全体の説明
- [プラットフォームガイド](../README.md) - 全プラットフォームの比較
- [LLM Factory](../../src/infrastructure/llm_factory.py) - LLMプロバイダー実装
