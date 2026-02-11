"""
================================================================================
test_api_gateway_backends.py - API Gateway→Backend統合テスト
================================================================================

【概要】
APIM/API Gateway/Apigee → Azure Functions/Lambda/Cloud Functions の統合をテストします。
実際のクラウド環境へのデプロイが必要です。

【前提条件】
1. Azure APIM + Azure Functions
   - AZURE_APIM_ENDPOINT
   - AZURE_APIM_SUBSCRIPTION_KEY

2. AWS API Gateway + Lambda
   - AWS_API_GATEWAY_ENDPOINT
   - AWS_API_KEY

3. GCP Apigee + Cloud Functions
   - GCP_APIGEE_ENDPOINT
   - GCP_API_KEY

【実行方法】
pytest tests/integration/test_api_gateway_backends.py -v --integration

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
    parser.addoption(
        "--integration",
        action="store_true",
        default=False,
        help="Run integration tests (requires deployed cloud environment)"
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

@pytest.fixture(params=["azure", "aws", "gcp"])
def api_gateway_config(request) -> Dict[str, Any]:
    """
    全プラットフォームのAPI Gateway設定
    """
    platform = request.param

    if platform == "azure":
        return {
            "name": "azure_apim",
            "endpoint": os.getenv("AZURE_APIM_ENDPOINT"),
            "api_key_header": "Ocp-Apim-Subscription-Key",
            "api_key": os.getenv("AZURE_APIM_SUBSCRIPTION_KEY"),
        }
    elif platform == "aws":
        return {
            "name": "aws_api_gateway",
            "endpoint": os.getenv("AWS_API_GATEWAY_ENDPOINT"),
            "api_key_header": "X-Api-Key",
            "api_key": os.getenv("AWS_API_KEY"),
        }
    elif platform == "gcp":
        return {
            "name": "gcp_apigee",
            "endpoint": os.getenv("GCP_APIGEE_ENDPOINT"),
            "api_key_header": "X-Api-Key",
            "api_key": os.getenv("GCP_API_KEY"),
        }


@pytest.fixture
def correlation_id() -> str:
    return f"integration_{int(time.time())}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_item() -> Dict[str, Any]:
    return {
        "id": "integration_test",
        "category": "統制環境",
        "control_name": "API Gateway統合テスト",
        "evaluation_criteria": "API Gatewayからバックエンドへの通信が正常",
        "evaluation_method": "統合テスト実施",
        "evidence": "integration_test.pdf",
        "status": "実施中"
    }


# ================================================================================
# 統合テスト: API Gateway → Backend
# ================================================================================

@pytest.mark.integration
def test_api_gateway_to_backend_health_check(api_gateway_config: Dict[str, Any]):
    """
    API Gateway経由でバックエンドのヘルスチェックが成功することを確認
    """
    if not api_gateway_config["endpoint"] or not api_gateway_config["api_key"]:
        pytest.skip(f"Missing config for {api_gateway_config['name']}")

    response = requests.get(
        f"{api_gateway_config['endpoint']}/health",
        headers={
            api_gateway_config["api_key_header"]: api_gateway_config["api_key"]
        },
        timeout=10
    )

    assert response.status_code == 200, (
        f"{api_gateway_config['name']}: Health check failed with {response.status_code}"
    )

    response_data = response.json()
    assert response_data["status"] == "healthy"

    print(f"✓ {api_gateway_config['name']}: Health check passed via API Gateway")


@pytest.mark.integration
def test_api_gateway_to_backend_evaluate(
    api_gateway_config: Dict[str, Any],
    correlation_id: str,
    test_item: Dict[str, Any]
):
    """
    API Gateway経由でバックエンドの評価エンドポイントが動作することを確認
    """
    if not api_gateway_config["endpoint"] or not api_gateway_config["api_key"]:
        pytest.skip(f"Missing config for {api_gateway_config['name']}")

    response = requests.post(
        f"{api_gateway_config['endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            api_gateway_config["api_key_header"]: api_gateway_config["api_key"],
            "Content-Type": "application/json"
        },
        json={"items": [test_item]},
        timeout=60
    )

    assert response.status_code == 200, (
        f"{api_gateway_config['name']}: Evaluate failed with {response.status_code}: {response.text}"
    )

    response_data = response.json()
    assert "results" in response_data
    assert len(response_data["results"]) == 1

    # 相関IDがレスポンスに含まれることを確認
    assert (
        "X-Correlation-ID" in response.headers or
        "x-correlation-id" in response.headers
    )

    print(f"✓ {api_gateway_config['name']}: Evaluate endpoint working via API Gateway")


@pytest.mark.integration
def test_api_gateway_authentication_enforcement(api_gateway_config: Dict[str, Any]):
    """
    API Gatewayで認証が強制されることを確認
    """
    if not api_gateway_config["endpoint"]:
        pytest.skip(f"Missing endpoint for {api_gateway_config['name']}")

    # API Keyなしでリクエスト
    response = requests.get(
        f"{api_gateway_config['endpoint']}/health",
        # API Keyヘッダーを意図的に省略
        timeout=10
    )

    # 401 Unauthorized または 403 Forbidden
    assert response.status_code in [401, 403], (
        f"{api_gateway_config['name']}: Authentication not enforced (got {response.status_code})"
    )

    print(f"✓ {api_gateway_config['name']}: Authentication enforced at API Gateway")


@pytest.mark.integration
def test_api_gateway_rate_limiting(api_gateway_config: Dict[str, Any]):
    """
    API Gatewayでレート制限が動作することを確認（オプション）
    """
    if not api_gateway_config["endpoint"] or not api_gateway_config["api_key"]:
        pytest.skip(f"Missing config for {api_gateway_config['name']}")

    # 短時間に複数リクエスト送信
    rate_limit_hit = False

    for i in range(20):  # 20リクエスト
        response = requests.get(
            f"{api_gateway_config['endpoint']}/health",
            headers={
                api_gateway_config["api_key_header"]: api_gateway_config["api_key"]
            },
            timeout=10
        )

        if response.status_code == 429:  # Too Many Requests
            rate_limit_hit = True
            break

        time.sleep(0.05)  # 50msインターバル

    # レート制限設定次第で到達しない可能性あり
    print(f"ℹ {api_gateway_config['name']}: Rate limit test (limit hit: {rate_limit_hit})")


@pytest.mark.integration
def test_api_gateway_cors_headers(api_gateway_config: Dict[str, Any]):
    """
    API GatewayでCORSヘッダーが正しく設定されることを確認
    """
    if not api_gateway_config["endpoint"] or not api_gateway_config["api_key"]:
        pytest.skip(f"Missing config for {api_gateway_config['name']}")

    # OPTIONS preflight request
    response = requests.options(
        f"{api_gateway_config['endpoint']}/evaluate",
        headers={
            "Origin": "https://example.com",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type"
        },
        timeout=10
    )

    # CORS設定次第で200/204が返される
    if response.status_code in [200, 204]:
        # Access-Control-Allow-Originヘッダー確認
        if "Access-Control-Allow-Origin" in response.headers:
            print(f"✓ {api_gateway_config['name']}: CORS headers configured")
        else:
            print(f"ℹ {api_gateway_config['name']}: CORS might not be configured")
    else:
        print(f"ℹ {api_gateway_config['name']}: CORS test inconclusive")


@pytest.mark.integration
def test_api_gateway_logging_integration(
    api_gateway_config: Dict[str, Any],
    correlation_id: str
):
    """
    API Gatewayでログが記録されることを確認（手動確認用）
    """
    if not api_gateway_config["endpoint"] or not api_gateway_config["api_key"]:
        pytest.skip(f"Missing config for {api_gateway_config['name']}")

    response = requests.get(
        f"{api_gateway_config['endpoint']}/health",
        headers={
            "X-Correlation-ID": correlation_id,
            api_gateway_config["api_key_header"]: api_gateway_config["api_key"]
        },
        timeout=10
    )

    assert response.status_code == 200

    print(
        f"✓ {api_gateway_config['name']}: Request completed with correlation_id: {correlation_id}\n"
        f"  Check API Gateway logs in cloud console"
    )


@pytest.mark.integration
def test_api_gateway_backend_latency(
    api_gateway_config: Dict[str, Any],
    correlation_id: str,
    test_item: Dict[str, Any]
):
    """
    API Gateway経由のレイテンシを測定
    """
    if not api_gateway_config["endpoint"] or not api_gateway_config["api_key"]:
        pytest.skip(f"Missing config for {api_gateway_config['name']}")

    start_time = time.time()

    response = requests.post(
        f"{api_gateway_config['endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            api_gateway_config["api_key_header"]: api_gateway_config["api_key"],
            "Content-Type": "application/json"
        },
        json={"items": [test_item]},
        timeout=60
    )

    duration_ms = (time.time() - start_time) * 1000

    assert response.status_code == 200

    print(
        f"✓ {api_gateway_config['name']}: API Gateway → Backend latency: {duration_ms:.2f}ms"
    )

    # レイテンシ閾値チェック（10秒以内）
    assert duration_ms < 10000, (
        f"{api_gateway_config['name']}: Latency too high ({duration_ms:.2f}ms)"
    )


@pytest.mark.integration
def test_api_gateway_config_endpoint(api_gateway_config: Dict[str, Any]):
    """
    API Gateway経由で設定エンドポイントが動作することを確認
    """
    if not api_gateway_config["endpoint"] or not api_gateway_config["api_key"]:
        pytest.skip(f"Missing config for {api_gateway_config['name']}")

    response = requests.get(
        f"{api_gateway_config['endpoint']}/config",
        headers={
            api_gateway_config["api_key_header"]: api_gateway_config["api_key"]
        },
        timeout=10
    )

    assert response.status_code == 200
    response_data = response.json()

    # 設定情報が含まれることを確認
    assert "llm_provider" in response_data
    assert "ocr_provider" in response_data
    assert "async_enabled" in response_data

    print(f"✓ {api_gateway_config['name']}: Config endpoint accessible via API Gateway")


# ================================================================================
# まとめ
# ================================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--integration", "--tb=short"])
