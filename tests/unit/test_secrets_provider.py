"""
シークレット管理機能のユニットテスト

secrets_provider.pyおよび各プロバイダー実装をテストします。
"""
import pytest
import os
from unittest.mock import Mock, patch, MagicMock

# テスト対象のモジュールをインポート
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from infrastructure.secrets.secrets_provider import (
    SecretProvider,
    EnvironmentSecretProvider,
    get_secret_provider,
    get_default_provider
)


class TestEnvironmentSecretProvider:
    """EnvironmentSecretProviderのテストクラス"""

    def setup_method(self):
        """各テストの前に環境変数をクリア"""
        # テスト用環境変数を削除
        for key in ["TEST_SECRET", "TEST_API_KEY", "ANOTHER_SECRET"]:
            if key in os.environ:
                del os.environ[key]

    def teardown_method(self):
        """各テストの後に環境変数をクリア"""
        for key in ["TEST_SECRET", "TEST_API_KEY", "ANOTHER_SECRET"]:
            if key in os.environ:
                del os.environ[key]

    def test_get_secret_existing(self):
        """
        環境変数からシークレットを取得できることを確認
        """
        os.environ["TEST_SECRET"] = "test-secret-value"

        provider = EnvironmentSecretProvider()
        secret = provider.get_secret("TEST_SECRET")

        assert secret == "test-secret-value"

    def test_get_secret_non_existing(self):
        """
        存在しない環境変数の場合、Noneが返されることを確認
        """
        provider = EnvironmentSecretProvider()
        secret = provider.get_secret("NON_EXISTING_SECRET")

        assert secret is None

    def test_set_secret(self):
        """
        シークレットを環境変数に設定できることを確認
        """
        provider = EnvironmentSecretProvider()
        success = provider.set_secret("TEST_API_KEY", "new-api-key")

        assert success is True
        assert os.environ["TEST_API_KEY"] == "new-api-key"

    def test_delete_secret_existing(self):
        """
        既存のシークレットを削除できることを確認
        """
        os.environ["ANOTHER_SECRET"] = "value-to-delete"

        provider = EnvironmentSecretProvider()
        success = provider.delete_secret("ANOTHER_SECRET")

        assert success is True
        assert "ANOTHER_SECRET" not in os.environ

    def test_delete_secret_non_existing(self):
        """
        存在しないシークレットを削除しようとした場合、Falseが返されることを確認
        """
        provider = EnvironmentSecretProvider()
        success = provider.delete_secret("NON_EXISTING_SECRET")

        assert success is False

    def test_list_secrets(self):
        """
        全環境変数のリストを取得できることを確認
        """
        # テスト用環境変数を設定
        os.environ["TEST_SECRET_1"] = "value1"
        os.environ["TEST_SECRET_2"] = "value2"

        provider = EnvironmentSecretProvider()
        secrets = provider.list_secrets()

        # 少なくともテスト用環境変数が含まれる
        assert "TEST_SECRET_1" in secrets
        assert "TEST_SECRET_2" in secrets


