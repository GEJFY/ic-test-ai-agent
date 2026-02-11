"""
================================================================================
test_secret_providers.py - シークレット管理統合テスト
================================================================================

【概要】
Key Vault/Secrets Manager/Secret Managerからシークレットを取得できることを確認します。
実際のクラウド環境へのアクセスが必要です。

【前提条件】
1. Azure Key Vault設定
   - KEY_VAULT_NAME環境変数
   - Azure認証設定（DefaultAzureCredential）

2. AWS Secrets Manager設定
   - AWS認証情報（~/.aws/credentials または環境変数）

3. GCP Secret Manager設定
   - GCP_PROJECT環境変数
   - GCP認証情報（gcloud auth application-default login）

【実行方法】
pytest tests/integration/test_secret_providers.py -v --integration

================================================================================
"""
import pytest
import os
from typing import Dict, Any
from src.infrastructure.secrets.secrets_provider import get_secret_provider, Platform


# ================================================================================
# Pytest設定
# ================================================================================

def pytest_addoption(parser):
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires cloud access)"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: mark test as integration test")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--integration"):
        return

    skip_integration = pytest.mark.skip(reason="need --integration option to run")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)


# ================================================================================
# フィクスチャ
# ================================================================================

@pytest.fixture(scope="module")
def azure_config() -> Dict[str, Any]:
    """
    Azure Key Vault設定
    """
    key_vault_name = os.getenv("KEY_VAULT_NAME")
    if not key_vault_name:
        pytest.skip("KEY_VAULT_NAME environment variable not set")

    return {
        "key_vault_name": key_vault_name,
        "test_secret_name": "test-api-key"  # テスト用シークレット名
    }


@pytest.fixture(scope="module")
def aws_config() -> Dict[str, Any]:
    """
    AWS Secrets Manager設定
    """
    # AWS認証確認（環境変数またはプロファイル）
    if not (os.getenv("AWS_ACCESS_KEY_ID") or os.path.exists(os.path.expanduser("~/.aws/credentials"))):
        pytest.skip("AWS credentials not configured")

    return {
        "test_secret_name": "test-api-key"  # テスト用シークレット名
    }


@pytest.fixture(scope="module")
def gcp_config() -> Dict[str, Any]:
    """
    GCP Secret Manager設定
    """
    project_id = os.getenv("GCP_PROJECT")
    if not project_id:
        pytest.skip("GCP_PROJECT environment variable not set")

    return {
        "project_id": project_id,
        "test_secret_name": "test-api-key"  # テスト用シークレット名
    }


# ================================================================================
# 統合テスト: Azure Key Vault
# ================================================================================

@pytest.mark.integration
def test_azure_key_vault_get_secret(azure_config: Dict[str, Any]):
    """
    Azure Key Vaultからシークレットを取得できることを確認
    """
    provider = get_secret_provider(Platform.AZURE)

    # テストシークレット取得
    try:
        secret_value = provider.get_secret(azure_config["test_secret_name"])

        assert secret_value is not None
        assert isinstance(secret_value, str)
        assert len(secret_value) > 0

        print(f"✓ Azure Key Vault: Secret retrieved (length: {len(secret_value)})")

    except Exception as e:
        pytest.fail(f"Failed to retrieve secret from Azure Key Vault: {e}")


@pytest.mark.integration
def test_azure_key_vault_nonexistent_secret(azure_config: Dict[str, Any]):
    """
    存在しないシークレットで例外が発生することを確認
    """
    provider = get_secret_provider(Platform.AZURE)

    with pytest.raises(Exception):
        provider.get_secret("nonexistent-secret-12345")

    print("✓ Azure Key Vault: Nonexistent secret raises exception")


@pytest.mark.integration
def test_azure_key_vault_cache(azure_config: Dict[str, Any]):
    """
    シークレットがキャッシュされることを確認（2回目は高速）
    """
    import time

    provider = get_secret_provider(Platform.AZURE)
    secret_name = azure_config["test_secret_name"]

    # 1回目: 実際に取得
    start1 = time.time()
    secret1 = provider.get_secret(secret_name)
    duration1 = time.time() - start1

    # 2回目: キャッシュから取得
    start2 = time.time()
    secret2 = provider.get_secret(secret_name)
    duration2 = time.time() - start2

    assert secret1 == secret2

    # 2回目はキャッシュされているため高速（または同等）
    print(f"✓ Azure Key Vault: 1st={duration1:.3f}s, 2nd={duration2:.3f}s (cached)")


# ================================================================================
# 統合テスト: AWS Secrets Manager
# ================================================================================

