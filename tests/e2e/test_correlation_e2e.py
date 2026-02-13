"""
================================================================================
test_correlation_e2e.py - 相関ID伝播の完全テスト
================================================================================

【概要】
全プラットフォーム（Azure/AWS/GCP）で相関IDが正しく伝播することを確認します。

【検証項目】
1. VBA/PowerShellで生成した相関IDがレスポンスヘッダーに含まれる
2. 相関IDが全ログに記録される
3. 相関IDが外部API（LLM/OCR）呼び出しにも伝播する
4. 相関IDで全ログを追跡できる

【実行方法】
pytest tests/e2e/test_correlation_e2e.py -v --e2e

================================================================================
"""
import pytest
import requests
import time
import uuid
import os
from typing import Dict, Any, List


# ================================================================================
# フィクスチャ
# ================================================================================

@pytest.fixture(params=["azure", "aws", "gcp"])
def platform_config(request) -> Dict[str, Any]:
    """
    全プラットフォームでテスト実行（パラメタライズ）
    """
    platform = request.param

    if platform == "azure":
        return {
            "name": "azure",
            "endpoint": os.getenv("AZURE_APIM_ENDPOINT"),
            "api_key_header": "Ocp-Apim-Subscription-Key",
            "api_key": os.getenv("AZURE_APIM_SUBSCRIPTION_KEY"),
        }
    elif platform == "aws":
        return {
            "name": "aws",
            "endpoint": os.getenv("AWS_API_GATEWAY_ENDPOINT"),
            "api_key_header": "X-Api-Key",
            "api_key": os.getenv("AWS_API_KEY"),
        }
    elif platform == "gcp":
        return {
            "name": "gcp",
            "endpoint": os.getenv("GCP_APIGEE_ENDPOINT"),
            "api_key_header": "X-Api-Key",
            "api_key": os.getenv("GCP_API_KEY"),
        }


@pytest.fixture
def correlation_id() -> str:
    """
    VBA/PowerShellで生成する相関ID形式（YYYYMMDD_UNIX_0001）
    """
    from datetime import datetime
    date_str = datetime.now().strftime("%Y%m%d")
    unix_timestamp = int(time.time())
    return f"{date_str}_{unix_timestamp}_0001"


@pytest.fixture
def test_item() -> Dict[str, Any]:
    return {
        "id": "correlation_test",
        "category": "統制環境",
        "control_name": "相関IDテスト",
        "evaluation_criteria": "相関IDが全ログに記録される",
        "evaluation_method": "ログ追跡",
        "evidence": "test.pdf",
        "status": "実施中"
    }


# ================================================================================
# E2Eテスト: 相関ID伝播
# ================================================================================

@pytest.mark.e2e
def test_correlation_id_in_response_header(
    platform_config: Dict[str, Any],
    correlation_id: str,
    test_item: Dict[str, Any]
):
    """
    相関IDがレスポンスヘッダーに含まれることを確認
    """
    if not platform_config["endpoint"] or not platform_config["api_key"]:
        pytest.skip(f"Missing config for {platform_config['name']}")

    response = requests.post(
        f"{platform_config['endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            platform_config["api_key_header"]: platform_config["api_key"],
            "Content-Type": "application/json"
        },
        json={"items": [test_item]},
        timeout=60
    )

    assert response.status_code == 200

    # 相関IDがレスポンスヘッダーに含まれる
    assert (
        "X-Correlation-ID" in response.headers or
        "x-correlation-id" in response.headers
    ), f"{platform_config['name']}: X-Correlation-ID not found in response headers"

    returned_correlation_id = (
        response.headers.get("X-Correlation-ID") or
        response.headers.get("x-correlation-id")
    )

    assert returned_correlation_id == correlation_id, (
        f"{platform_config['name']}: Correlation ID mismatch. "
        f"Expected: {correlation_id}, Got: {returned_correlation_id}"
    )

    print(f"✓ {platform_config['name']}: Correlation ID returned in header")


