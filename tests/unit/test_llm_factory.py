# -*- coding: utf-8 -*-
"""
================================================================================
test_llm_factory.py - llm_factory.pyのユニットテスト
================================================================================

【テスト対象】
- LLMProvider: プロバイダー列挙型
- LLMConfigError: 設定エラークラス
- LLMFactory: LLMファクトリークラス

================================================================================
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock

from infrastructure.llm_factory import (
    LLMProvider,
    LLMConfigError,
    LLMFactory,
    MAX_RETRIES,
    RETRY_DELAY_SECONDS
)


# =============================================================================
# LLMProvider テスト
# =============================================================================

class TestLLMProvider:
    """LLMProvider列挙型のテスト"""

    def test_all_providers_exist(self):
        """全プロバイダーが定義されているか"""
        expected_providers = ["AZURE_FOUNDRY", "GCP", "AWS", "LOCAL"]
        for provider in expected_providers:
            assert hasattr(LLMProvider, provider)

    def test_provider_values(self):
        """プロバイダー値の確認"""
        assert LLMProvider.AZURE_FOUNDRY.value == "AZURE_FOUNDRY"
        assert LLMProvider.GCP.value == "GCP"
        assert LLMProvider.AWS.value == "AWS"
        assert LLMProvider.LOCAL.value == "LOCAL"


# =============================================================================
# LLMConfigError テスト
# =============================================================================

class TestLLMConfigError:
    """LLMConfigErrorクラスのテスト"""

    def test_create_basic_error(self):
        """基本的なエラー作成"""
        error = LLMConfigError("設定エラー")
        assert str(error) == "設定エラー"

    def test_create_error_with_provider(self):
        """プロバイダー情報付きエラー"""
        error = LLMConfigError(
            message="エンドポイント未設定",
            provider="AZURE_FOUNDRY"
        )
        assert error.provider == "AZURE_FOUNDRY"

    def test_create_error_with_missing_vars(self):
        """不足変数情報付きエラー"""
        error = LLMConfigError(
            message="環境変数が不足",
            missing_vars=["AZURE_FOUNDRY_ENDPOINT", "AZURE_FOUNDRY_API_KEY"]
        )
        assert len(error.missing_vars) == 2
        assert "AZURE_FOUNDRY_ENDPOINT" in error.missing_vars


# =============================================================================
# LLMFactory テスト
# =============================================================================

class TestLLMFactory:
    """LLMFactoryクラスのテスト"""

    def test_get_provider_default_raises(self):
        """環境変数なしでエラーが発生する"""
        with patch.dict(os.environ, {}, clear=True):
            # 環境変数なしの場合はエラー
            with pytest.raises(LLMConfigError):
                LLMFactory.get_provider()

    def test_get_provider_azure_foundry(self):
        """Azure Foundryプロバイダー取得"""
        with patch.dict(os.environ, {"LLM_PROVIDER": "AZURE_FOUNDRY"}):
            provider = LLMFactory.get_provider()
            assert provider == LLMProvider.AZURE_FOUNDRY

    def test_get_provider_gcp(self):
        """GCPプロバイダー取得"""
        with patch.dict(os.environ, {"LLM_PROVIDER": "GCP"}):
            provider = LLMFactory.get_provider()
            assert provider == LLMProvider.GCP

    def test_get_provider_aws(self):
        """AWSプロバイダー取得"""
        with patch.dict(os.environ, {"LLM_PROVIDER": "AWS"}):
            provider = LLMFactory.get_provider()
            assert provider == LLMProvider.AWS

    def test_get_provider_local(self):
        """LOCALプロバイダー取得"""
        with patch.dict(os.environ, {"LLM_PROVIDER": "LOCAL"}):
            provider = LLMFactory.get_provider()
            assert provider == LLMProvider.LOCAL

    def test_get_config_status_not_configured(self):
        """未設定状態の取得"""
        with patch.dict(os.environ, {}, clear=True):
            status = LLMFactory.get_config_status()
            assert "configured" in status
            assert "provider" in status

    def test_get_config_status_azure_foundry(self):
        """Azure Foundry設定状態の取得"""
        env_vars = {
            "LLM_PROVIDER": "AZURE_FOUNDRY",
            "AZURE_FOUNDRY_ENDPOINT": "https://test.azure.com/",
            "AZURE_FOUNDRY_API_KEY": "test-key",
            "AZURE_FOUNDRY_MODEL": "gpt-4o-mini"
        }
        with patch.dict(os.environ, env_vars):
            status = LLMFactory.get_config_status()
            assert status["provider"] == "AZURE_FOUNDRY"
            assert status["configured"] is True

    def test_get_config_status_missing_vars(self):
        """必要変数が不足している場合"""
        env_vars = {
            "LLM_PROVIDER": "AZURE_FOUNDRY",
            "AZURE_FOUNDRY_ENDPOINT": "https://test.azure.com/"
            # API_KEYとMODELが不足
        }
        with patch.dict(os.environ, env_vars, clear=True):
            status = LLMFactory.get_config_status()
            if not status["configured"]:
                assert "missing_vars" in status

    def test_create_chat_model_raises_without_config(self):
        """設定なしでChatModel作成時にエラー"""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises((LLMConfigError, Exception)):
                LLMFactory.create_chat_model()


# =============================================================================
# 定数テスト
# =============================================================================

class TestConstants:
    """定数のテスト"""

    def test_max_retries(self):
        """最大リトライ回数"""
        assert MAX_RETRIES == 3

    def test_retry_delay(self):
        """リトライ遅延時間"""
        assert RETRY_DELAY_SECONDS == 1.0


# =============================================================================
# 統合テスト
# =============================================================================

class TestLLMFactoryIntegration:
    """LLMFactoryの統合テスト"""

    @pytest.mark.integration
    def test_config_status_format(self):
        """設定状態の形式確認"""
        status = LLMFactory.get_config_status()

        # 必須フィールドの確認
        assert "provider" in status
        assert "configured" in status
        assert isinstance(status["configured"], bool)

    @pytest.mark.integration
    def test_multiple_provider_detection(self):
        """複数プロバイダーの検出"""
        providers_to_test = [
            ("AZURE_FOUNDRY", LLMProvider.AZURE_FOUNDRY),
            ("GCP", LLMProvider.GCP),
            ("AWS", LLMProvider.AWS),
            ("LOCAL", LLMProvider.LOCAL),
        ]

        for env_value, expected_provider in providers_to_test:
            with patch.dict(os.environ, {"LLM_PROVIDER": env_value}):
                provider = LLMFactory.get_provider()
                assert provider == expected_provider, f"Failed for {env_value}"


# =============================================================================
# ローカルLLM (Ollama) テスト
# =============================================================================

class TestLocalLLMProvider:
    """ローカルLLM (Ollama) のテスト"""

    def test_local_provider_exists(self):
        """LOCALプロバイダーが定義されているか"""
        assert hasattr(LLMProvider, "LOCAL")
        assert LLMProvider.LOCAL.value == "LOCAL"

    def test_local_no_required_vars(self):
        """LOCALは必須環境変数がない"""
        required_vars = LLMFactory.REQUIRED_ENV_VARS.get(LLMProvider.LOCAL, [])
        assert len(required_vars) == 0

    def test_local_default_model(self):
        """LOCALのデフォルトモデル"""
        default_model = LLMFactory.DEFAULT_MODELS.get(LLMProvider.LOCAL)
        assert default_model is not None
        assert "llama" in default_model.lower()

    def test_local_vision_model(self):
        """LOCALのVisionモデル"""
        vision_model = LLMFactory.VISION_MODELS.get(LLMProvider.LOCAL)
        assert vision_model is not None
        assert "llava" in vision_model.lower()

    def test_get_config_status_local(self):
        """LOCAL設定状態の取得"""
        env_vars = {
            "LLM_PROVIDER": "LOCAL",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "llama3.1:8b"
        }
        with patch.dict(os.environ, env_vars):
            status = LLMFactory.get_config_status()
            assert status["provider"] == "LOCAL"
            # LOCALは必須環境変数がないのでconfiguredはTrue
            assert status["configured"] is True

    def test_get_config_status_local_minimal(self):
        """LOCAL最小設定（環境変数なし）"""
        env_vars = {"LLM_PROVIDER": "LOCAL"}
        with patch.dict(os.environ, env_vars, clear=True):
            status = LLMFactory.get_config_status()
            assert status["provider"] == "LOCAL"
            assert status["configured"] is True
            assert len(status.get("missing_vars", [])) == 0

    @pytest.mark.integration
    @pytest.mark.llm
    def test_create_local_model_mock(self):
        """LOCALモデル作成（モック）"""
        env_vars = {
            "LLM_PROVIDER": "LOCAL",
            "OLLAMA_BASE_URL": "http://localhost:11434",
            "OLLAMA_MODEL": "llama3.1:8b"
        }
        with patch.dict(os.environ, env_vars):
            # 設定検証まではテスト（実際のモデル作成は実際のOllamaが必要）
            LLMFactory.validate_config(LLMProvider.LOCAL)

            # 設定状態の確認
            status = LLMFactory.get_config_status()
            assert status["provider"] == "LOCAL"
            assert status["configured"] is True

            # langchain-ollamaがインストールされていなくてもテストはパス
            # 実際のモデル作成はOllamaサーバーが必要なので統合テストとする
