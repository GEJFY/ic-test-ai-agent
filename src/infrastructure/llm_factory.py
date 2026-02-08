# -*- coding: utf-8 -*-
"""
================================================================================
llm_factory.py - LLMファクトリー（マルチクラウドLLMプロバイダー対応）
================================================================================

【概要】
このモジュールは、複数のクラウドLLMプロバイダーに対応した
LLMインスタンス生成ファクトリーを提供します。

環境変数の設定に基づいて、適切なプロバイダーのLLMを
自動的に選択・作成します。

【設計思想】
- ファクトリーパターン: クライアントコードはプロバイダーの違いを意識しない
- 設定の一元管理: 環境変数で全設定を制御
- フェイルセーフ: 設定不足時は明確なエラーメッセージを表示

【対応プロバイダー】
┌─────────────────┬────────────────────────────────────────────────┐
│ プロバイダー    │ 説明                                           │
├─────────────────┼────────────────────────────────────────────────┤
│ AZURE           │ Azure OpenAI Service（企業向け、SLA保証）      │
│ AZURE_FOUNDRY   │ Azure AI Foundry（統合AIプラットフォーム）     │
│ GCP             │ Google Cloud Vertex AI（Geminiモデル）         │
│ AWS             │ Amazon Bedrock（Claude等）                     │
└─────────────────┴────────────────────────────────────────────────┘

【使用例】
```python
from infrastructure.llm_factory import LLMFactory

# === 基本的な使い方 ===

# テキスト処理用LLMを作成
llm = LLMFactory.create_chat_model(temperature=0.0)

# 画像認識用LLMを作成
vision_llm = LLMFactory.create_vision_model(temperature=0.0)

# === 設定状態の確認 ===

status = LLMFactory.get_config_status()
print(f"プロバイダー: {status['provider']}")
print(f"設定完了: {status['configured']}")

if not status['configured']:
    print(f"不足している環境変数: {status['missing_vars']}")
```

【環境変数の設定例】

Azure OpenAI の場合:
```bash
export LLM_PROVIDER=AZURE
export AZURE_OPENAI_API_KEY=your-api-key
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o
```

Azure AI Foundry の場合:
```bash
export LLM_PROVIDER=AZURE_FOUNDRY
export AZURE_FOUNDRY_ENDPOINT=https://project.region.models.ai.azure.com
export AZURE_FOUNDRY_API_KEY=your-api-key
export AZURE_FOUNDRY_MODEL=gpt-4o
```

【注意事項】
- 各プロバイダーの認証情報は環境変数または.envファイルで設定
- APIキーは決してソースコードにハードコードしないこと
- 本番環境ではKey Vault等のシークレット管理サービスを使用推奨

================================================================================
"""

import os
import time
import traceback
from typing import Optional, Dict, Any, List
from enum import Enum

# =============================================================================
# ログ設定
# =============================================================================
# 新しいログモジュールを使用（ファイル出力、ローテーション対応）

try:
    from infrastructure.logging_config import get_logger
except ImportError:
    # フォールバック：標準のloggingモジュールを使用
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s | %(levelname)-8s | %(name)s | %(message)s'
    )
    def get_logger(name):
        return logging.getLogger(name)

# このモジュール用のロガーを取得
logger = get_logger(__name__)


# =============================================================================
# 定数定義
# =============================================================================

# APIリトライ設定
MAX_RETRIES = 3
RETRY_DELAY_SECONDS = 1.0


# =============================================================================
# 例外クラス
# =============================================================================

class LLMConfigError(Exception):
    """
    LLM設定エラーを表すカスタム例外

    【発生条件】
    - LLM_PROVIDER環境変数が未設定
    - LLM_PROVIDERの値が不正（対応プロバイダー以外）
    - 必要な環境変数が不足している

    【使い方】
    ```python
    try:
        llm = LLMFactory.create_chat_model()
    except LLMConfigError as e:
        print(f"LLM設定エラー: {e}")
        # エラーメッセージには解決方法のヒントが含まれています
    ```

    【属性】
    - message: エラーメッセージ（解決方法のヒント付き）
    - provider: エラーが発生したプロバイダー（オプション）
    - missing_vars: 不足している環境変数のリスト（オプション）
    """

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        missing_vars: Optional[List[str]] = None
    ):
        """
        初期化

        Args:
            message: エラーメッセージ
            provider: プロバイダー名（オプション）
            missing_vars: 不足している環境変数リスト（オプション）
        """
        super().__init__(message)
        self.provider = provider
        self.missing_vars = missing_vars or []

    def __str__(self) -> str:
        """文字列表現"""
        return self.args[0]


# =============================================================================
# LLMプロバイダー列挙型
# =============================================================================

class LLMProvider(Enum):
    """
    対応LLMプロバイダーの列挙型

    【列挙型（Enum）とは】
    関連する定数をグループ化するための仕組みです。
    文字列リテラルの代わりに使用することで、
    タイプミスを防ぎ、IDEの補完機能が使えます。

    【各プロバイダーの特徴】
    ┌──────────────────┬─────────────────────────────────────────────┐
    │ AZURE            │ 企業向けOpenAI、SLA保証、リージョン指定可能 │
    │ AZURE_FOUNDRY    │ 複数モデル対応、統合管理、モデルカタログ    │
    │ GCP              │ Gemini、Google検索連携、マルチモーダル      │
    │ AWS              │ Claude、既存AWSサービスとの統合、IAM連携    │
    │ LOCAL            │ Ollama、ローカル実行、プライバシー重視      │
    └──────────────────┴─────────────────────────────────────────────┘

    【使用例】
    ```python
    # プロバイダーの比較
    if provider == LLMProvider.AZURE:
        print("Azure OpenAIを使用")

    # 文字列との変換
    provider = LLMProvider("AZURE")  # 文字列から列挙型へ
    name = provider.value            # 列挙型から文字列へ ("AZURE")
    ```
    """
    AZURE = "AZURE"                    # Azure OpenAI Service
    AZURE_FOUNDRY = "AZURE_FOUNDRY"    # Azure AI Foundry
    GCP = "GCP"                        # Google Cloud Vertex AI
    AWS = "AWS"                        # Amazon Bedrock
    LOCAL = "LOCAL"                    # Ollama (ローカルLLM)


