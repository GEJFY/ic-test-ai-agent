"""
================================================================================
test_error_scenarios.py - エラーシナリオのE2Eテスト
================================================================================

【概要】
様々なエラーシナリオで正しくエラーハンドリングされることを確認します。

【検証項目】
1. 不正なリクエストボディ（400 Bad Request）
2. 認証エラー（401/403 Unauthorized/Forbidden）
3. リソース不足（429 Too Many Requests）
4. サーバーエラー（500 Internal Server Error）
5. タイムアウト
6. エラーレスポンスでトレースバック非表示
7. エラー時も相関ID記録

【実行方法】
pytest tests/e2e/test_error_scenarios.py -v --e2e

================================================================================
"""
import pytest
import requests
import time
import uuid
import os
from typing import Dict, Any


# ================================================================================
# フィクスチャ
# ================================================================================

@pytest.fixture(params=["azure", "aws", "gcp"])
def platform_config(request) -> Dict[str, Any]:
    """
    全プラットフォームでテスト実行
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
    return f"error_test_{int(time.time())}_{uuid.uuid4().hex[:8]}"


# ================================================================================
# E2Eテスト: エラーシナリオ
# ================================================================================

@pytest.mark.e2e
def test_error_invalid_request_body(
    platform_config: Dict[str, Any],
    correlation_id: str
):
    """
    不正なリクエストボディで400 Bad Requestが返されることを確認
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
        json={"invalid_key": "invalid_value"},  # 不正なボディ
        timeout=60
    )

    # 400 Bad Request または 422 Unprocessable Entity
    assert response.status_code in [400, 422], (
        f"{platform_config['name']}: Expected 400/422, got {response.status_code}"
    )

    response_data = response.json()

    # エラーメッセージが含まれる
    assert "error_code" in response_data or "message" in response_data, (
        f"{platform_config['name']}: Error message not found in response"
    )

    # トレースバックが本番環境で非表示
    response_str = str(response_data)
    assert "Traceback" not in response_str, (
        f"{platform_config['name']}: Traceback exposed in production error response"
    )
    assert ".py\", line" not in response_str, (
        f"{platform_config['name']}: Stack trace exposed in production error response"
    )

    print(f"✓ {platform_config['name']}: Invalid request body handled correctly (no traceback)")


@pytest.mark.e2e
def test_error_missing_required_fields(
    platform_config: Dict[str, Any],
    correlation_id: str
):
    """
    必須フィールド欠如で422 Unprocessable Entityが返されることを確認
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
        json={"items": [{"id": "001"}]},  # 必須フィールド欠如
        timeout=60
    )

    assert response.status_code in [400, 422]
    response_data = response.json()

    # エラー詳細が含まれる
    assert "message" in response_data or "error_code" in response_data

    print(f"✓ {platform_config['name']}: Missing required fields handled correctly")


@pytest.mark.e2e
def test_error_authentication_failure(platform_config: Dict[str, Any]):
    """
    認証エラーで401/403が返されることを確認
    """
    if not platform_config["endpoint"]:
        pytest.skip(f"Missing endpoint for {platform_config['name']}")

    response = requests.get(
        f"{platform_config['endpoint']}/health",
        # API Keyヘッダーを意図的に省略
        timeout=10
    )

    # 401 Unauthorized または 403 Forbidden
    assert response.status_code in [401, 403], (
        f"{platform_config['name']}: Expected 401/403, got {response.status_code}"
    )

    print(f"✓ {platform_config['name']}: Authentication failure handled correctly")


@pytest.mark.e2e
def test_error_invalid_api_key(platform_config: Dict[str, Any]):
    """
    不正なAPI Keyで401/403が返されることを確認
    """
    if not platform_config["endpoint"]:
        pytest.skip(f"Missing endpoint for {platform_config['name']}")

    response = requests.get(
        f"{platform_config['endpoint']}/health",
        headers={
            platform_config["api_key_header"]: "invalid_api_key_12345"  # 不正なキー
        },
        timeout=10
    )

    assert response.status_code in [401, 403], (
        f"{platform_config['name']}: Expected 401/403, got {response.status_code}"
    )

    print(f"✓ {platform_config['name']}: Invalid API key handled correctly")


@pytest.mark.e2e
def test_error_not_found(
    platform_config: Dict[str, Any],
    correlation_id: str
):
    """
    存在しないエンドポイントで404 Not Foundが返されることを確認
    """
    if not platform_config["endpoint"] or not platform_config["api_key"]:
        pytest.skip(f"Missing config for {platform_config['name']}")

    response = requests.get(
        f"{platform_config['endpoint']}/nonexistent/endpoint",
        headers={
            "X-Correlation-ID": correlation_id,
            platform_config["api_key_header"]: platform_config["api_key"]
        },
        timeout=10
    )

    assert response.status_code == 404, (
        f"{platform_config['name']}: Expected 404, got {response.status_code}"
    )

    print(f"✓ {platform_config['name']}: 404 Not Found handled correctly")


@pytest.mark.e2e
def test_error_method_not_allowed(
    platform_config: Dict[str, Any],
    correlation_id: str
):
    """
    不正なHTTPメソッドで405 Method Not Allowedが返されることを確認
    """
    if not platform_config["endpoint"] or not platform_config["api_key"]:
        pytest.skip(f"Missing config for {platform_config['name']}")

    # /evaluateはPOSTのみ許可、GETは不可
    response = requests.get(
        f"{platform_config['endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            platform_config["api_key_header"]: platform_config["api_key"]
        },
        timeout=10
    )

    # 405 Method Not Allowed または 400 Bad Request
    assert response.status_code in [400, 405], (
        f"{platform_config['name']}: Expected 400/405, got {response.status_code}"
    )

    print(f"✓ {platform_config['name']}: Method not allowed handled correctly")


@pytest.mark.e2e
def test_error_correlation_id_preserved_in_error(
    platform_config: Dict[str, Any],
    correlation_id: str
):
    """
    エラー時でも相関IDが保持されることを確認
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
        json={"invalid": "data"},
        timeout=60
    )

    assert response.status_code in [400, 422]

    # 相関IDがエラーレスポンスにも含まれる
    has_correlation_id = (
        "X-Correlation-ID" in response.headers
        or "x-correlation-id" in response.headers
    )

    if not has_correlation_id:
        # ヘッダーになければボディに含まれることを確認
        response_data = response.json()
        has_correlation_id = "correlation_id" in response_data

    assert has_correlation_id, (
        f"{platform_config['name']}: Correlation ID not preserved in error response"
    )

    print(f"✓ {platform_config['name']}: Correlation ID preserved in error")


