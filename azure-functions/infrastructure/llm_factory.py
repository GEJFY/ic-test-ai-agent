"""
================================================================================
llm_factory.py - LLMファクトリー（クラウドLLMプロバイダー）
================================================================================

【概要】
複数のクラウドLLMプロバイダーに対応したLLMインスタンス生成ファクトリーです。
環境変数の設定に基づいて適切なプロバイダーのLLMを自動的に選択・作成します。

【対応プロバイダー】
- AZURE: Azure OpenAI Service（Microsoft）
- AZURE_FOUNDRY: Azure AI Foundry（統合AIプラットフォーム）
- GCP: Google Cloud Vertex AI（Gemini）
- AWS: Amazon Bedrock（Claude等）

【使用例】
```python
from infrastructure.llm_factory import LLMFactory

# テキスト処理用LLMを作成
llm = LLMFactory.create_chat_model(temperature=0.0)

# 画像認識用LLMを作成
vision_llm = LLMFactory.create_vision_model(temperature=0.0)

# 設定状態を確認
status = LLMFactory.get_config_status()
print(f"プロバイダー: {status['provider']}")
print(f"設定完了: {status['configured']}")
```

【環境変数の設定例】
```bash
# Azure OpenAI の場合
export LLM_PROVIDER=AZURE
export AZURE_OPENAI_API_KEY=your-api-key
export AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
export AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4o

# Azure AI Foundry の場合
export LLM_PROVIDER=AZURE_FOUNDRY
export AZURE_FOUNDRY_ENDPOINT=https://project.region.models.ai.azure.com
export AZURE_FOUNDRY_API_KEY=your-api-key
export AZURE_FOUNDRY_MODEL=gpt-4o
```

================================================================================
"""
import os
import logging
from typing import Optional
from enum import Enum

# =============================================================================
# ログ設定
# =============================================================================

logger = logging.getLogger(__name__)


# =============================================================================
# LLMプロバイダー定義
# =============================================================================

class LLMProvider(Enum):
    """
    対応LLMプロバイダー（主要クラウドプラットフォーム）

    各プロバイダーの特徴:
    - AZURE: 企業向けOpenAI、SLA保証あり
    - AZURE_FOUNDRY: 複数モデル対応、統合管理
    - GCP: Gemini、Google検索連携可能
    - AWS: Claude、既存AWSサービスとの統合
    """
    AZURE = "AZURE"                    # Azure OpenAI Service
    AZURE_FOUNDRY = "AZURE_FOUNDRY"    # Azure AI Foundry
    GCP = "GCP"                        # Google Cloud Vertex AI
    AWS = "AWS"                        # Amazon Bedrock


class LLMConfigError(Exception):
    """
    LLM設定エラー

    必要な環境変数が設定されていない場合や、
    不正なプロバイダーが指定された場合に発生します。
    """
    pass


# =============================================================================
# メインクラス: LLMFactory
# =============================================================================

