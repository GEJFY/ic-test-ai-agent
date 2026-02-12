"""
AWS Secrets Manager シークレット管理実装

AWS Secrets ManagerでLLM APIキーやOCR APIキーを安全に管理します。
"""

from typing import Optional
import logging
import os
import json

from .secrets_provider import SecretProvider

logger = logging.getLogger(__name__)


class AWSSecretsManagerProvider(SecretProvider):
    """
    AWS Secrets Manager シークレットプロバイダー

    AWS Secrets Managerからシークレットを取得・管理します。
    """

    def __init__(
        self,
        region_name: Optional[str] = None,
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None
    ):
        """
        AWSSecretsManagerProviderを初期化します。

        Args:
            region_name: AWSリージョン名（例: us-east-1）
                         Noneの場合は環境変数AWS_REGIONまたはAWS_DEFAULT_REGIONから取得
            aws_access_key_id: AWSアクセスキーID（Noneの場合はデフォルト認証情報を使用）
            aws_secret_access_key: AWSシークレットアクセスキー

        Raises:
            ImportError: boto3がインストールされていない場合
        """
        try:
            import boto3
        except ImportError as e:
            raise ImportError(
                "boto3 がインストールされていません。"
                "pip install boto3 を実行してください。"
            ) from e

        # リージョン名の取得
        self.region_name = (
            region_name or
            os.getenv("AWS_REGION") or
            os.getenv("AWS_DEFAULT_REGION") or
            "us-east-1"
        )

        # Secrets Managerクライアント初期化
        session_kwargs = {"region_name": self.region_name}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs.update({
                "aws_access_key_id": aws_access_key_id,
                "aws_secret_access_key": aws_secret_access_key
            })

        session = boto3.session.Session(**session_kwargs)
        self.client = session.client("secretsmanager")

        logger.info(f"AWS Secrets Manager に接続しました: {self.region_name}")

    def get_secret(self, secret_name: str) -> Optional[str]:
        """
        Secrets Managerからシークレットを取得します。

        Args:
            secret_name: シークレット名

        Returns:
            シークレット値。取得できない場合はNone

        Examples:
            >>> provider = AWSSecretsManagerProvider()
            >>> api_key = provider.get_secret("bedrock-api-key")
            >>> print(api_key)
            sk-...
        """
        try:
            logger.debug(f"Secrets Managerからシークレットを取得: {secret_name}")
            response = self.client.get_secret_value(SecretId=secret_name)

            # SecretStringまたはSecretBinaryから値を取得
            if "SecretString" in response:
                secret = response["SecretString"]
                # JSON形式の場合はパース試行
                try:
                    secret_dict = json.loads(secret)
                    # JSON形式の場合、最初の値を返す
                    if isinstance(secret_dict, dict):
                        return next(iter(secret_dict.values()))
                    return secret
                except json.JSONDecodeError:
                    return secret
            else:
                # バイナリシークレットの場合
                return response["SecretBinary"].decode("utf-8")

        except self.client.exceptions.ResourceNotFoundException:
            logger.error(f"シークレットが見つかりません: {secret_name}")
            return None

        except Exception as e:
            logger.error(
                f"Secrets Managerからシークレット取得に失敗: {secret_name} - {e}",
                exc_info=True
            )
            return None

    def set_secret(self, secret_name: str, secret_value: str) -> bool:
        """
        Secrets Managerにシークレットを設定します。

        Args:
            secret_name: シークレット名
            secret_value: シークレット値

        Returns:
            成功した場合True、失敗した場合False

        Examples:
            >>> provider = AWSSecretsManagerProvider()
            >>> success = provider.set_secret("my-api-key", "sk-...")
            >>> print(success)
            True
        """
        try:
            logger.debug(f"Secrets Managerにシークレットを設定: {secret_name}")

            # シークレットが存在するか確認
            try:
                self.client.describe_secret(SecretId=secret_name)
                # 存在する場合は更新
                self.client.put_secret_value(
                    SecretId=secret_name,
                    SecretString=secret_value
                )
                logger.info(f"Secrets Managerのシークレットを更新しました: {secret_name}")

            except self.client.exceptions.ResourceNotFoundException:
                # 存在しない場合は新規作成
                self.client.create_secret(
                    Name=secret_name,
                    SecretString=secret_value
                )
                logger.info(f"Secrets Managerにシークレットを作成しました: {secret_name}")

            return True

        except Exception as e:
            logger.error(
                f"Secrets Managerへのシークレット設定に失敗: {secret_name} - {e}",
                exc_info=True
            )
            return False

    def delete_secret(self, secret_name: str, force_delete: bool = False) -> bool:
        """
        Secrets Managerからシークレットを削除します。

        Args:
            secret_name: シークレット名
            force_delete: 即座に削除するか（デフォルトは30日間の猶予期間）

        Returns:
            成功した場合True、失敗した場合False

        Note:
            force_delete=Falseの場合、30日間の猶予期間後に削除されます。
        """
        try:
            logger.debug(f"Secrets Managerからシークレットを削除: {secret_name}")

            kwargs = {"SecretId": secret_name}
            if force_delete:
                kwargs["ForceDeleteWithoutRecovery"] = True
            else:
                kwargs["RecoveryWindowInDays"] = 30

            self.client.delete_secret(**kwargs)

            if force_delete:
                logger.info(f"Secrets Managerからシークレットを即座に削除しました: {secret_name}")
            else:
                logger.info(
                    f"Secrets Managerからシークレットを削除しました "
                    f"(30日後に完全削除): {secret_name}"
                )

            return True

        except Exception as e:
            logger.error(
                f"Secrets Managerからのシークレット削除に失敗: {secret_name} - {e}",
                exc_info=True
            )
            return False

    def list_secrets(self) -> list[str]:
        """
        Secrets Manager内のシークレット名リストを取得します。

        Returns:
            シークレット名のリスト

        Examples:
            >>> provider = AWSSecretsManagerProvider()
            >>> secrets = provider.list_secrets()
            >>> print(secrets)
            ['bedrock-api-key', 'textract-config', ...]
        """
        try:
            logger.debug("Secrets Managerからシークレットリストを取得")
            paginator = self.client.get_paginator("list_secrets")
            secret_names = []

            for page in paginator.paginate():
                for secret in page.get("SecretList", []):
                    secret_names.append(secret["Name"])

            logger.info(f"Secrets Managerから{len(secret_names)}個のシークレットを取得しました")
            return secret_names

        except Exception as e:
            logger.error(
                f"Secrets Managerからのシークレットリスト取得に失敗: {e}",
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
            >>> provider = AWSSecretsManagerProvider()
            >>> api_key = provider.get_secret_with_retry("bedrock-api-key")
        """
        import time

        for attempt in range(max_retries):
            secret = self.get_secret(secret_name)
            if secret:
                return secret

            if attempt < max_retries - 1:
                wait_time = 2 ** attempt  # 指数バックオフ
                logger.warning(
                    f"Secrets Manager接続失敗。{wait_time}秒後にリトライします "
                    f"({attempt + 1}/{max_retries})"
                )
                time.sleep(wait_time)

        # 全リトライ失敗後、環境変数にフォールバック
        if fallback_env:
            logger.warning(
                f"Secrets Manager接続に失敗。環境変数 {secret_name} にフォールバックします"
            )
            return os.getenv(secret_name)

        return None
