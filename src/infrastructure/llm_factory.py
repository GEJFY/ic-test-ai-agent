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
    }

    # -------------------------------------------------------------------------
    # デフォルトモデル（プロバイダー別）
    # -------------------------------------------------------------------------
    # 明示的にモデルが指定されない場合に使用されるデフォルト値
    DEFAULT_MODELS: Dict[LLMProvider, Optional[str]] = {
        LLMProvider.AZURE: None,  # Azure OpenAIはデプロイ名を使用
        LLMProvider.AZURE_FOUNDRY: "gpt-4o",
        LLMProvider.GCP: "gemini-1.5-pro",
        LLMProvider.AWS: "anthropic.claude-3-5-sonnet-20241022-v2:0",
    }

    # -------------------------------------------------------------------------
    # 画像認識対応モデル
    # -------------------------------------------------------------------------
    # Vision（画像認識）機能をサポートするモデル
    VISION_MODELS: Dict[LLMProvider, Optional[str]] = {
        LLMProvider.AZURE: None,  # Visionデプロイまたはデフォルト
        LLMProvider.AZURE_FOUNDRY: "gpt-4o",    # GPT-4oはVision対応
        LLMProvider.GCP: "gemini-1.5-pro",      # GeminiはネイティブでVision対応
        LLMProvider.AWS: "anthropic.claude-3-5-sonnet-20241022-v2:0",  # Claude 3はVision対応
    }

    # -------------------------------------------------------------------------
    # temperatureパラメータ非対応モデル
    # -------------------------------------------------------------------------
    # これらのモデル（主に推論系）はtemperatureパラメータを受け付けません
    # temperatureを渡すとエラーになるため、自動的にスキップします
    MODELS_WITHOUT_TEMPERATURE: List[str] = [
        "gpt-5-nano",
        "o1",
        "o1-mini",
        "o1-preview",
        "deepseek-r1",  # 推論モデル
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
        if not any(m in model_lower for m in cls.MODELS_WITHOUT_TEMPERATURE):
            model_kwargs["temperature"] = temperature
        else:
            logger.info(
                f"[LLMFactory] モデル '{model_name}' は "
                f"temperatureパラメータ非対応のためスキップ"
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
        model_id = model or cls.DEFAULT_MODELS[LLMProvider.AWS]

        logger.debug(
            f"[LLMFactory] AWS Bedrock設定: "
            f"region={region}, "
            f"profile={profile or 'default'}, "
            f"model={model_id}"
        )

        # モデルを作成
        llm = ChatBedrock(
            region_name=region,
            model_id=model_id,
            model_kwargs={
                "temperature": temperature,
                **kwargs.get("model_kwargs", {})
            },
            credentials_profile_name=profile,
        )

        logger.info(f"[LLMFactory] AWS Bedrockモデル作成完了: {model_id}")
        return llm

    # =========================================================================
    # Vision対応モデル作成メソッド
    # =========================================================================

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
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-35-turbo"],
                "required_env_vars": cls.REQUIRED_ENV_VARS[LLMProvider.AZURE],
                "optional_env_vars": [
                    "AZURE_OPENAI_API_VERSION",
                    "AZURE_OPENAI_VISION_DEPLOYMENT"
                ],
                "documentation": "https://learn.microsoft.com/azure/ai-services/openai/"
            },
            "AZURE_FOUNDRY": {
                "name": "Azure AI Foundry",
                "description": "Azure AI Foundry - 統合AIプラットフォーム。モデルカタログから多様なモデルを選択可能。",
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "Phi-4", "DeepSeek-R1", "Mistral"],
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
                "description": "Google CloudのAIプラットフォーム。Geminiモデルとマルチモーダル対応。",
                "models": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash-exp"],
                "required_env_vars": cls.REQUIRED_ENV_VARS[LLMProvider.GCP],
                "optional_env_vars": [
                    "GOOGLE_APPLICATION_CREDENTIALS"
                ],
                "documentation": "https://cloud.google.com/vertex-ai/docs"
            },
            "AWS": {
                "name": "Amazon Bedrock",
                "description": "AWSのマネージド基盤モデルサービス。Claude、Titan等が利用可能。",
                "models": [
                    "anthropic.claude-3-5-sonnet-20241022-v2:0",
                    "anthropic.claude-3-haiku-20240307-v1:0",
                    "amazon.titan-text-express-v1"
                ],
                "required_env_vars": cls.REQUIRED_ENV_VARS[LLMProvider.AWS],
                "optional_env_vars": [
                    "AWS_ACCESS_KEY_ID",
                    "AWS_SECRET_ACCESS_KEY",
                    "AWS_PROFILE"
                ],
                "documentation": "https://docs.aws.amazon.com/bedrock/"
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