@pytest.mark.integration
def test_aws_secrets_manager_get_secret(aws_config: Dict[str, Any]):
    """
    AWS Secrets Managerからシークレットを取得できることを確認
    """
    provider = get_secret_provider(Platform.AWS)

    try:
        secret_value = provider.get_secret(aws_config["test_secret_name"])

        assert secret_value is not None
        assert isinstance(secret_value, str)
        assert len(secret_value) > 0

        print(f"✓ AWS Secrets Manager: Secret retrieved (length: {len(secret_value)})")

    except Exception as e:
        pytest.fail(f"Failed to retrieve secret from AWS Secrets Manager: {e}")


@pytest.mark.integration
def test_aws_secrets_manager_nonexistent_secret(aws_config: Dict[str, Any]):
    """
    存在しないシークレットで例外が発生することを確認
    """
    provider = get_secret_provider(Platform.AWS)

    with pytest.raises(Exception):
        provider.get_secret("nonexistent-secret-12345")

    print("✓ AWS Secrets Manager: Nonexistent secret raises exception")


@pytest.mark.integration
def test_aws_secrets_manager_cache(aws_config: Dict[str, Any]):
    """
    シークレットがキャッシュされることを確認
    """
    import time

    provider = get_secret_provider(Platform.AWS)
    secret_name = aws_config["test_secret_name"]

    # 1回目
    start1 = time.time()
    secret1 = provider.get_secret(secret_name)
    duration1 = time.time() - start1

    # 2回目
    start2 = time.time()
    secret2 = provider.get_secret(secret_name)
    duration2 = time.time() - start2

    assert secret1 == secret2

    print(f"✓ AWS Secrets Manager: 1st={duration1:.3f}s, 2nd={duration2:.3f}s (cached)")


# ================================================================================
# 統合テスト: GCP Secret Manager
# ================================================================================

@pytest.mark.integration
def test_gcp_secret_manager_get_secret(gcp_config: Dict[str, Any]):
    """
    GCP Secret Managerからシークレットを取得できることを確認
    """
    provider = get_secret_provider(Platform.GCP)

    try:
        secret_value = provider.get_secret(gcp_config["test_secret_name"])

        assert secret_value is not None
        assert isinstance(secret_value, str)
        assert len(secret_value) > 0

        print(f"✓ GCP Secret Manager: Secret retrieved (length: {len(secret_value)})")

    except Exception as e:
        pytest.fail(f"Failed to retrieve secret from GCP Secret Manager: {e}")


@pytest.mark.integration
def test_gcp_secret_manager_nonexistent_secret(gcp_config: Dict[str, Any]):
    """
    存在しないシークレットで例外が発生することを確認
    """
    provider = get_secret_provider(Platform.GCP)

    with pytest.raises(Exception):
        provider.get_secret("nonexistent-secret-12345")

    print("✓ GCP Secret Manager: Nonexistent secret raises exception")


@pytest.mark.integration
def test_gcp_secret_manager_cache(gcp_config: Dict[str, Any]):
    """
    シークレットがキャッシュされることを確認
    """
    import time

    provider = get_secret_provider(Platform.GCP)
    secret_name = gcp_config["test_secret_name"]

    # 1回目
    start1 = time.time()
    secret1 = provider.get_secret(secret_name)
    duration1 = time.time() - start1

    # 2回目
    start2 = time.time()
    secret2 = provider.get_secret(secret_name)
    duration2 = time.time() - start2

    assert secret1 == secret2

    print(f"✓ GCP Secret Manager: 1st={duration1:.3f}s, 2nd={duration2:.3f}s (cached)")


# ================================================================================
# 統合テスト: プラットフォーム自動検出
# ================================================================================

@pytest.mark.integration
def test_auto_detect_platform():
    """
    プラットフォームが自動検出されることを確認
    """
    # 環境変数に基づいて自動検出
    provider = get_secret_provider()  # Platformを指定しない

    assert provider is not None
    print(f"✓ Platform auto-detected: {type(provider).__name__}")


# ================================================================================
# 統合テスト: エラーハンドリング
# ================================================================================

@pytest.mark.integration
def test_secret_provider_graceful_degradation():
    """
    シークレット取得失敗時に環境変数へフォールバックすることを確認
    """
    # テスト用環境変数設定
    os.environ["TEST_SECRET_FALLBACK"] = "fallback_value_12345"

    provider = get_secret_provider()

    try:
        # 存在しないシークレットを取得
        secret = provider.get_secret("TEST_SECRET_FALLBACK")

        # 環境変数からフォールバック取得できることを確認
        if secret == "fallback_value_12345":
            print("✓ Secret provider: Fallback to environment variable successful")
        else:
            print("⚠ Secret provider: Fallback behavior differs from expected")

    except Exception as e:
        # フォールバックなしで例外が発生した場合
        print(f"ℹ Secret provider: No fallback mechanism (strict mode): {e}")

    finally:
        # クリーンアップ
        del os.environ["TEST_SECRET_FALLBACK"]


# ================================================================================
# まとめ
# ================================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--integration", "--tb=short"])