class TestGetSecretProvider:
    """get_secret_provider関数のテストクラス"""

    def setup_method(self):
        """各テストの前に環境変数をクリア"""
        if "SECRET_PROVIDER" in os.environ:
            del os.environ["SECRET_PROVIDER"]
        if "CLOUD_PLATFORM" in os.environ:
            del os.environ["CLOUD_PLATFORM"]

    def teardown_method(self):
        """各テストの後に環境変数をクリア"""
        if "SECRET_PROVIDER" in os.environ:
            del os.environ["SECRET_PROVIDER"]
        if "CLOUD_PLATFORM" in os.environ:
            del os.environ["CLOUD_PLATFORM"]

    def test_get_secret_provider_env(self):
        """
        provider_type='env'で環境変数プロバイダーが返されることを確認
        """
        provider = get_secret_provider(provider_type="env")

        assert isinstance(provider, EnvironmentSecretProvider)

    def test_get_secret_provider_environment(self):
        """
        provider_type='environment'で環境変数プロバイダーが返されることを確認
        """
        provider = get_secret_provider(provider_type="environment")

        assert isinstance(provider, EnvironmentSecretProvider)

    def test_get_secret_provider_from_env_var(self):
        """
        環境変数SECRET_PROVIDERからプロバイダータイプを取得できることを確認
        """
        os.environ["SECRET_PROVIDER"] = "env"

        provider = get_secret_provider()

        assert isinstance(provider, EnvironmentSecretProvider)

    def test_get_secret_provider_from_cloud_platform(self):
        """
        環境変数CLOUD_PLATFORMからプロバイダータイプを取得できることを確認
        """
        os.environ["CLOUD_PLATFORM"] = "env"

        provider = get_secret_provider()

        assert isinstance(provider, EnvironmentSecretProvider)

    def test_get_secret_provider_invalid_type(self):
        """
        不正なプロバイダータイプの場合、ValueErrorが発生することを確認
        """
        with pytest.raises(ValueError) as exc_info:
            get_secret_provider(provider_type="invalid_type", fallback_to_env=False)

        assert "不正なシークレットプロバイダータイプ" in str(exc_info.value)

    def test_get_secret_provider_fallback_to_env(self):
        """
        プロバイダー初期化失敗時、fallback_to_env=Trueで環境変数プロバイダーにフォールバックすることを確認
        """
        # 存在しないプロバイダーを指定（Azureライブラリがインストールされていない想定）
        with patch('infrastructure.secrets.secrets_provider.os.getenv', return_value='azure'):
            provider = get_secret_provider(fallback_to_env=True)

            # フォールバックして環境変数プロバイダーが返される
            assert isinstance(provider, EnvironmentSecretProvider)

    @patch('infrastructure.secrets.azure_keyvault.AzureKeyVaultProvider')
    def test_get_secret_provider_azure(self, mock_azure_provider):
        """
        provider_type='azure'でAzureプロバイダーが返されることを確認（モック）
        """
        mock_instance = Mock()
        mock_azure_provider.return_value = mock_instance

        with patch.dict('sys.modules', {'azure.keyvault.secrets': Mock(), 'azure.identity': Mock()}):
            provider = get_secret_provider(provider_type="azure", vault_url="https://test.vault.azure.net")

            # Azureプロバイダーが初期化された（実際はモック）
            mock_azure_provider.assert_called_once()

    @patch('infrastructure.secrets.aws_secrets.AWSSecretsManagerProvider')
    def test_get_secret_provider_aws(self, mock_aws_provider):
        """
        provider_type='aws'でAWSプロバイダーが返されることを確認（モック）
        """
        mock_instance = Mock()
        mock_aws_provider.return_value = mock_instance

        with patch.dict('sys.modules', {'boto3': Mock()}):
            provider = get_secret_provider(provider_type="aws", region_name="us-east-1")

            # AWSプロバイダーが初期化された（実際はモック）
            mock_aws_provider.assert_called_once()

    @patch('infrastructure.secrets.gcp_secrets.GCPSecretManagerProvider')
    def test_get_secret_provider_gcp(self, mock_gcp_provider):
        """
        provider_type='gcp'でGCPプロバイダーが返されることを確認（モック）
        """
        mock_instance = Mock()
        mock_gcp_provider.return_value = mock_instance

        with patch.dict('sys.modules', {'google.cloud.secretmanager': Mock()}):
            provider = get_secret_provider(provider_type="gcp", project_id="test-project")

            # GCPプロバイダーが初期化された（実際はモック）
            mock_gcp_provider.assert_called_once()


class TestGetDefaultProvider:
    """get_default_provider関数のテストクラス"""

    def setup_method(self):
        """各テストの前にグローバルプロバイダーをクリア"""
        import infrastructure.secrets.secrets_provider as sp
        sp._global_provider = None

    def teardown_method(self):
        """各テストの後にグローバルプロバイダーをクリア"""
        import infrastructure.secrets.secrets_provider as sp
        sp._global_provider = None

    def test_get_default_provider_singleton(self):
        """
        get_default_providerがシングルトンとして動作することを確認
        """
        provider1 = get_default_provider()
        provider2 = get_default_provider()

        # 同じインスタンスが返される
        assert provider1 is provider2

    def test_get_default_provider_force_reinitialize(self):
        """
        force_reinitialize=Trueで再初期化されることを確認
        """
        provider1 = get_default_provider()
        provider2 = get_default_provider(force_reinitialize=True)

        # 異なるインスタンスが返される
        assert provider1 is not provider2


class TestAzureKeyVaultProvider:
    """AzureKeyVaultProviderのテストクラス（モック使用）"""

    @patch('azure.keyvault.secrets.SecretClient')
    @patch('azure.identity.DefaultAzureCredential')
    def test_azure_provider_initialization(self, mock_credential, mock_client):
        """
        AzureKeyVaultProviderが正しく初期化されることを確認
        """
        from infrastructure.secrets.azure_keyvault import AzureKeyVaultProvider

        provider = AzureKeyVaultProvider(vault_url="https://test.vault.azure.net")

        # DefaultAzureCredentialが呼ばれた
        mock_credential.assert_called_once()
        # SecretClientが呼ばれた
        mock_client.assert_called_once_with(
            vault_url="https://test.vault.azure.net",
            credential=mock_credential.return_value
        )

    @patch('azure.keyvault.secrets.SecretClient')
    @patch('azure.identity.DefaultAzureCredential')
    def test_azure_provider_get_secret(self, mock_credential, mock_client):
        """
        AzureKeyVaultProviderでシークレット取得ができることを確認
        """
        from infrastructure.secrets.azure_keyvault import AzureKeyVaultProvider

        # モックの設定
        mock_secret = Mock()
        mock_secret.value = "azure-secret-value"
        mock_client_instance = Mock()
        mock_client_instance.get_secret.return_value = mock_secret
        mock_client.return_value = mock_client_instance

        provider = AzureKeyVaultProvider(vault_url="https://test.vault.azure.net")
        secret = provider.get_secret("test-secret")

        assert secret == "azure-secret-value"
        mock_client_instance.get_secret.assert_called_once_with("test-secret")


