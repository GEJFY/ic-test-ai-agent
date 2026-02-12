"""
シークレット管理モジュール

Azure Key Vault、AWS Secrets Manager、GCP Secret Managerの統一インターフェースを提供します。
"""

from .secrets_provider import SecretProvider, get_secret_provider

__all__ = ["SecretProvider", "get_secret_provider"]