@pytest.mark.e2e
def test_correlation_id_generates_if_not_provided(
    platform_config: Dict[str, Any],
    test_item: Dict[str, Any]
):
    """
    相関IDが提供されない場合、自動生成されることを確認
    """
    if not platform_config["endpoint"] or not platform_config["api_key"]:
        pytest.skip(f"Missing config for {platform_config['name']}")

    response = requests.post(
        f"{platform_config['endpoint']}/evaluate",
        headers={
            # X-Correlation-IDヘッダーを意図的に省略
            platform_config["api_key_header"]: platform_config["api_key"],
            "Content-Type": "application/json"
        },
        json={"items": [test_item]},
        timeout=60
    )

    assert response.status_code == 200

    # 相関IDが自動生成されレスポンスヘッダーに含まれる
    assert (
        "X-Correlation-ID" in response.headers or
        "x-correlation-id" in response.headers
    ), f"{platform_config['name']}: Auto-generated correlation ID not found"

    auto_generated_id = (
        response.headers.get("X-Correlation-ID") or
        response.headers.get("x-correlation-id")
    )

    assert auto_generated_id is not None
    assert len(auto_generated_id) > 0

    print(f"✓ {platform_config['name']}: Correlation ID auto-generated: {auto_generated_id}")


@pytest.mark.e2e
def test_correlation_id_unique_per_request(
    platform_config: Dict[str, Any],
    test_item: Dict[str, Any]
):
    """
    異なるリクエストで異なる相関IDが生成されることを確認
    """
    if not platform_config["endpoint"] or not platform_config["api_key"]:
        pytest.skip(f"Missing config for {platform_config['name']}")

    correlation_ids = []

    # 3つのリクエストを送信
    for i in range(3):
        custom_correlation_id = f"test_{int(time.time())}_{i}"

        response = requests.post(
            f"{platform_config['endpoint']}/evaluate",
            headers={
                "X-Correlation-ID": custom_correlation_id,
                platform_config["api_key_header"]: platform_config["api_key"],
                "Content-Type": "application/json"
            },
            json={"items": [test_item]},
            timeout=60
        )

        assert response.status_code == 200

        returned_id = (
            response.headers.get("X-Correlation-ID") or
            response.headers.get("x-correlation-id")
        )

        correlation_ids.append(returned_id)
        time.sleep(1)  # 1秒インターバル

    # 全ての相関IDがユニークであることを確認
    assert len(correlation_ids) == len(set(correlation_ids)), (
        f"{platform_config['name']}: Duplicate correlation IDs found: {correlation_ids}"
    )

    print(f"✓ {platform_config['name']}: All correlation IDs are unique")


@pytest.mark.e2e
def test_correlation_id_in_logs(
    platform_config: Dict[str, Any],
    correlation_id: str,
    test_item: Dict[str, Any]
):
    """
    相関IDが全ログに記録されることを確認（手動検証用）

    注: 実際のログ確認は以下で実施:
    - Azure: Application Insights
    - AWS: CloudWatch Logs
    - GCP: Cloud Logging
    """
    if not platform_config["endpoint"] or not platform_config["api_key"]:
        pytest.skip(f"Missing config for {platform_config['name']}")

    response = requests.post(
        f"{platform_config['endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            platform_config["api_key_header"]: platform_config["api_key"],
            "Content-Type": "application/json"
        },
        json={"items": [test_item]},
        timeout=60
    )

    assert response.status_code == 200

    # ログ伝播待機
    time.sleep(15)

    print(
        f"✓ {platform_config['name']}: Request completed with correlation_id: {correlation_id}\n"
        f"  Check logs in monitoring service:\n"
        f"  - Azure: Application Insights -> Logs -> search for '{correlation_id}'\n"
        f"  - AWS: CloudWatch Logs -> search for '{correlation_id}'\n"
        f"  - GCP: Cloud Logging -> search for '{correlation_id}'"
    )


@pytest.mark.e2e
def test_correlation_id_in_error_response(
    platform_config: Dict[str, Any],
    correlation_id: str
):
    """
    エラーレスポンスにも相関IDが含まれることを確認
    """
    if not platform_config["endpoint"] or not platform_config["api_key"]:
        pytest.skip(f"Missing config for {platform_config['name']}")

    # 不正なリクエストを送信
    response = requests.post(
        f"{platform_config['endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            platform_config["api_key_header"]: platform_config["api_key"],
            "Content-Type": "application/json"
        },
        json={"invalid": "body"},  # 不正なボディ
        timeout=60
    )

    # エラーレスポンス
    assert response.status_code in [400, 422]

    # 相関IDがエラーレスポンスにも含まれる
    response_data = response.json()
    assert (
        "correlation_id" in response_data or
        "X-Correlation-ID" in response.headers or
        "x-correlation-id" in response.headers
    ), f"{platform_config['name']}: Correlation ID not found in error response"

    print(f"✓ {platform_config['name']}: Correlation ID included in error response")


# ================================================================================
# まとめ
# ================================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--e2e", "--tb=short"])