class TestAWSSecretsManagerProvider:
    """AWSSecretsManagerProviderのテストクラス（モック使用）"""

    @patch('boto3.session.Session')
    def test_aws_provider_initialization(self, mock_session_class):
        """
        AWSSecretsManagerProviderが正しく初期化されることを確認
        """
        from infrastructure.secrets.aws_secrets import AWSSecretsManagerProvider

        mock_session = Mock()
        mock_client = Mock()
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        provider = AWSSecretsManagerProvider(region_name="us-east-1")

        # boto3 Sessionが初期化された
        mock_session_class.assert_called_once_with(region_name="us-east-1")
        # Secrets Managerクライアントが作成された
        mock_session.client.assert_called_once_with("secretsmanager")

    @patch('boto3.session.Session')
    def test_aws_provider_get_secret(self, mock_session_class):
        """
        AWSSecretsManagerProviderでシークレット取得ができることを確認
        """
        from infrastructure.secrets.aws_secrets import AWSSecretsManagerProvider

        # モックの設定
        mock_session = Mock()
        mock_client = Mock()
        mock_client.get_secret_value.return_value = {"SecretString": "aws-secret-value"}
        mock_session.client.return_value = mock_client
        mock_session_class.return_value = mock_session

        provider = AWSSecretsManagerProvider(region_name="us-east-1")
        secret = provider.get_secret("test-secret")

        assert secret == "aws-secret-value"
        # get_secret_valueが呼ばれたことを確認
        assert mock_client.get_secret_value.called


class TestGCPSecretManagerProvider:
    """GCPSecretManagerProviderのテストクラス（モック使用）"""

    @patch('google.cloud.secretmanager.SecretManagerServiceClient')
    def test_gcp_provider_initialization(self, mock_client_class):
        """
        GCPSecretManagerProviderが正しく初期化されることを確認
        """
        from infrastructure.secrets.gcp_secrets import GCPSecretManagerProvider

        mock_client = Mock()
        mock_client_class.return_value = mock_client

        provider = GCPSecretManagerProvider(project_id="test-project")

        # SecretManagerServiceClientが初期化された
        mock_client_class.assert_called_once()

    @patch('google.cloud.secretmanager.SecretManagerServiceClient')
    def test_gcp_provider_get_secret(self, mock_client_class):
        """
        GCPSecretManagerProviderでシークレット取得ができることを確認
        """
        from infrastructure.secrets.gcp_secrets import GCPSecretManagerProvider

        # モックの設定
        mock_client = Mock()
        mock_response = Mock()
        mock_response.payload.data = b"gcp-secret-value"
        mock_client.access_secret_version.return_value = mock_response
        mock_client_class.return_value = mock_client

        provider = GCPSecretManagerProvider(project_id="test-project")
        secret = provider.get_secret("test-secret")

        assert secret == "gcp-secret-value"
        # access_secret_versionが呼ばれたことを確認
        assert mock_client.access_secret_version.called


class TestSecretProviderRetry:
    """シークレットプロバイダーのリトライ機能テスト"""

    @patch('azure.keyvault.secrets.SecretClient')
    @patch('azure.identity.DefaultAzureCredential')
    @patch('time.sleep')  # sleep をモック化して高速化
    def test_get_secret_with_retry_success_on_retry(self, mock_sleep, mock_credential, mock_client):
        """
        リトライで成功することを確認
        """
        from infrastructure.secrets.azure_keyvault import AzureKeyVaultProvider

        # 最初は失敗、2回目で成功
        mock_secret = Mock()
        mock_secret.value = "retry-success-value"
        mock_client_instance = Mock()
        mock_client_instance.get_secret.side_effect = [
            Exception("Connection error"),
            mock_secret
        ]
        mock_client.return_value = mock_client_instance

        provider = AzureKeyVaultProvider(vault_url="https://test.vault.azure.net")
        secret = provider.get_secret_with_retry("test-secret", max_retries=3)

        assert secret == "retry-success-value"
        assert mock_client_instance.get_secret.call_count == 2

    @patch('azure.keyvault.secrets.SecretClient')
    @patch('azure.identity.DefaultAzureCredential')
    @patch('time.sleep')
    def test_get_secret_with_retry_fallback_to_env(self, mock_sleep, mock_credential, mock_client):
        """
        全リトライ失敗後、環境変数にフォールバックすることを確認
        """
        from infrastructure.secrets.azure_keyvault import AzureKeyVaultProvider

        # 全て失敗
        mock_client_instance = Mock()
        mock_client_instance.get_secret.side_effect = Exception("Always fails")
        mock_client.return_value = mock_client_instance

        # 環境変数を設定
        os.environ["FALLBACK_SECRET"] = "env-fallback-value"

        try:
            provider = AzureKeyVaultProvider(vault_url="https://test.vault.azure.net")
            secret = provider.get_secret_with_retry("FALLBACK_SECRET", max_retries=2, fallback_env=True)

            # 環境変数から取得
            assert secret == "env-fallback-value"
        finally:
            if "FALLBACK_SECRET" in os.environ:
                del os.environ["FALLBACK_SECRET"]


# pytest実行時のエントリポイント
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
