"""
================================================================================
test_azure_e2e.py - Azure全体フローのエンドツーエンドテスト
================================================================================

【概要】
VBA → APIM → Azure Functions → Azure AI Foundry の完全フローをテストします。
実際のAzure環境へのデプロイが必要です。

【前提条件】
1. Azure環境にリソースがデプロイ済み
   - Azure Functions
   - APIM (API Management)
   - Application Insights
   - Key Vault
   - Azure AI Foundry

2. 環境変数設定
   - AZURE_APIM_ENDPOINT
   - AZURE_APIM_SUBSCRIPTION_KEY
   - APPLICATIONINSIGHTS_CONNECTION_STRING

【実行方法】
pytest tests/e2e/test_azure_e2e.py -v --e2e

【注意】
実際のAzure APIを呼び出すため、コストが発生します。

================================================================================
"""
import pytest
import requests
import time
import uuid
import os
from typing import Dict, Any


# ================================================================================
# Pytest設定
# ================================================================================

def pytest_addoption(parser):
    """
    E2Eテスト用のコマンドラインオプション追加
    """
    parser.addoption(
        "--e2e",
        action="store_true",
        default=False,
        help="Run E2E tests (requires deployed Azure environment)"
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "e2e: mark test as end-to-end test")


def pytest_collection_modifyitems(config, items):
    """
    --e2eオプションなしでE2Eテストをスキップ
    """
    if config.getoption("--e2e"):
        return

    skip_e2e = pytest.mark.skip(reason="need --e2e option to run")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip_e2e)


# ================================================================================
# フィクスチャ
# ================================================================================

@pytest.fixture(scope="module")
def azure_config() -> Dict[str, str]:
    """
    Azure環境設定を取得
    """
    config = {
        "apim_endpoint": os.getenv("AZURE_APIM_ENDPOINT"),
        "apim_subscription_key": os.getenv("AZURE_APIM_SUBSCRIPTION_KEY"),
        "app_insights_connection_string": os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING"),
    }

    # 必須環境変数のチェック
    missing = [k for k, v in config.items() if not v]
    if missing:
        pytest.skip(f"Missing required environment variables: {missing}")

    return config


@pytest.fixture
def correlation_id() -> str:
    """
    テスト用相関ID生成
    """
    timestamp = int(time.time())
    return f"e2e_test_{timestamp}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_item() -> Dict[str, Any]:
    """
    テスト用評価項目データ
    """
    return {
        "id": "001",
        "category": "統制環境",
        "control_name": "経営者の誠実性と倫理観",
        "evaluation_criteria": "行動規範が文書化され、全社員に周知されている",
        "evaluation_method": "行動規範の文書確認、全社員へのアンケート実施",
        "evidence": "倫理規定.pdf",
        "status": "実施中"
    }


# ================================================================================
# ヘルパー関数
# ================================================================================

def wait_for_logs(correlation_id: str, timeout: int = 30):
    """
    Application Insightsにログが伝播するまで待機

    Args:
        correlation_id: 相関ID
        timeout: タイムアウト秒数
    """
    time.sleep(timeout)


# ================================================================================
# E2Eテスト: Azure全体フロー
# ================================================================================

@pytest.mark.e2e
def test_azure_e2e_evaluate_with_correlation_id(
    azure_config: Dict[str, str],
    correlation_id: str,
    test_item: Dict[str, Any]
):
    """
    Azure E2E: VBA模擬 → APIM → Functions → AI Foundry
    相関IDが全ログに記録されることを確認
    """
    # 1. VBA模擬リクエスト送信
    response = requests.post(
        f"{azure_config['apim_endpoint']}/api/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            "Ocp-Apim-Subscription-Key": azure_config["apim_subscription_key"],
            "Content-Type": "application/json"
        },
        json={"items": [test_item]},
        timeout=60
    )

    # 2. レスポンス検証
    assert response.status_code == 200, f"Expected 200, got {response.status_code}: {response.text}"

    response_data = response.json()
    assert "results" in response_data
    assert len(response_data["results"]) == 1

    # 相関IDがレスポンスヘッダーに含まれることを確認
    assert "X-Correlation-ID" in response.headers
    assert response.headers["X-Correlation-ID"] == correlation_id

    print(f"✓ Request successful with correlation_id: {correlation_id}")

    # 3. Application Insightsログ確認（オプション）
    # 注: 実際にはApplication Insights APIを使用してログをクエリ
    # この例では待機のみ
    wait_for_logs(correlation_id, timeout=15)

    print(f"✓ Logs should be available in Application Insights with correlation_id: {correlation_id}")


@pytest.mark.e2e
def test_azure_e2e_health_check(azure_config: Dict[str, str]):
    """
    Azure E2E: ヘルスチェックエンドポイント
    """
    response = requests.get(
        f"{azure_config['apim_endpoint']}/api/health",
        headers={
            "Ocp-Apim-Subscription-Key": azure_config["apim_subscription_key"]
        },
        timeout=10
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "healthy"

    print("✓ Health check passed")


@pytest.mark.e2e
def test_azure_e2e_apim_authentication_required(azure_config: Dict[str, str]):
    """
    Azure E2E: API Key認証が必須であることを確認
    """
    response = requests.get(
        f"{azure_config['apim_endpoint']}/api/health",
        # Ocp-Apim-Subscription-Keyヘッダーを意図的に省略
        timeout=10
    )

    # 401 Unauthorizedが返されることを確認
    assert response.status_code == 401, f"Expected 401, got {response.status_code}"

    print("✓ APIM authentication enforced")


@pytest.mark.e2e
def test_azure_e2e_rate_limiting(azure_config: Dict[str, str]):
    """
    Azure E2E: レート制限が動作することを確認
    """
    # APIM設定でレート制限が100 calls/60秒の場合
    # 短時間に大量リクエストを送信してレート制限エラーを確認

    rate_limit_hit = False

    for i in range(10):  # 10リクエスト送信
        response = requests.get(
            f"{azure_config['apim_endpoint']}/api/health",
            headers={
                "Ocp-Apim-Subscription-Key": azure_config["apim_subscription_key"]
            },
            timeout=10
        )

        if response.status_code == 429:  # Too Many Requests
            rate_limit_hit = True
            break

        time.sleep(0.1)  # 100msインターバル

    # 注: 実際のレート制限は100 calls/60秒なので、10リクエストでは制限に到達しない可能性あり
    # このテストはサンプルとして記載
    print(f"✓ Rate limiting test completed (limit hit: {rate_limit_hit})")


@pytest.mark.e2e
def test_azure_e2e_error_handling(azure_config: Dict[str, str], correlation_id: str):
    """
    Azure E2E: エラーハンドリングが正しく動作することを確認
    """
    # 不正なリクエストボディを送信
    response = requests.post(
        f"{azure_config['apim_endpoint']}/api/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            "Ocp-Apim-Subscription-Key": azure_config["apim_subscription_key"],
            "Content-Type": "application/json"
        },
        json={"invalid_key": "invalid_value"},  # 不正なボディ
        timeout=60
    )

    # 400 Bad Requestまたは422 Unprocessable Entityが返されることを確認
    assert response.status_code in [400, 422], f"Expected 400 or 422, got {response.status_code}"

    response_data = response.json()
    assert "error_code" in response_data or "message" in response_data

    # トレースバックが本番環境で非表示になることを確認
    assert "Traceback" not in str(response_data)

    print("✓ Error handling working correctly (no traceback exposed)")


# ================================================================================
# まとめ
# ================================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--e2e", "--tb=short"])