# =============================================================================
# メインクラス: LLMFactory
# =============================================================================

class LLMFactory:
    """
    LLMファクトリークラス（LLMインスタンスの生成を担当）

    【ファクトリーパターンとは】
    オブジェクトの生成ロジックを一箇所に集約するデザインパターンです。
    利用者は生成の詳細を知らなくても、インスタンスを取得できます。

    【このクラスの役割】
    1. 環境変数からプロバイダーを自動検出
    2. プロバイダー固有の設定を検証
    3. 適切なLangChainモデルを初期化
    4. 設定済みのLLMインスタンスを返却

    【主なメソッド】
    - create_chat_model(): テキスト処理用LLMを作成
    - create_vision_model(): 画像認識対応LLMを作成
    - get_config_status(): 現在の設定状態を確認
    - get_provider_info(): プロバイダー情報を取得

    【使用例】
    ```python
    # LLMを作成（プロバイダーは環境変数から自動検出）
    llm = LLMFactory.create_chat_model()

    # 設定状態を確認
    if LLMFactory.get_config_status()["configured"]:
        print("LLM設定完了")
    else:
        print("設定が不完全です")
    ```

    【クラスメソッド（@classmethod）について】
    このクラスのメソッドはすべて@classmethodで定義されています。
    これは、インスタンスを作成せずに直接呼び出せることを意味します：
    - ○ LLMFactory.create_chat_model()  # 正しい
    - × factory = LLMFactory(); factory.create_chat_model()  # 不要
    """

    # =========================================================================
    # 定数定義（クラス変数）
    # =========================================================================

    # -------------------------------------------------------------------------
    # 各プロバイダーの必須環境変数
    # -------------------------------------------------------------------------
    # これらの環境変数が設定されていないと、LLMを作成できません
    REQUIRED_ENV_VARS: Dict[LLMProvider, List[str]] = {
        LLMProvider.AZURE: [
            "AZURE_OPENAI_API_KEY",           # APIキー（認証用）
            "AZURE_OPENAI_ENDPOINT",          # エンドポイントURL
            "AZURE_OPENAI_DEPLOYMENT_NAME",   # デプロイメント名
        ],
        LLMProvider.AZURE_FOUNDRY: [
            "AZURE_FOUNDRY_ENDPOINT",         # Foundryエンドポイント
            "AZURE_FOUNDRY_API_KEY",          # APIキー
        ],
        LLMProvider.GCP: [
            "GCP_PROJECT_ID",                 # GCPプロジェクトID
            "GCP_LOCATION",                   # リージョン（例: us-central1）
        ],
        LLMProvider.AWS: [
            "AWS_REGION",                     # AWSリージョン（例: us-east-1）
        ],
        LLMProvider.LOCAL: [
            # Ollamaはデフォルトでlocalhost:11434で動作するため必須環境変数なし
            # OLLAMA_BASE_URLはオプション（カスタムエンドポイント用）
        ],
    }

    # -------------------------------------------------------------------------
    # デフォルトモデル（プロバイダー別）- 2026年2月最新
    # -------------------------------------------------------------------------
    # 明示的にモデルが指定されない場合に使用されるデフォルト値
    # Note: AWS Bedrockでは on-demand throughput には inference profile ID が必要
    DEFAULT_MODELS: Dict[LLMProvider, Optional[str]] = {
        LLMProvider.AZURE: None,  # Azure OpenAIはデプロイ名を使用
        LLMProvider.AZURE_FOUNDRY: "gpt-5-nano",  # GPT-5 Nano (動作確認済み)
        LLMProvider.GCP: "gemini-2.5-flash",  # Gemini 2.5 Flash (動作確認済み)
        LLMProvider.AWS: "jp.anthropic.claude-sonnet-4-5-20250929-v1:0",  # Claude Sonnet 4.5 JP (動作確認済み)
        LLMProvider.LOCAL: "llama3.2:8b",      # Llama 3.2 8B (Ollama)
    }

    # -------------------------------------------------------------------------
    # コスト重視モデル（プロバイダー別）- 2026年2月最新
    # -------------------------------------------------------------------------
    # 低コスト・高速応答を優先する場合に使用
    COST_EFFECTIVE_MODELS: Dict[LLMProvider, Optional[str]] = {
        LLMProvider.AZURE: None,
        LLMProvider.AZURE_FOUNDRY: "gpt-5-nano",        # GPT-5 Nano (高速・低コスト)
        LLMProvider.GCP: "gemini-2.5-flash-lite",       # Gemini 2.5 Flash Lite (動作確認済み)
        LLMProvider.AWS: "anthropic.claude-3-haiku-20240307-v1:0",  # Claude 3 Haiku
        LLMProvider.LOCAL: "phi4:3.8b",                 # Phi-4 3.8B (超軽量)
    }

    # -------------------------------------------------------------------------
    # ハイエンドモデル（プロバイダー別）- 2026年2月最新
    # -------------------------------------------------------------------------
    # 最高精度を求める場合に使用（コスト高）
    # Note: AWS Bedrockでは on-demand throughput には inference profile ID が必要
    HIGH_END_MODELS: Dict[LLMProvider, Optional[str]] = {
        LLMProvider.AZURE: None,
        LLMProvider.AZURE_FOUNDRY: "gpt-5-nano",        # GPT-5 Nano (デプロイ済み)
        LLMProvider.GCP: "gemini-2.5-pro",              # Gemini 2.5 Pro (動作確認済み)
        LLMProvider.AWS: "global.anthropic.claude-opus-4-6-v1",  # Claude Opus 4.6 (動作確認済み)
        LLMProvider.LOCAL: "llama3.2:70b",              # Llama 3.2 70B
    }

    # -------------------------------------------------------------------------
    # 画像認識対応モデル - 2026年2月最新
    # -------------------------------------------------------------------------
    # Vision（画像認識）機能をサポートするモデル
    VISION_MODELS: Dict[LLMProvider, Optional[str]] = {
        LLMProvider.AZURE: None,  # Visionデプロイまたはデフォルト
        LLMProvider.AZURE_FOUNDRY: "gpt-5-nano",        # GPT-5 NanoはVision対応
        LLMProvider.GCP: "gemini-2.5-flash",            # Gemini 2.5はネイティブでVision対応（動作確認済み）
        LLMProvider.AWS: "anthropic.claude-3-sonnet-20240229-v1:0",  # Claude 3 Sonnet Vision対応
        LLMProvider.LOCAL: "llava:34b",                 # LLaVA 34B (Vision対応、Ollama)
    }

    # -------------------------------------------------------------------------
    # 利用可能なモデル一覧（プロバイダー別）
    # -------------------------------------------------------------------------
    AVAILABLE_MODELS: Dict[LLMProvider, Dict[str, str]] = {
        LLMProvider.AZURE_FOUNDRY: {
            # GPT-5.2 シリーズ (2026年1月〜)
            "gpt-5.2": "GPT-5.2 - 企業エージェント・コーディング向けフラッグシップ",
            "gpt-5.2-codex": "GPT-5.2 Codex - コード特化モデル",
            # GPT-5.1 シリーズ
            "gpt-5.1": "GPT-5.1 - 推論機能付きモデル",
            "gpt-5.1-chat": "GPT-5.1 Chat - 推論機能付き会話モデル",
            # GPT-5 シリーズ
            "gpt-5": "GPT-5 - ロジック・マルチステップタスク向け",
            "gpt-5-chat": "GPT-5 Chat - 会話・マルチモーダル向け",
            "gpt-5-mini": "GPT-5 Mini - 軽量版",
            "gpt-5-nano": "GPT-5 Nano - 高速・低レイテンシ向け",
            "gpt-5-codex": "GPT-5 Codex - コード特化",
            # レガシー
            "gpt-4o": "GPT-4o - 旧世代フラッグシップ",
            "gpt-4o-mini": "GPT-4o Mini - 旧世代軽量版",
            # Claude モデル (Anthropic via Microsoft Foundry)
            "claude-opus-4-6": "Claude Opus 4.6 - Anthropic最高性能（エージェントチーム、1Mトークン）",
            "claude-opus-4-5": "Claude Opus 4.5 - Anthropic高性能モデル",
            "claude-sonnet-4-5": "Claude Sonnet 4.5 - Anthropicバランス型",
            "claude-haiku-4-5": "Claude Haiku 4.5 - Anthropic高速・低コスト",
        },
        LLMProvider.GCP: {
            # Gemini 3.x シリーズ (Preview - 申請が必要)
            "gemini-3-pro-preview": "Gemini 3 Pro - 高度な推論・エージェント向け（Preview）",
            "gemini-3-flash-preview": "Gemini 3 Flash - 高速・マルチモーダル（Preview）",
            # Gemini 2.5 シリーズ (GA - 動作確認済み)
            "gemini-2.5-pro": "Gemini 2.5 Pro - 高度な推論・コーディング（動作確認済み）",
            "gemini-2.5-flash": "Gemini 2.5 Flash - 高速・コスト効率（動作確認済み・推奨）",
            "gemini-2.5-flash-lite": "Gemini 2.5 Flash Lite - 超軽量（動作確認済み）",
            # Gemini 2.0 シリーズ (Legacy - 2026/3/31廃止予定)
            "gemini-2.0-flash-001": "Gemini 2.0 Flash - レガシー（2026/3/31廃止予定）",
        },
        LLMProvider.AWS: {
            # Claude Opus 4.x シリーズ (2026年〜)
            # Note: on-demand throughput には inference profile ID が必要
            #       global.* = グローバル推論プロファイル
            #       jp.* = 日本リージョン推論プロファイル
            "global.anthropic.claude-opus-4-6-v1": "Claude Opus 4.6 - 最高性能モデル（動作確認済み）",
            "global.anthropic.claude-opus-4-5-20251101-v1:0": "Claude Opus 4.5 - 高性能モデル（動作確認済み）",
            "global.anthropic.claude-sonnet-4-5-v1": "Claude Sonnet 4.5 - バランス型",
            "global.anthropic.claude-haiku-4-5-v1": "Claude Haiku 4.5 - 高速・低コスト",
            # JP リージョン inference profile
            "jp.anthropic.claude-sonnet-4-5-20250929-v1:0": "Claude Sonnet 4.5 (JP) - 日本リージョン（動作確認済み）",
            # レガシー（Vision対応）
            "anthropic.claude-3-sonnet-20240229-v1:0": "Claude 3 Sonnet - Vision対応",
            "anthropic.claude-3-haiku-20240307-v1:0": "Claude 3 Haiku - 高速・低コスト",
        },
        LLMProvider.LOCAL: {
            "llama3.2:8b": "Llama 3.2 8B - バランス型",
            "llama3.2:70b": "Llama 3.2 70B - 高精度",
            "phi4:3.8b": "Phi-4 3.8B - 超軽量",
            "mistral:7b": "Mistral 7B - 軽量高速",
            "llava:34b": "LLaVA 34B - Vision対応",
        },
    }

    # -------------------------------------------------------------------------
    # temperatureパラメータ非対応モデル
    # -------------------------------------------------------------------------
    # これらのモデル（主に推論系）はtemperatureパラメータを受け付けません
    # temperatureを渡すとエラーになるため、自動的にスキップします
    MODELS_WITHOUT_TEMPERATURE: List[str] = [
        # GPT-5.x 推論系
        "gpt-5-nano",
        "gpt-5.1",
        "gpt-5.1-chat",
        # o シリーズ
        "o1",
        "o1-mini",
        "o1-preview",
        "o3",
        "o3-mini",
        # その他推論モデル
        "deepseek-r1",
    ]

    # =========================================================================
    # プロバイダー取得・検証メソッド
    # =========================================================================

    @classmethod
    def get_provider(cls) -> LLMProvider:
        """
        設定されているLLMプロバイダーを取得する

        【処理の流れ】
        1. 環境変数 LLM_PROVIDER の値を読み取る
        2. 値が空の場合はエラーを発生
        3. 対応プロバイダーに変換して返す

        Returns:
            LLMProvider: 設定されているプロバイダー

        Raises:
            LLMConfigError: LLM_PROVIDERが未設定または不正な場合

        【使用例】
        ```python
        try:
            provider = LLMFactory.get_provider()
            print(f"使用プロバイダー: {provider.value}")
        except LLMConfigError as e:
            print(f"プロバイダー取得エラー: {e}")
        ```
        """
        logger.debug("[LLMFactory] プロバイダー取得開始")

        # 環境変数を読み取り（大文字に正規化）
        provider_str = os.getenv("LLM_PROVIDER", "").upper().strip()

        # 未設定の場合
        if not provider_str:
            error_msg = (
                "LLM_PROVIDER環境変数が設定されていません。\n"
                "\n"
                "【対応プロバイダー】\n"
                "  AZURE         - Azure OpenAI Service\n"
                "  AZURE_FOUNDRY - Azure AI Foundry\n"
                "  GCP           - Google Cloud Vertex AI\n"
                "  AWS           - Amazon Bedrock\n"
                "  LOCAL         - Ollama (ローカルLLM)\n"
                "\n"
                "【設定方法】\n"
                "  環境変数: export LLM_PROVIDER=AZURE_FOUNDRY\n"
                "  .envファイル: LLM_PROVIDER=AZURE_FOUNDRY"
            )
            logger.error(f"[LLMFactory] {error_msg}")
            raise LLMConfigError(error_msg)

        # プロバイダー名の検証と変換
        try:
            provider = LLMProvider(provider_str)
            logger.info(f"[LLMFactory] プロバイダー検出: {provider.value}")
            return provider

        except ValueError:
            # 不正なプロバイダー名
            valid_providers = ", ".join(p.value for p in LLMProvider)
            error_msg = (
                f"不正なLLM_PROVIDER: '{provider_str}'\n"
                f"\n"
                f"【対応プロバイダー】\n"
                f"  {valid_providers}\n"
                f"\n"
                f"スペルミスがないか確認してください。"
            )
            logger.error(f"[LLMFactory] {error_msg}")
            raise LLMConfigError(error_msg, provider=provider_str)

    @classmethod
    def validate_config(cls, provider: LLMProvider) -> None:
        """
        プロバイダー設定を検証する

        指定されたプロバイダーに必要な環境変数が
        すべて設定されているかを確認します。

        【検証内容】
        - 必須環境変数がすべて設定されているか
        - 値が空文字でないか

        Args:
            provider: 検証するプロバイダー

        Raises:
            LLMConfigError: 必須環境変数が不足している場合

        【使用例】
        ```python
        try:
            LLMFactory.validate_config(LLMProvider.AZURE)
            print("設定OK")
        except LLMConfigError as e:
            print(f"設定エラー: {e}")
        ```
        """
        logger.debug(f"[LLMFactory] 設定検証開始: {provider.value}")

        # 必須環境変数を取得
        required_vars = cls.REQUIRED_ENV_VARS.get(provider, [])
        missing_vars = []

        # 各環境変数をチェック
        for var in required_vars:
            value = os.getenv(var, "").strip()
            if not value:
                missing_vars.append(var)
                logger.debug(f"[LLMFactory] 環境変数未設定: {var}")
            else:
                # APIキーは最初の数文字だけログに出力（セキュリティ対策）
                if "KEY" in var or "SECRET" in var:
                    logger.debug(f"[LLMFactory] 環境変数設定済み: {var} = ****{value[-4:]}")
                else:
                    logger.debug(f"[LLMFactory] 環境変数設定済み: {var} = {value[:50]}...")

        # 不足がある場合はエラー
        if missing_vars:
            error_msg = (
                f"{provider.value}に必要な環境変数が不足しています。\n"
                f"\n"
                f"【不足している環境変数】\n"
                f"  {', '.join(missing_vars)}\n"
                f"\n"
                f"【設定方法】\n"
                f"  1. 環境変数として設定\n"
                f"  2. .envファイルに記述\n"
                f"  3. setting.jsonに設定（推奨）\n"
                f"\n"
                f"詳細は .env.example または setting.json.example を参照してください。"
            )
            logger.error(f"[LLMFactory] 環境変数不足: {missing_vars}")
            raise LLMConfigError(error_msg, provider=provider.value, missing_vars=missing_vars)

        logger.info(f"[LLMFactory] 設定検証完了: {provider.value} (OK)")

    # =========================================================================
    # LLMインスタンス作成メソッド
    # =========================================================================

    @classmethod
    def create_chat_model(
        cls,
        temperature: float = 0.0,
        model: Optional[str] = None,
        **kwargs
    ):
        """
        チャットモデル（テキスト処理用LLM）を作成する

        【処理の流れ】
        1. プロバイダーを取得（環境変数から）
        2. 設定を検証
        3. プロバイダー固有のモデルを作成
        4. LangChainのChatModelインスタンスを返す

        Args:
            temperature: 生成の多様性を制御するパラメータ
                - 0.0: 決定論的（常に同じ出力）
                - 0.7: バランス
                - 1.0: 創造的（多様な出力）
            model: モデル名の上書き（省略時はデフォルトを使用）
            **kwargs: プロバイダー固有の追加パラメータ

        Returns:
            ChatModel: LangChainチャットモデルインスタンス
                - AzureChatOpenAI (Azure / Azure Foundry)
                - ChatVertexAI (GCP)
                - ChatBedrock (AWS)

        Raises:
            LLMConfigError: 設定エラー時
            ImportError: 必要なライブラリがない場合

        【使用例】
        ```python
        # デフォルト設定で作成（temperature=0.0）
        llm = LLMFactory.create_chat_model()

        # カスタム設定で作成
        llm = LLMFactory.create_chat_model(
            temperature=0.7,
            model="gpt-4o-mini"
        )

        # LangChain形式で呼び出し
        response = llm.invoke("Hello, world!")
        print(response.content)
        ```

        【temperatureについて】
        内部統制テストでは、結果の一貫性が重要なため、
        temperature=0.0（決定論的）を推奨します。
        """
        start_time = time.time()

        # プロバイダーを取得・検証
        provider = cls.get_provider()
        cls.validate_config(provider)

        logger.info(
            f"[LLMFactory] チャットモデル作成開始: "
            f"プロバイダー={provider.value}, "
            f"temperature={temperature}, "
            f"model={model or 'default'}"
        )

        try:
            # プロバイダー別にモデルを作成
            if provider == LLMProvider.AZURE:
                llm = cls._create_azure_model(temperature, model, **kwargs)
            elif provider == LLMProvider.AZURE_FOUNDRY:
                llm = cls._create_azure_foundry_model(temperature, model, **kwargs)
            elif provider == LLMProvider.GCP:
                llm = cls._create_gcp_model(temperature, model, **kwargs)
            elif provider == LLMProvider.AWS:
                llm = cls._create_aws_model(temperature, model, **kwargs)
            elif provider == LLMProvider.LOCAL:
                llm = cls._create_local_model(temperature, model, **kwargs)
            else:
                # 通常到達しないが、念のため
                raise LLMConfigError(f"未対応のプロバイダー: {provider}")

            elapsed = time.time() - start_time
            logger.info(
                f"[LLMFactory] チャットモデル作成完了 ({elapsed:.2f}秒)"
            )
            return llm

        except ImportError as e:
            # LangChainの依存ライブラリがない場合
            logger.error(
                f"[LLMFactory] 必要なライブラリがインストールされていません: {e}"
            )
            logger.info(
                f"[LLMFactory] 以下のコマンドでインストールしてください:\n"
                f"  pip install langchain-openai  (Azure/Azure Foundry用)\n"
                f"  pip install langchain-google-vertexai  (GCP用)\n"
                f"  pip install langchain-aws  (AWS用)"
            )
            raise

        except Exception as e:
            # その他のエラー
            logger.error(
                f"[LLMFactory] チャットモデル作成エラー: {type(e).__name__}: {e}"
            )
            logger.debug(f"[LLMFactory] トレースバック:\n{traceback.format_exc()}")
            raise

    @classmethod
    def _create_azure_model(
        cls,
        temperature: float,
        model: Optional[str],
        **kwargs
    ):
        """
        Azure OpenAI ChatModelを作成する（内部メソッド）

        【Azure OpenAI Serviceとは】
        MicrosoftがAzure上で提供するOpenAI APIのマネージドサービスです。
        エンタープライズ向けのセキュリティとコンプライアンスが特徴です。

        Args:
            temperature: 生成の多様性
            model: デプロイ名の上書き
            **kwargs: 追加パラメータ

        Returns:
            AzureChatOpenAI: Azure OpenAIチャットモデル
        """
        logger.debug("[LLMFactory] Azure OpenAIモデル作成開始")

        # LangChainのAzureモジュールをインポート
        from langchain_openai import AzureChatOpenAI

        # 環境変数から設定を取得
        endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
        api_key = os.getenv("AZURE_OPENAI_API_KEY")
        api_version = os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview")
        deployment = model or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")

        logger.debug(
            f"[LLMFactory] Azure OpenAI設定: "
            f"endpoint={endpoint[:30]}..., "
            f"deployment={deployment}, "
            f"api_version={api_version}"
        )

        # モデルを作成
        llm = AzureChatOpenAI(
            azure_endpoint=endpoint,
            api_key=api_key,
            api_version=api_version,
            deployment_name=deployment,
            temperature=temperature,
            **kwargs
        )

        logger.info(f"[LLMFactory] Azure OpenAIモデル作成完了: {deployment}")
        return llm

    @classmethod
    def _create_azure_foundry_model(
        cls,
        temperature: float,
        model: Optional[str],
        **kwargs
    ):
        """
        Azure AI Foundry ChatModelを作成する（内部メソッド）

        【Azure AI Foundryとは】
        Microsoftの統合AIプラットフォームです。
        OpenAIモデルに加えて、Phi、Mistral、LLaMAなど
        複数のモデルを統一的なAPIで利用できます。

        【エンドポイント形式】
        https://<project-name>.<region>.models.ai.azure.com

        Args:
            temperature: 生成の多様性
            model: モデル名の上書き
            **kwargs: 追加パラメータ

        Returns:
            AzureChatOpenAI: Azure AI Foundryチャットモデル

        Note:
            一部のモデル（o1シリーズ、DeepSeek-R1等）は
            temperatureパラメータ非対応です。
        """
        logger.debug("[LLMFactory] Azure AI Foundryモデル作成開始")

        from langchain_openai import AzureChatOpenAI

        # 環境変数から設定を取得
        endpoint = os.getenv("AZURE_FOUNDRY_ENDPOINT")
        api_key = os.getenv("AZURE_FOUNDRY_API_KEY")
        api_version = os.getenv("AZURE_FOUNDRY_API_VERSION", "2024-08-01-preview")
        model_name = model or os.getenv(
            "AZURE_FOUNDRY_MODEL",
            cls.DEFAULT_MODELS[LLMProvider.AZURE_FOUNDRY]
        )

        logger.debug(
            f"[LLMFactory] Azure AI Foundry設定: "
            f"endpoint={endpoint[:30]}..., "
            f"model={model_name}"
        )

        # モデルパラメータを構築
        model_kwargs = {
            "azure_endpoint": endpoint,
            "api_key": api_key,
            "api_version": api_version,
            "deployment_name": model_name,
            **kwargs
        }

        # temperatureパラメータ対応を確認
        # 一部のモデル（推論系）はtemperatureを受け付けない
        model_lower = model_name.lower() if model_name else ""
        is_temp_unsupported = any(m in model_lower for m in cls.MODELS_WITHOUT_TEMPERATURE)

        if not is_temp_unsupported:
            model_kwargs["temperature"] = temperature
        else:
            # temperature非対応モデルでも安定性を高めるためseedを設定
            # seedは再現可能な出力を促す（完全な再現は保証されない）
            # 環境変数LLM_SEEDで制御可能（デフォルト: 42）
            seed = int(os.getenv("LLM_SEED", "42"))
            model_kwargs["seed"] = seed  # LangChain推奨: 明示的パラメータとして指定
            logger.info(
                f"[LLMFactory] モデル '{model_name}' は "
                f"temperatureパラメータ非対応のためseed={seed}で安定化"
            )

        # モデルを作成
        llm = AzureChatOpenAI(**model_kwargs)

        logger.info(f"[LLMFactory] Azure AI Foundryモデル作成完了: {model_name}")
        return llm

    @classmethod
    def _create_gcp_model(
        cls,
        temperature: float,
        model: Optional[str],
        **kwargs
    ):
        """
        GCP Vertex AI ChatModelを作成する（内部メソッド）

        【Google Cloud Vertex AIとは】
        GoogleのマネージドAIプラットフォームです。
        Geminiモデルが利用可能で、Google検索との連携も可能です。

        【認証方法】
        - サービスアカウントキー（GOOGLE_APPLICATION_CREDENTIALS）
        - デフォルト認証（gcloud auth application-default login）

        Args:
            temperature: 生成の多様性
            model: モデル名の上書き
            **kwargs: 追加パラメータ

        Returns:
            ChatVertexAI: GCP Vertex AIチャットモデル
        """
        logger.debug("[LLMFactory] GCP Vertex AIモデル作成開始")

        from langchain_google_vertexai import ChatVertexAI

        # 環境変数から設定を取得
        project_id = os.getenv("GCP_PROJECT_ID")
        location = os.getenv("GCP_LOCATION", "us-central1")
        model_name = model or cls.DEFAULT_MODELS[LLMProvider.GCP]

        logger.debug(
            f"[LLMFactory] GCP Vertex AI設定: "
            f"project={project_id}, "
            f"location={location}, "
            f"model={model_name}"
        )

        # モデルを作成
        llm = ChatVertexAI(
            project=project_id,
            location=location,
            model_name=model_name,
            temperature=temperature,
            **kwargs
        )

        logger.info(f"[LLMFactory] GCP Vertex AIモデル作成完了: {model_name}")
        return llm

    @classmethod
    def _create_aws_model(
        cls,
        temperature: float,
        model: Optional[str],
        **kwargs
    ):
        """
        AWS Bedrock ChatModelを作成する（内部メソッド）

        【Amazon Bedrockとは】
        AWSの基盤モデルサービスです。
        Claude、Titan、Mistral等のモデルが利用可能です。

        【認証方法】
        - 環境変数（AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY）
        - プロファイル（AWS_PROFILE）
        - IAMロール（EC2、Lambda等で自動取得）

        Args:
            temperature: 生成の多様性
            model: モデルIDの上書き
            **kwargs: 追加パラメータ

        Returns:
            ChatBedrock: AWS Bedrockチャットモデル
        """
        logger.debug("[LLMFactory] AWS Bedrockモデル作成開始")

        from langchain_aws import ChatBedrock

        # 環境変数から設定を取得
        region = os.getenv("AWS_REGION", "us-east-1")
        profile = os.getenv("AWS_PROFILE")
        model_id = model or os.getenv("AWS_BEDROCK_MODEL_ID", cls.DEFAULT_MODELS[LLMProvider.AWS])

        logger.debug(
            f"[LLMFactory] AWS Bedrock設定: "
            f"region={region}, "
            f"profile={profile or 'default'}, "
            f"model={model_id}"
        )

        # モデルパラメータを構築
        bedrock_kwargs = {
            "region_name": region,
            "model_id": model_id,
            "model_kwargs": {
                "temperature": temperature,
                **kwargs.get("model_kwargs", {})
            },
        }

        # プロファイルが指定されている場合のみ追加（Lambda環境ではIAMロールを使用）
        if profile:
            bedrock_kwargs["credentials_profile_name"] = profile

        # モデルを作成
        llm = ChatBedrock(**bedrock_kwargs)

        logger.info(f"[LLMFactory] AWS Bedrockモデル作成完了: {model_id}")
        return llm

    @classmethod
    def _create_local_model(
        cls,
        temperature: float,
        model: Optional[str],
        **kwargs
    ):
        """
        Ollama (ローカルLLM) ChatModelを作成する（内部メソッド）

        【Ollamaとは】
        ローカル環境でLLMを実行するためのツールです。
        LLaMA、Mistral、Phi等のオープンソースモデルが利用可能です。

        【特徴】
        - プライバシー: データが外部に送信されない
        - オフライン: ネットワーク接続不要
        - 無料: 追加コストなし
        - カスタマイズ: モデルの微調整が可能

        【推奨モデル】
        - llama3.1:8b   : バランスの取れた汎用モデル
        - llama3.1:70b  : 高精度モデル（要高スペック）
        - mistral:7b    : 軽量高速モデル
        - phi3:3.8b     : 超軽量モデル
        - llava:13b     : Vision対応モデル

        【必要条件】
        - Ollamaがインストール・起動していること
        - 使用するモデルがpullされていること
          例: ollama pull llama3.1:8b

        Args:
            temperature: 生成の多様性
            model: モデル名の上書き
            **kwargs: 追加パラメータ

        Returns:
            ChatOllama: Ollamaチャットモデル
        """
        logger.debug("[LLMFactory] Ollamaモデル作成開始")

        from langchain_ollama import ChatOllama

        # 環境変数から設定を取得
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        model_name = model or os.getenv("OLLAMA_MODEL", cls.DEFAULT_MODELS[LLMProvider.LOCAL])

        logger.debug(
            f"[LLMFactory] Ollama設定: "
            f"base_url={base_url}, "
            f"model={model_name}"
        )

        # モデルを作成
        llm = ChatOllama(
            base_url=base_url,
            model=model_name,
            temperature=temperature,
            **kwargs
        )

        logger.info(f"[LLMFactory] Ollamaモデル作成完了: {model_name}")
        return llm

    # =========================================================================
    # Vision対応モデル作成メソッド
    # =========================================================================

    @classmethod
    def create_cost_effective_model(
        cls,
        temperature: float = 0.0,
        **kwargs
    ):
        """
        コスト重視モデルを作成する

        高速・低コストを優先する場合に使用します。
        処理速度が重要な場合や、大量のリクエストを処理する場合に推奨。

        Args:
            temperature: 生成の多様性
            **kwargs: 追加パラメータ

        Returns:
            ChatModel: コスト重視LLMインスタンス

        【対応モデル】
        - Azure: GPT-5 Nano
        - GCP: Gemini 3 Flash
        - AWS: Claude Haiku 4.5
        """
        provider = cls.get_provider()
        model = cls.COST_EFFECTIVE_MODELS.get(provider)
        logger.info(f"[LLMFactory] コスト重視モデル作成: {model}")
        return cls.create_chat_model(temperature=temperature, model=model, **kwargs)

    @classmethod
    def create_high_end_model(
        cls,
        temperature: float = 0.0,
        **kwargs
    ):
        """
        ハイエンドモデルを作成する

        最高精度を求める場合に使用します。
        複雑な推論や高品質な出力が必要な場合に推奨。

        Args:
            temperature: 生成の多様性
            **kwargs: 追加パラメータ

        Returns:
            ChatModel: ハイエンドLLMインスタンス

        【対応モデル】
        - Azure: GPT-5.2
        - GCP: Gemini 3 Pro
        - AWS: Claude Opus 4.6
        """
        provider = cls.get_provider()
        model = cls.HIGH_END_MODELS.get(provider)
        logger.info(f"[LLMFactory] ハイエンドモデル作成: {model}")
        return cls.create_chat_model(temperature=temperature, model=model, **kwargs)

    @classmethod
    def get_available_models(cls) -> Dict[str, str]:
        """
        現在のプロバイダーで利用可能なモデル一覧を取得する

        Returns:
            dict: モデルID -> 説明 のマッピング

        【使用例】
        ```python
        models = LLMFactory.get_available_models()
        for model_id, description in models.items():
            print(f"{model_id}: {description}")
        ```
        """
        try:
            provider = cls.get_provider()
            return cls.AVAILABLE_MODELS.get(provider, {})
        except LLMConfigError:
            return {}

    @classmethod
    def create_vision_model(cls, **kwargs):
        """
        画像認識対応モデルを作成する

        【Vision対応モデルとは】
        テキストだけでなく、画像も入力として受け取れるモデルです。
        内部統制テストでは、スキャンされた書類や図表の分析に使用します。

        【対応モデル】
        - Azure/Azure Foundry: GPT-4o, GPT-4V
        - GCP: Gemini 1.5 Pro/Flash
        - AWS: Claude 3シリーズ

        Args:
            **kwargs: 追加パラメータ（temperatureなど）

        Returns:
            ChatModel: Vision対応LLMインスタンス

        【使用例】
        ```python
        vision_llm = LLMFactory.create_vision_model()

        # 画像を含むメッセージを送信
        from langchain_core.messages import HumanMessage

        messages = [
            HumanMessage(content=[
                {"type": "text", "text": "この書類の内容を説明してください"},
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                }
            ])
        ]
        response = vision_llm.invoke(messages)
        print(response.content)
        ```
        """
        provider = cls.get_provider()
        logger.info(f"[LLMFactory] Vision対応モデル作成: プロバイダー={provider.value}")

        # 各プロバイダーのVision対応モデルを取得
        vision_models = {
            LLMProvider.AZURE: os.getenv(
                "AZURE_OPENAI_VISION_DEPLOYMENT",
                os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
            ),
            LLMProvider.AZURE_FOUNDRY: os.getenv(
                "AZURE_FOUNDRY_VISION_MODEL",
                os.getenv("AZURE_FOUNDRY_MODEL", cls.VISION_MODELS[LLMProvider.AZURE_FOUNDRY])
            ),
            LLMProvider.GCP: cls.VISION_MODELS[LLMProvider.GCP],
            LLMProvider.AWS: cls.VISION_MODELS[LLMProvider.AWS],
            LLMProvider.LOCAL: os.getenv(
                "OLLAMA_VISION_MODEL",
                cls.VISION_MODELS[LLMProvider.LOCAL]
            ),
        }

        selected_model = vision_models.get(provider)
        logger.debug(f"[LLMFactory] 選択されたVisionモデル: {selected_model}")

        return cls.create_chat_model(
            model=selected_model,
            **kwargs
        )

    # =========================================================================
    # 設定確認・デバッグメソッド
    # =========================================================================

    @classmethod
    def get_config_status(cls) -> Dict[str, Any]:
        """
        LLM設定状態を取得する

        現在の設定状態を辞書形式で返します。
        ヘルスチェックやデバッグに使用します。

        Returns:
            dict: 設定状態
                - provider: プロバイダー名（未設定の場合は"NOT_SET"）
                - configured: 設定完了フラグ（True/False）
                - missing_vars: 不足している環境変数リスト
                - model: 使用予定のモデル名

        【使用例】
        ```python
        status = LLMFactory.get_config_status()

        if status["configured"]:
            print(f"LLM設定OK: {status['provider']}")
        else:
            print(f"未設定の環境変数: {status['missing_vars']}")
        ```
        """
        logger.debug("[LLMFactory] 設定状態確認開始")

        # 初期値
        status = {
            "provider": "NOT_SET",
            "configured": False,
            "missing_vars": [],
            "model": None,
        }

        # プロバイダーを取得
        try:
            provider = cls.get_provider()
            status["provider"] = provider.value
        except LLMConfigError:
            logger.debug("[LLMFactory] プロバイダー未設定")
            return status

        # 必須環境変数をチェック
        required_vars = cls.REQUIRED_ENV_VARS.get(provider, [])
        for var in required_vars:
            if not os.getenv(var, "").strip():
                status["missing_vars"].append(var)

        # 設定完了フラグ
        status["configured"] = len(status["missing_vars"]) == 0

        # モデル名を取得
        if provider == LLMProvider.AZURE:
            status["model"] = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        elif provider == LLMProvider.AZURE_FOUNDRY:
            status["model"] = os.getenv(
                "AZURE_FOUNDRY_MODEL",
                cls.DEFAULT_MODELS[LLMProvider.AZURE_FOUNDRY]
            )
        else:
            status["model"] = cls.DEFAULT_MODELS.get(provider)

        logger.debug(f"[LLMFactory] 設定状態: {status}")
        return status

    @classmethod
    def get_provider_info(cls) -> Dict[str, Dict[str, Any]]:
        """
        対応プロバイダー情報を取得する

        全対応プロバイダーの詳細情報を返します。
        設定ガイダンスやヘルプ表示に使用します。

        Returns:
            dict: プロバイダー情報（キー: プロバイダー名）
                - name: 表示名
                - description: 説明
                - models: 対応モデル一覧
                - required_env_vars: 必須環境変数
                - optional_env_vars: オプション環境変数
                - documentation: ドキュメントURL

        【使用例】
        ```python
        info = LLMFactory.get_provider_info()

        for provider_name, details in info.items():
            print(f"=== {details['name']} ===")
            print(f"説明: {details['description']}")
            print(f"必須環境変数: {details['required_env_vars']}")
            print()
        ```
        """
        return {
            "AZURE": {
                "name": "Azure OpenAI Service",
                "description": "MicrosoftのマネージドOpenAIサービス。企業向けSLA保証あり。",
                "models": ["gpt-5.2", "gpt-5", "gpt-5-nano", "gpt-4o"],
                "required_env_vars": cls.REQUIRED_ENV_VARS[LLMProvider.AZURE],
                "optional_env_vars": [
                    "AZURE_OPENAI_API_VERSION",
                    "AZURE_OPENAI_VISION_DEPLOYMENT"
                ],
                "documentation": "https://learn.microsoft.com/azure/ai-services/openai/"
            },
            "AZURE_FOUNDRY": {
                "name": "Azure AI Foundry",
                "description": "Azure AI Foundry - 統合AIプラットフォーム。GPT-5.2、Phi-4、DeepSeek-R1等が利用可能。",
                "models": list(cls.AVAILABLE_MODELS.get(LLMProvider.AZURE_FOUNDRY, {}).keys()),
                "models_detail": cls.AVAILABLE_MODELS.get(LLMProvider.AZURE_FOUNDRY, {}),
                "high_end": cls.HIGH_END_MODELS[LLMProvider.AZURE_FOUNDRY],
                "cost_effective": cls.COST_EFFECTIVE_MODELS[LLMProvider.AZURE_FOUNDRY],
                "required_env_vars": cls.REQUIRED_ENV_VARS[LLMProvider.AZURE_FOUNDRY],
                "optional_env_vars": [
                    "AZURE_FOUNDRY_MODEL",
                    "AZURE_FOUNDRY_VISION_MODEL",
                    "AZURE_FOUNDRY_API_VERSION"
                ],
                "documentation": "https://ai.azure.com/"
            },
            "GCP": {
                "name": "Google Cloud Vertex AI",
                "description": "Google CloudのAIプラットフォーム。Gemini 3シリーズとマルチモーダル対応。",
                "models": list(cls.AVAILABLE_MODELS.get(LLMProvider.GCP, {}).keys()),
                "models_detail": cls.AVAILABLE_MODELS.get(LLMProvider.GCP, {}),
                "high_end": cls.HIGH_END_MODELS[LLMProvider.GCP],
                "cost_effective": cls.COST_EFFECTIVE_MODELS[LLMProvider.GCP],
                "required_env_vars": cls.REQUIRED_ENV_VARS[LLMProvider.GCP],
                "optional_env_vars": [
                    "GOOGLE_APPLICATION_CREDENTIALS"
                ],
                "documentation": "https://cloud.google.com/vertex-ai/docs"
            },
            "AWS": {
                "name": "Amazon Bedrock",
                "description": "AWSのマネージド基盤モデルサービス。Claude Opus 4.6が利用可能。",
                "models": list(cls.AVAILABLE_MODELS.get(LLMProvider.AWS, {}).keys()),
                "models_detail": cls.AVAILABLE_MODELS.get(LLMProvider.AWS, {}),
                "high_end": cls.HIGH_END_MODELS[LLMProvider.AWS],
                "cost_effective": cls.COST_EFFECTIVE_MODELS[LLMProvider.AWS],
                "required_env_vars": cls.REQUIRED_ENV_VARS[LLMProvider.AWS],
                "optional_env_vars": [
                    "AWS_ACCESS_KEY_ID",
                    "AWS_SECRET_ACCESS_KEY",
                    "AWS_PROFILE",
                    "AWS_BEDROCK_MODEL_ID"
                ],
                "documentation": "https://docs.aws.amazon.com/bedrock/"
            },
            "LOCAL": {
                "name": "Ollama (ローカルLLM)",
                "description": "ローカル環境で動作するLLM。プライバシー重視・オフライン対応。",
                "models": list(cls.AVAILABLE_MODELS.get(LLMProvider.LOCAL, {}).keys()),
                "models_detail": cls.AVAILABLE_MODELS.get(LLMProvider.LOCAL, {}),
                "high_end": cls.HIGH_END_MODELS[LLMProvider.LOCAL],
                "cost_effective": cls.COST_EFFECTIVE_MODELS[LLMProvider.LOCAL],
                "required_env_vars": cls.REQUIRED_ENV_VARS[LLMProvider.LOCAL],
                "optional_env_vars": [
                    "OLLAMA_BASE_URL",
                    "OLLAMA_MODEL",
                    "OLLAMA_VISION_MODEL"
                ],
                "documentation": "https://ollama.ai/"
            }
        }


# =============================================================================
# モジュール情報
# =============================================================================

# 公開する名前を明示的に定義
__all__ = [
    # メインクラス
    "LLMFactory",
    # 例外クラス
    "LLMConfigError",
    # 列挙型
    "LLMProvider",
]
