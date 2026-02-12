"""
Azure Key Vault シークレット管理実装

Azure Key VaultでLLM APIキーやOCR APIキーを安全に管理します。
"""

from typing import Optional
import logging
import os

from .secrets_provider import SecretProvider

logger = logging.getLogger(__name__)


class AzureKeyVaultProvider(SecretProvider):
    """
    Azure Key Vault シークレットプロバイダー

    Azure Key Vaultからシークレットを取得・管理します。
    """

    def __init__(
        self,
        vault_url: Optional[str] = None,
        credential: Optional[any] = None
    ):
        """
        AzureKeyVaultProviderを初期化します。

        Args:
            vault_url: Key VaultのURL（例: https://my-vault.vault.azure.net/）
                       Noneの場合は環境変数AZURE_KEY_VAULT_URLから取得
            credential: Azure認証情報（DefaultAzureCredentialなど）
                        Noneの場合はDefaultAzureCredentialを使用

        Raises:
            ImportError: azure-keyvault-secretsがインストールされていない場合
            ValueError: vault_urlが指定されておらず環境変数も設定されていない場合
        """
        try:
            from azure.keyvault.secrets import SecretClient
            from azure.identity import DefaultAzureCredential
        except ImportError as e:
            raise ImportError(
                "azure-keyvault-secrets と azure-identity がインストールされていません。"
                "pip install azure-keyvault-secrets azure-identity を実行してください。"
            ) from e

        # Vault URLの取得
        self.vault_url = vault_url or os.getenv("AZURE_KEY_VAULT_URL")
        if not self.vault_url:
            raise ValueError(
                "Key Vault URLが指定されていません。"
                "引数 vault_url または環境変数 AZURE_KEY_VAULT_URL を設定してください。"
            )

        # 認証情報の設定
        if credential is None:
            credential = DefaultAzureCredential()

        # SecretClient初期化
        self.client = SecretClient(
            vault_url=self.vault_url,
            credential=credential
        )

        logger.info(f"Azure Key Vault に接続しました: {self.vault_url}")

    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Key Vaultからシークレットを取得します。

        Args:
            secret_name: シークレット名

        Returns:
            シークレット値。取得できない場合はNone

        Examples:
            >>> provider = AzureKeyVaultProvider()
            >>> api_key = provider.get_secret("AZURE-FOUNDRY-API-KEY")
            >>> print(api_key)
            sk-...
        """
        try:
            logger.debug(f"Key Vaultからシークレットを取得: {secret_name}")
            secret = self.client.get_secret(secret_name)
            return secret.value

        except Exception as e:
            logger.error(
                f"Key Vaultからシークレット取得に失敗: {secret_name} - {e}",
                exc_info=True
            )
            return None

    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        Key Vaultにシークレットを設定します。

        Args:
            secret_name: シークレット名
            secret_value: シークレット値

        Returns:
            成功した場合True、失敗した場合False

        Examples:
            >>> provider = AzureKeyVaultProvider()
            >>> success = provider.set_secret("MY-API-KEY", "sk-...")
            >>> print(success)
            True
        """
        try:
            logger.debug(f"Key Vaultにシークレットを設定: {secret_name}")
            self.client.set_secret(secret_name, secret_value)
            logger.info(f"Key Vaultにシークレットを設定しました: {secret_name}")
            return True

        except Exception as e:
            logger.error(
                f"Key Vaultへのシークレット設定に失敗: {secret_name} - {e}",
                exc_info=True
            )
            return False

    def delete_secret(self, secret_name: str) -> bool:
        """
        Key Vaultからシークレットを削除します。

        Args:
            secret_name: シークレット名

        Returns:
            成功した場合True、失敗した場合False

        Note:
            Azure Key Vaultでは削除後もsoft-deleteにより一定期間保持されます。
        """
        try:
            logger.debug(f"Key Vaultからシークレットを削除: {secret_name}")
            poller = self.client.begin_delete_secret(secret_name)
            poller.wait()
            logger.info(f"Key Vaultからシークレットを削除しました: {secret_name}")
            return True

        except Exception as e:
            logger.error(
                f"Key Vaultからのシークレット削除に失敗: {secret_name} - {e}",
                exc_info=True
            )
            return False

    def list_secrets(self) -> list[str]:
        """
        Key Vault内のシークレット名リストを取得します。

        Returns:
            シークレット名のリスト

        Examples:
            >>> provider = AzureKeyVaultProvider()
            >>> secrets = provider.list_secrets()
            >>> print(secrets)
            ['AZURE-FOUNDRY-API-KEY', 'AZURE-DI-KEY', ...]
        """
        try:
            logger.debug("Key Vaultからシークレットリストを取得")
            secret_properties = self.client.list_properties_of_secrets()
            secret_names = [prop.name for prop in secret_properties]
            logger.info(f"Key Vaultから{len(secret_names)}個のシークレットを取得しました")
            return secret_names

        except Exception as e:
            logger.error(
                f"Key Vaultからのシークレットリスト取得に失敗: {e}",
                exc_info=True
            )
            return []

    def get_secret_with_retry(
        self,
        secret_name: str,
        max_retries: int = 3,
        fallback_env: bool = True
    ) -> Optional[str]:
        """
        リトライ機能付きでシークレットを取得します。

        Args:
            secret_name: シークレット名
            max_retries: 最大リトライ回数
            fallback_env: 失敗時に環境変数にフォールバックするか

        Returns:
            シークレット値。取得できない場合はNone

        Examples:
            >>> provider = AzureKeyVaultProvider()
            >>> api_key = provider.get_secret_with_retry("AZURE-FOUNDRY-API-KEY")
        """
        import time

        for attempt in range(max_retries):
            secret = self.get_secret(secret_name)
            if secret:
                return secret

            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数バックオフ
                logger.warning(
                    f"Key Vault接続失敗。{wait_time}秒後にリトライします "
                    f"({attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)

        # 全リトライ失敗後、環境変数にフォールバック
        if fallback_env:
            logger.warning(
                f"Key Vault接続に失敗。環境変数 {secret_name} にフォールバックします"
            )
            return os.getenv(secret_name)

        return None