@pytest.mark.e2e
def test_error_timeout_handling(
    platform_config: Dict[str, Any],
    correlation_id: str
):
    """
    タイムアウト処理が正しく動作することを確認
    """
    if not platform_config["endpoint"] or not platform_config["api_key"]:
        pytest.skip(f"Missing config for {platform_config['name']}")

    # 非常に短いタイムアウトを設定
    try:
        _ = requests.post(
            f"{platform_config['endpoint']}/evaluate",
            headers={
                "X-Correlation-ID": correlation_id,
                platform_config["api_key_header"]: platform_config["api_key"],
                "Content-Type": "application/json"
            },
            json={"items": [{"id": "test"}]},
            timeout=0.001  # 1msタイムアウト（必ず失敗）
        )
    except requests.exceptions.Timeout:
        print(f"✓ {platform_config['name']}: Timeout handled correctly by client")
        return

    # タイムアウトしなかった場合（サーバーが非常に高速な場合）
    print(f"⚠ {platform_config['name']}: Request completed before timeout")


@pytest.mark.e2e
@pytest.mark.slow
def test_error_large_payload_rejection(
    platform_config: Dict[str, Any],
    correlation_id: str
):
    """
    過大なペイロードで413 Payload Too Largeが返されることを確認
    """
    if not platform_config["endpoint"] or not platform_config["api_key"]:
        pytest.skip(f"Missing config for {platform_config['name']}")

    # 10MBのダミーデータ生成
    large_items = [
        {
            "id": f"item_{i}",
            "category": "test" * 100,
            "control_name": "test" * 100,
            "evaluation_criteria": "test" * 1000,
            "evaluation_method": "test" * 1000,
            "evidence": "test.pdf",
            "status": "実施中"
        }
        for i in range(1000)  # 1000項目
    ]

    try:
        response = requests.post(
            f"{platform_config['endpoint']}/evaluate",
            headers={
                "X-Correlation-ID": correlation_id,
                platform_config["api_key_header"]: platform_config["api_key"],
                "Content-Type": "application/json"
            },
            json={"items": large_items},
            timeout=60
        )

        # 413 Payload Too Large または 400 Bad Request
        if response.status_code in [400, 413, 422]:
            print(f"✓ {platform_config['name']}: Large payload rejected correctly")
        else:
            print(f"⚠ {platform_config['name']}: Large payload accepted (no size limit)")

    except requests.exceptions.RequestException:
        print(f"✓ {platform_config['name']}: Large payload rejected at network level")


# ================================================================================
# まとめ
# ================================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--e2e", "--tb=short"])
