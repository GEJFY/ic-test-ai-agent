"""
GCP Secret Manager シークレット管理実装

GCP Secret ManagerでLLM APIキーやOCR APIキーを安全に管理します。
"""

from typing import Optional
import logging
import os

from .secrets_provider import SecretProvider

logger = logging.getLogger(__name__)


class GCPSecretManagerProvider(SecretProvider):
    """
    GCP Secret Manager シークレットプロバイダー

    GCP Secret Managerからシークレットを取得・管理します。
    """

    def __init__(
        self,
        project_id: Optional[str] = None,
        credentials_path: Optional[str] = None
    ):
        """
        GCPSecretManagerProviderを初期化します。

        Args:
            project_id: GCPプロジェクトID
                        Noneの場合は環境変数GCP_PROJECT_IDまたはGOOGLE_CLOUD_PROJECTから取得
            credentials_path: サービスアカウントキーのJSONファイルパス
                              Noneの場合はデフォルト認証情報を使用

        Raises:
            ImportError: google-cloud-secret-managerがインストールされていない場合
            ValueError: project_idが指定されておらず環境変数も設定されていない場合
        """
        try:
            from google.cloud import secretmanager
        except ImportError as e:
            raise ImportError(
                "google-cloud-secret-manager がインストールされていません。"
                "pip install google-cloud-secret-manager を実行してください。"
            ) from e

        # プロジェクトIDの取得
        self.project_id = (
            project_id or
            os.getenv("GCP_PROJECT_ID") or
            os.getenv("GOOGLE_CLOUD_PROJECT")
        )

        if not self.project_id:
            raise ValueError(
                "GCPプロジェクトIDが指定されていません。"
                "引数 project_id または環境変数 GCP_PROJECT_ID を設定してください。"
            )

        # 認証情報の設定
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

        # Secret Managerクライアント初期化
        self.client = secretmanager.SecretManagerServiceClient()

        logger.info(f"GCP Secret Manager に接続しました: プロジェクト {self.project_id}")

    def _get_secret_path(self, secret_name: str, version: str = "latest") -> str:
        """
        シークレットのフルパスを取得します。

        Args:
            secret_name: シークレット名
            version: バージョン（デフォルト: "latest"）

        Returns:
            シークレットのフルパス
        """
        return f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"

    def get_secret(self, secret_name: str, version: str = "latest") -> Optional[str]:
        """
        Secret Managerからシークレットを取得します。

        Args:
            secret_name: シークレット名
            version: バージョン（デフォルト: "latest"）

        Returns:
            シークレット値。取得できない場合はNone

        Examples:
            >>> provider = GCPSecretManagerProvider(project_id="my-project")
            >>> api_key = provider.get_secret("gemini-api-key")
            >>> print(api_key)
            sk-...
        """
        try:
            logger.debug(f"Secret Managerからシークレットを取得: {secret_name}")
            name = self._get_secret_path(secret_name, version)
            response = self.client.access_secret_version(request={"name": name})
            secret_value = response.payload.data.decode("utf-8")
            return secret_value

        except Exception as e:
            logger.error(
                f"Secret Managerからシークレット取得に失敗: {secret_name} - {e}",
                exc_info=True
            )
            return None

    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        Secret Managerにシークレットを設定します。

        Args:
            secret_name: シークレット名
            secret_value: シークレット値

        Returns:
            成功した場合True、失敗した場合False

        Examples:
            >>> provider = GCPSecretManagerProvider(project_id="my-project")
            >>> success = provider.set_secret("my-api-key", "sk-...")
            >>> print(success)
            True
        """
        try:
            logger.debug(f"Secret Managerにシークレットを設定: {secret_name}")
            parent = f"projects/{self.project_id}"

            # シークレットが存在するか確認
            try:
                secret_path = f"{parent}/secrets/{secret_name}"
                self.client.get_secret(request={"name": secret_path})
                # 存在する場合は新しいバージョンを追加
                payload = secret_value.encode("utf-8")
                self.client.add_secret_version(
                    request={
                        "parent": secret_path,
                        "payload": {"data": payload}
                    }
                )
                logger.info(f"Secret Managerのシークレットを更新しました: {secret_name}")

            except Exception:
                # 存在しない場合は新規作成
                secret = self.client.create_secret(
                    request={
                        "parent": parent,
                        "secret_id": secret_name,
                        "secret": {
                            "replication": {
                                "automatic": {}
                            }
                        }
                    }
                )
                # 最初のバージョンを追加
                payload = secret_value.encode("utf-8")
                self.client.add_secret_version(
                    request={
                        "parent": secret.name,
                        "payload": {"data": payload}
                    }
                )
                logger.info(f"Secret Managerにシークレットを作成しました: {secret_name}")

            return True

        except Exception as e:
            logger.error(
                f"Secret Managerへのシークレット設定に失敗: {secret_name} - {e}",
                exc_info=True
            )
            return False

    def delete_secret(self, secret_name: str) -> bool:
        """
        Secret Managerからシークレットを削除します。

        Args:
            secret_name: シークレット名

        Returns:
            成功した場合True、失敗した場合False

        Note:
            シークレットと全バージョンが完全に削除されます。
        """
        try:
            logger.debug(f"Secret Managerからシークレットを削除: {secret_name}")
            name = f"projects/{self.project_id}/secrets/{secret_name}"
            self.client.delete_secret(request={"name": name})
            logger.info(f"Secret Managerからシークレットを削除しました: {secret_name}")
            return True

        except Exception as e:
            logger.error(
                f"Secret Managerからのシークレット削除に失敗: {secret_name} - {e}",
                exc_info=True
            )
            return False

    def list_secrets(self) -> list[str]:
        """
        Secret Manager内のシークレット名リストを取得します。

        Returns:
            シークレット名のリスト

        Examples:
            >>> provider = GCPSecretManagerProvider(project_id="my-project")
            >>> secrets = provider.list_secrets()
            >>> print(secrets)
            ['gemini-api-key', 'document-ai-config', ...]
        """
        try:
            logger.debug("Secret Managerからシークレットリストを取得")
            parent = f"projects/{self.project_id}"
            secrets = self.client.list_secrets(request={"parent": parent})

            secret_names = []
            for secret in secrets:
                # フルパスから名前部分を抽出
                # projects/123/secrets/my-secret → my-secret
                secret_name = secret.name.split("/")[-1]
                secret_names.append(secret_name)

            logger.info(f"Secret Managerから{len(secret_names)}個のシークレットを取得しました")
            return secret_names

        except Exception as e:
            logger.error(
                f"Secret Managerからのシークレットリスト取得に失敗: {e}",
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
            >>> provider = GCPSecretManagerProvider(project_id="my-project")
            >>> api_key = provider.get_secret_with_retry("gemini-api-key")
        """
        import time

        for attempt in range(max_retries):
            secret = self.get_secret(secret_name)
            if secret:
                return secret

            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数バックオフ
                logger.warning(
                    f"Secret Manager接続失敗。{wait_time}秒後にリトライします "
                    f"({attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)

        # 全リトライ失敗後、環境変数にフォールバック
        if fallback_env:
            logger.warning(
                f"Secret Manager接続に失敗。環境変数 {secret_name} にフォールバックします"
            )
            return os.getenv(secret_name)

        return None

    def list_secret_versions(self, secret_name: str) -> list[str]:
        """
        指定されたシークレットのバージョンリストを取得します。

        Args:
            secret_name: シークレット名

        Returns:
            バージョン番号のリスト

        Examples:
            >>> provider = GCPSecretManagerProvider(project_id="my-project")
            >>> versions = provider.list_secret_versions("gemini-api-key")
            >>> print(versions)
            ['1', '2', '3', ...]
        """
        try:
            logger.debug(f"Secret Managerからバージョンリストを取得: {secret_name}")
            parent = f"projects/{self.project_id}/secrets/{secret_name}"
            versions = self.client.list_secret_versions(request={"parent": parent})

            version_names = []
            for version in versions:
                # フルパスからバージョン番号を抽出
                # projects/123/secrets/my-secret/versions/1 → 1
                version_number = version.name.split("/")[-1]
                version_names.append(version_number)

            logger.info(
                f"Secret Managerから{len(version_names)}個のバージョンを取得しました: "
                f"{secret_name}"
            )
            return version_names

        except Exception as e:
            logger.error(
                f"Secret Managerからのバージョンリスト取得に失敗: {secret_name} - {e}",
                exc_info=True
            )
            return []