class LLMFactory:
    """
    LLMファクトリークラス

    環境変数の設定に基づいてLLMインスタンスを生成します。
    Azure OpenAI、Azure AI Foundry、GCP Vertex AI、AWS Bedrockに対応。

    【主な機能】
    - 環境変数からプロバイダーを自動検出
    - プロバイダー固有の設定検証
    - テキスト処理用LLMの作成
    - 画像認識用LLMの作成
    - 設定状態の確認

    【処理フロー】
    1. LLM_PROVIDER環境変数を確認
    2. プロバイダー固有の必須環境変数を検証
    3. 対応するLangChainモデルを初期化
    4. 設定済みのLLMインスタンスを返却

    Attributes:
        REQUIRED_ENV_VARS: 各プロバイダーの必須環境変数
        DEFAULT_MODELS: 各プロバイダーのデフォルトモデル
        VISION_MODELS: 画像認識対応モデル

    使用例:
        ```python
        # LLMを作成
        llm = LLMFactory.create_chat_model()

        # 設定状態を確認
        if LLMFactory.get_config_status()["configured"]:
            print("LLM設定完了")
        ```
    """

    # =========================================================================
    # 定数定義
    # =========================================================================

    # 各プロバイダーの必須環境変数
    REQUIRED_ENV_VARS = {
        LLMProvider.AZURE: [
            "AZURE_OPENAI_API_KEY",           # APIキー
            "AZURE_OPENAI_ENDPOINT",          # エンドポイントURL
            "AZURE_OPENAI_DEPLOYMENT_NAME",   # デプロイ名
        ],
        LLMProvider.AZURE_FOUNDRY: [
            "AZURE_FOUNDRY_ENDPOINT",         # Foundryエンドポイント
            "AZURE_FOUNDRY_API_KEY",          # APIキー
        ],
        LLMProvider.GCP: [
            "GCP_PROJECT_ID",                 # GCPプロジェクトID
            "GCP_LOCATION",                   # リージョン
        ],
        LLMProvider.AWS: [
            "AWS_REGION",                     # AWSリージョン
        ],
    }

    # デフォルトモデル（プロバイダー別）
    DEFAULT_MODELS = {
        LLMProvider.AZURE: None,  # デプロイ名を使用
        LLMProvider.AZURE_FOUNDRY: "gpt-4o",
        LLMProvider.GCP: "gemini-1.5-pro",
        LLMProvider.AWS: "anthropic.claude-3-5-sonnet-20241022-v2:0",
    }

    # 画像認識対応モデル
    VISION_MODELS = {
        LLMProvider.AZURE: None,  # Visionデプロイまたはデフォルト
        LLMProvider.AZURE_FOUNDRY: "gpt-4o",  # GPT-4oはVision対応
        LLMProvider.GCP: "gemini-1.5-pro",    # GeminiはネイティブでVision対応
        LLMProvider.AWS: "anthropic.claude-3-5-sonnet-20241022-v2:0",  # ClaudeはVision対応
    }

    # temperatureパラメータ非対応モデル（推論系モデル）
    MODELS_WITHOUT_TEMPERATURE = ["gpt-5-nano", "o1", "o1-mini", "o1-preview"]

    # =========================================================================
    # プロバイダー取得・検証
    # =========================================================================

    @classmethod
    def get_provider(cls) -> LLMProvider:
        """
        設定されているLLMプロバイダーを取得

        環境変数 LLM_PROVIDER の値を読み取り、
        対応するLLMProviderを返します。

        Returns:
            LLMProvider: 設定されているプロバイダー

        Raises:
            LLMConfigError: LLM_PROVIDERが未設定または不正な場合
        """
        provider_str = os.getenv("LLM_PROVIDER", "").upper()

        if not provider_str:
            logger.error("[LLMFactory] LLM_PROVIDER環境変数が設定されていません")
            raise LLMConfigError(
                "LLM_PROVIDER環境変数が設定されていません。\n"
                "以下のいずれかを設定してください: AZURE, AZURE_FOUNDRY, GCP, AWS\n\n"
                "設定例:\n"
                "  export LLM_PROVIDER=AZURE_FOUNDRY"
            )

        try:
            provider = LLMProvider(provider_str)
            logger.debug(f"[LLMFactory] プロバイダー検出: {provider.value}")
            return provider
        except ValueError:
            logger.error(f"[LLMFactory] 不正なプロバイダー: {provider_str}")
            raise LLMConfigError(
                f"不正なLLM_PROVIDER: '{provider_str}'\n"
                f"対応プロバイダー: {', '.join(p.value for p in LLMProvider)}"
            )

    @classmethod
    def validate_config(cls, provider: LLMProvider) -> None:
        """
        プロバイダー設定を検証

        指定されたプロバイダーに必要な環境変数が
        すべて設定されているかを確認します。

        Args:
            provider (LLMProvider): 検証するプロバイダー

        Raises:
            LLMConfigError: 必須環境変数が不足している場合
        """
        missing_vars = []
        required_vars = cls.REQUIRED_ENV_VARS.get(provider, [])

        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            logger.error(f"[LLMFactory] 環境変数不足: {missing_vars}")
            raise LLMConfigError(
                f"{provider.value}に必要な環境変数が不足しています:\n"
                f"  {', '.join(missing_vars)}\n\n"
                f"環境変数または.envファイルで設定してください。\n"
                f"参考: .env.example"
            )

        logger.debug(f"[LLMFactory] 設定検証OK: {provider.value}")

    # =========================================================================
    # LLMインスタンス作成
    # =========================================================================

    @classmethod
    def create_chat_model(
        cls,
        temperature: float = 0.0,
        model: Optional[str] = None,
        **kwargs
    ):
        """
        チャットモデルを作成

        設定されているプロバイダーに基づいて
        LangChainのChatModelインスタンスを作成します。

        Args:
            temperature (float): 生成の多様性（0.0 = 決定論的）
            model (str, optional): モデル名の上書き
            **kwargs: プロバイダー固有の追加パラメータ

        Returns:
            ChatModel: LangChainチャットモデルインスタンス

        Raises:
            LLMConfigError: 設定エラー時

        使用例:
            ```python
            # デフォルト設定で作成
            llm = LLMFactory.create_chat_model()

            # カスタム設定で作成
            llm = LLMFactory.create_chat_model(
                temperature=0.7,
                model="gpt-4o-mini"
            )
            ```
        """
        provider = cls.get_provider()
        cls.validate_config(provider)

        logger.info(f"[LLMFactory] LLMインスタンス作成: プロバイダー={provider.value}")

        if provider == LLMProvider.AZURE:
            return cls._create_azure_model(temperature, model, **kwargs)
        elif provider == LLMProvider.AZURE_FOUNDRY:
            return cls._create_azure_foundry_model(temperature, model, **kwargs)
        elif provider == LLMProvider.GCP:
            return cls._create_gcp_model(temperature, model, **kwargs)
        elif provider == LLMProvider.AWS:
            return cls._create_aws_model(temperature, model, **kwargs)
        else:
            raise LLMConfigError(f"未対応のプロバイダー: {provider}")

    @classmethod
    def _create_azure_model(cls, temperature: float, model: Optional[str], **kwargs):
        """
        Azure OpenAI ChatModelを作成

        Azure OpenAI Serviceを使用してChatModelを作成します。

        Args:
            temperature (float): 生成の多様性
            model (str, optional): デプロイ名の上書き
            **kwargs: 追加パラメータ

        Returns:
            AzureChatOpenAI: Azure OpenAIチャットモデル
        """
        from langchain_openai import AzureChatOpenAI

        deployment = model or os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")
        logger.debug(f"[LLMFactory] Azure OpenAI作成: デプロイ={deployment}")

        return AzureChatOpenAI(
            azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
            api_key=os.getenv("AZURE_OPENAI_API_KEY"),
            api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-08-01-preview"),
            deployment_name=deployment,
            temperature=temperature,
            **kwargs
        )

    @classmethod
    def _create_azure_foundry_model(cls, temperature: float, model: Optional[str], **kwargs):
        """
        Azure AI Foundry ChatModelを作成

        Azure AI Foundryを使用してChatModelを作成します。
        OpenAI互換エンドポイントを使用します。

        エンドポイント形式:
            https://<project-name>.<region>.models.ai.azure.com

        Args:
            temperature (float): 生成の多様性
            model (str, optional): モデル名の上書き
            **kwargs: 追加パラメータ

        Returns:
            AzureChatOpenAI: Azure AI Foundryチャットモデル

        Note:
            一部のモデル（o1シリーズ等）はtemperatureパラメータ非対応
        """
        from langchain_openai import AzureChatOpenAI

        endpoint = os.getenv("AZURE_FOUNDRY_ENDPOINT")
        api_key = os.getenv("AZURE_FOUNDRY_API_KEY")
        model_name = model or os.getenv("AZURE_FOUNDRY_MODEL", cls.DEFAULT_MODELS[LLMProvider.AZURE_FOUNDRY])

        logger.debug(f"[LLMFactory] Azure AI Foundry作成: モデル={model_name}")

        # モデルパラメータを構築
        model_kwargs = {
            "azure_endpoint": endpoint,
            "api_key": api_key,
            "api_version": os.getenv("AZURE_FOUNDRY_API_VERSION", "2024-08-01-preview"),
            "deployment_name": model_name,
            **kwargs
        }

        # temperatureパラメータ対応を確認
        if not any(m in model_name.lower() for m in cls.MODELS_WITHOUT_TEMPERATURE):
            model_kwargs["temperature"] = temperature
        else:
            logger.info(f"[LLMFactory] モデル '{model_name}' はtemperatureパラメータ非対応、スキップします")

        return AzureChatOpenAI(**model_kwargs)

    @classmethod
    def _create_gcp_model(cls, temperature: float, model: Optional[str], **kwargs):
        """
        GCP Vertex AI ChatModelを作成

        Google Cloud Vertex AIを使用してChatModelを作成します。
        Geminiモデルが利用可能です。

        Args:
            temperature (float): 生成の多様性
            model (str, optional): モデル名の上書き
            **kwargs: 追加パラメータ

        Returns:
            ChatVertexAI: GCP Vertex AIチャットモデル
        """
        from langchain_google_vertexai import ChatVertexAI

        model_name = model or cls.DEFAULT_MODELS[LLMProvider.GCP]
        logger.debug(f"[LLMFactory] GCP Vertex AI作成: モデル={model_name}")

        return ChatVertexAI(
            project=os.getenv("GCP_PROJECT_ID"),
            location=os.getenv("GCP_LOCATION", "us-central1"),
            model_name=model_name,
            temperature=temperature,
            **kwargs
        )

    @classmethod
    def _create_aws_model(cls, temperature: float, model: Optional[str], **kwargs):
        """
        AWS Bedrock ChatModelを作成

        Amazon Bedrockを使用してChatModelを作成します。
        Claude等のモデルが利用可能です。

        Args:
            temperature (float): 生成の多様性
            model (str, optional): モデルIDの上書き
            **kwargs: 追加パラメータ

        Returns:
            ChatBedrock: AWS Bedrockチャットモデル

        Note:
            AWS認証は環境変数またはIAMロールから自動取得
        """
        from langchain_aws import ChatBedrock

        model_id = model or cls.DEFAULT_MODELS[LLMProvider.AWS]
        logger.debug(f"[LLMFactory] AWS Bedrock作成: モデル={model_id}")

        return ChatBedrock(
            region_name=os.getenv("AWS_REGION", "us-east-1"),
            model_id=model_id,
            model_kwargs={
                "temperature": temperature,
                **kwargs.get("model_kwargs", {})
            },
            credentials_profile_name=os.getenv("AWS_PROFILE"),
        )

    # =========================================================================
    # Vision対応モデル作成
    # =========================================================================

    @classmethod
    def create_vision_model(cls, **kwargs):
        """
        画像認識対応モデルを作成

        画像分析が可能なLLMインスタンスを作成します。
        対応する全プロバイダーでVision機能が利用可能です。

        Args:
            **kwargs: 追加パラメータ

        Returns:
            ChatModel: Vision対応LLMインスタンス

        使用例:
            ```python
            vision_llm = LLMFactory.create_vision_model()

            # 画像を含むメッセージを送信
            messages = [
                HumanMessage(content=[
                    {"type": "text", "text": "この画像を説明してください"},
                    {"type": "image_url", "image_url": {"url": image_data}}
                ])
            ]
            response = vision_llm.invoke(messages)
            ```
        """
        provider = cls.get_provider()

        logger.info(f"[LLMFactory] Vision対応モデル作成: プロバイダー={provider.value}")

        # 各プロバイダーのVision対応モデルを取得
        vision_models = {
            LLMProvider.AZURE: os.getenv("AZURE_OPENAI_VISION_DEPLOYMENT",
                                         os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME")),
            LLMProvider.AZURE_FOUNDRY: os.getenv("AZURE_FOUNDRY_VISION_MODEL",
                                                  os.getenv("AZURE_FOUNDRY_MODEL", cls.VISION_MODELS[LLMProvider.AZURE_FOUNDRY])),
            LLMProvider.GCP: cls.VISION_MODELS[LLMProvider.GCP],
            LLMProvider.AWS: cls.VISION_MODELS[LLMProvider.AWS],
        }

        return cls.create_chat_model(
            model=vision_models.get(provider),
            **kwargs
        )

    # =========================================================================
    # 設定確認・デバッグ
    # =========================================================================

    @classmethod
    def get_config_status(cls) -> dict:
        """
        LLM設定状態を取得

        現在のLLM設定状態をデバッグ用に返します。

        Returns:
            dict: 設定状態
                - provider: プロバイダー名（未設定の場合は"NOT_SET"）
                - configured: 設定完了フラグ
                - missing_vars: 不足している環境変数リスト

        使用例:
            ```python
            status = LLMFactory.get_config_status()
            if status["configured"]:
                print(f"LLM設定OK: {status['provider']}")
            else:
                print(f"未設定の環境変数: {status['missing_vars']}")
            ```
        """
        try:
            provider = cls.get_provider()
            provider_str = provider.value
        except LLMConfigError:
            provider = None
            provider_str = "NOT_SET"

        status = {
            "provider": provider_str,
            "configured": False,
            "missing_vars": [],
        }

        if provider:
            required_vars = cls.REQUIRED_ENV_VARS.get(provider, [])
            for var in required_vars:
                if not os.getenv(var):
                    status["missing_vars"].append(var)

            status["configured"] = len(status["missing_vars"]) == 0

        logger.debug(f"[LLMFactory] 設定状態: {status}")
        return status

    @classmethod
    def get_provider_info(cls) -> dict:
        """
        対応プロバイダー情報を取得

        全対応プロバイダーの詳細情報を返します。
        設定ガイダンスやトラブルシューティングに使用します。

        Returns:
            dict: プロバイダー情報
                - name: プロバイダー名
                - description: 説明
                - models: 対応モデル一覧
                - required_env_vars: 必須環境変数
                - optional_env_vars: オプション環境変数
                - documentation: ドキュメントURL

        使用例:
            ```python
            info = LLMFactory.get_provider_info()
            for provider, details in info.items():
                print(f"{provider}: {details['name']}")
                print(f"  必須: {details['required_env_vars']}")
            ```
        """
        return {
            "AZURE": {
                "name": "Azure OpenAI Service",
                "description": "MicrosoftのマネージドOpenAIサービス",
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"],
                "required_env_vars": cls.REQUIRED_ENV_VARS[LLMProvider.AZURE],
                "optional_env_vars": [
                    "AZURE_OPENAI_API_VERSION",
                    "AZURE_OPENAI_VISION_DEPLOYMENT"
                ],
                "documentation": "https://learn.microsoft.com/azure/ai-services/openai/"
            },
            "AZURE_FOUNDRY": {
                "name": "Azure AI Foundry",
                "description": "Azure AI Foundry - 統合AIプラットフォーム、モデルカタログ対応",
                "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "Phi-4", "DeepSeek-R1"],
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
                "description": "Google CloudのAIプラットフォーム、Geminiモデル対応",
                "models": ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.0-flash-exp"],
                "required_env_vars": cls.REQUIRED_ENV_VARS[LLMProvider.GCP],
                "optional_env_vars": [
                    "GOOGLE_APPLICATION_CREDENTIALS"
                ],
                "documentation": "https://cloud.google.com/vertex-ai/docs"
            },
            "AWS": {
                "name": "Amazon Bedrock",
                "description": "AWSのマネージド基盤モデルサービス",
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
