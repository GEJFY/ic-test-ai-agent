"""
シークレット管理統一インターフェース

Azure Key Vault、AWS Secrets Manager、GCP Secret Managerの共通インターフェースを定義します。
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)


class SecretProvider(ABC):
    """
    シークレット管理プロバイダーの抽象基底クラス

    各クラウドプロバイダーのシークレット管理サービスの統一インターフェースです。
    """

    @abstractmethod
    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        シークレットを取得します。

        Args:
            secret_name: シークレット名

        Returns:
            シークレット値。取得できない場合はNone

        Raises:
            Exception: シークレット取得に失敗した場合
        """
        pass

    @abstractmethod
    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        シークレットを設定します。

        Args:
            secret_name: シークレット名
            secret_value: シークレット値

        Returns:
            成功した場合True、失敗した場合False

        Raises:
            Exception: シークレット設定に失敗した場合
        """
        pass

    @abstractmethod
    def delete_secret(self, secret_name: str) -> bool:
        """
        シークレットを削除します。

        Args:
            secret_name: シークレット名

        Returns:
            成功した場合True、失敗した場合False

        Raises:
            Exception: シークレット削除に失敗した場合
        """
        pass

    @abstractmethod
    def list_secrets(self) -> list[str]:
        """
        シークレット名のリストを取得します。

        Returns:
            シークレット名のリスト

        Raises:
            Exception: リスト取得に失敗した場合
        """
        pass


class EnvironmentSecretProvider(SecretProvider):
    """
    環境変数ベースのシークレットプロバイダー

    開発環境やKey Vault接続失敗時のフォールバックとして使用します。
    """

    def __init__(self):
        """
        EnvironmentSecretProviderを初期化します。
        """
        logger.info("環境変数ベースのシークレットプロバイダーを初期化しました")

    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        環境変数からシークレットを取得します。

        Args:
            secret_name: シークレット名（環境変数名）

        Returns:
            シークレット値。環境変数が存在しない場合はNone
        """
        value = os.getenv(secret_name)
        if value:
            logger.debug(f"環境変数からシークレットを取得しました: {secret_name}")
        else:
            logger.warning(f"環境変数が見つかりません: {secret_name}")
        return value

    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        環境変数にシークレットを設定します（実行時のみ有効）。

        Args:
            secret_name: シークレット名
            secret_value: シークレット値

        Returns:
            常にTrue
        """
        os.environ[secret_name] = secret_value
        logger.debug(f"環境変数にシークレットを設定しました: {secret_name}")
        return True

    def delete_secret(self, secret_name: str) -> bool:
        """
        環境変数からシークレットを削除します。

        Args:
            secret_name: シークレット名

        Returns:
            削除成功時True、環境変数が存在しない場合False
        """
        if secret_name in os.environ:
            del os.environ[secret_name]
            logger.debug(f"環境変数からシークレットを削除しました: {secret_name}")
            return True
        logger.warning(f"環境変数が見つかりません: {secret_name}")
        return False

    def list_secrets(self) -> list[str]:
        """
        全環境変数名のリストを取得します。

        Returns:
            環境変数名のリスト
        """
        return list(os.environ.keys())


def get_secret_provider(
    provider_type: Optional[str] = None,
    fallback_to_env: bool = True,
    **kwargs
) -> SecretProvider:
    """
    プロバイダータイプに応じたSecretProviderインスタンスを取得します。

    Args:
        provider_type: プロバイダータイプ（"azure", "aws", "gcp", "env"）
                       Noneの場合は環境変数SECRET_PROVIDERまたはCLOUD_PLATFORMから取得
        fallback_to_env: クラウドプロバイダー接続失敗時に環境変数にフォールバックするか
        **kwargs: プロバイダー固有の初期化パラメータ

    Returns:
        SecretProviderインスタンス

    Raises:
        ValueError: 不正なプロバイダータイプが指定された場合
        ImportError: 必要なライブラリがインストールされていない場合

    Examples:
        >>> # 環境変数からプロバイダータイプを取得
        >>> provider = get_secret_provider()

        >>> # 明示的にAzure Key Vaultを指定
        >>> provider = get_secret_provider(provider_type="azure")

        >>> # フォールバックなしで環境変数プロバイダーを使用
        >>> provider = get_secret_provider(provider_type="env", fallback_to_env=False)
    """
    # プロバイダータイプの決定
    if provider_type is None:
        provider_type = os.getenv("SECRET_PROVIDER") or os.getenv("CLOUD_PLATFORM", "env")

    provider_type = provider_type.lower()

    logger.info(f"シークレットプロバイダーを初期化: {provider_type}")

    try:
        if provider_type == "azure":
            from .azure_keyvault import AzureKeyVaultProvider
            return AzureKeyVaultProvider(**kwargs)

        elif provider_type == "aws":
            from .aws_secrets import AWSSecretsManagerProvider
            return AWSSecretsManagerProvider(**kwargs)

        elif provider_type == "gcp":
            from .gcp_secrets import GCPSecretManagerProvider
            return GCPSecretManagerProvider(**kwargs)

        elif provider_type == "env" or provider_type == "environment":
            return EnvironmentSecretProvider()

        else:
            raise ValueError(
                f"不正なシークレットプロバイダータイプ: {provider_type}。"
                f"有効な値: azure, aws, gcp, env"
            )

    except (ImportError, Exception) as e:
        logger.error(
            f"シークレットプロバイダーの初期化に失敗: {e}",
            exc_info=True
        )

        if fallback_to_env:
            logger.warning("環境変数ベースのプロバイダーにフォールバックします")
            return EnvironmentSecretProvider()
        else:
            raise


# キャッシュ用のグローバルインスタンス
_global_provider: Optional[SecretProvider] = None


def get_default_provider(force_reinitialize: bool = False) -> SecretProvider:
    """
    デフォルトのシークレットプロバイダーを取得します（シングルトン）。

    Args:
        force_reinitialize: 強制的に再初期化するか

    Returns:
        SecretProviderインスタンス

    Examples:
        >>> # 最初の呼び出しで初期化
        >>> provider1 = get_default_provider()
        >>> # 2回目以降は同じインスタンスを返す
        >>> provider2 = get_default_provider()
        >>> provider1 is provider2
        True
    """
    global _global_provider

    if _global_provider is None or force_reinitialize:
        _global_provider = get_secret_provider()

    return _global_provider
