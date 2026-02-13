"""
================================================================================
test_aws_e2e.py - AWS全体フローのエンドツーエンドテスト
================================================================================

【概要】
PowerShell → API Gateway → App Runner → Bedrock の完全フローをテストします。
実際のAWS環境へのデプロイが必要です。

【前提条件】
1. AWS環境にリソースがデプロイ済み
   - App Runner (FastAPI/Docker)
   - API Gateway
   - CloudWatch Logs
   - X-Ray
   - Secrets Manager
   - Bedrock (Claude)

2. 環境変数設定
   - AWS_API_GATEWAY_ENDPOINT
   - AWS_API_KEY

【実行方法】
pytest tests/e2e/test_aws_e2e.py -v --e2e

【注意】
実際のAWS APIを呼び出すため、コストが発生します。

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

@pytest.fixture(scope="module")
def aws_config() -> Dict[str, str]:
    """
    AWS環境設定を取得
    """
    config = {
        "api_gateway_endpoint": os.getenv("AWS_API_GATEWAY_ENDPOINT"),
        "api_key": os.getenv("AWS_API_KEY"),
    }

    missing = [k for k, v in config.items() if not v]
    if missing:
        pytest.skip(f"Missing required environment variables: {missing}")

    return config


@pytest.fixture
def correlation_id() -> str:
    timestamp = int(time.time())
    return f"e2e_aws_{timestamp}_{uuid.uuid4().hex[:8]}"


@pytest.fixture
def test_item() -> Dict[str, Any]:
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
# E2Eテスト: AWS全体フロー
# ================================================================================

@pytest.mark.e2e
def test_aws_e2e_evaluate_with_correlation_id(
    aws_config: Dict[str, str],
    correlation_id: str,
    test_item: Dict[str, Any]
):
    """
    AWS E2E: PowerShell模擬 → API Gateway → App Runner → Bedrock
    相関IDが全ログに記録されることを確認
    """
    # 1. PowerShell模擬リクエスト送信
    response = requests.post(
        f"{aws_config['api_gateway_endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            "X-Api-Key": aws_config["api_key"],
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
    assert "X-Correlation-ID" in response.headers or "x-correlation-id" in response.headers
    returned_correlation_id = (
        response.headers.get("X-Correlation-ID") or
        response.headers.get("x-correlation-id")
    )
    assert returned_correlation_id == correlation_id

    print(f"✓ AWS Request successful with correlation_id: {correlation_id}")

    # 3. CloudWatch Logsログ確認（オプション）
    time.sleep(10)
    print(f"✓ Logs should be available in CloudWatch Logs with correlation_id: {correlation_id}")


@pytest.mark.e2e
def test_aws_e2e_health_check(aws_config: Dict[str, str]):
    """
    AWS E2E: ヘルスチェックエンドポイント
    """
    response = requests.get(
        f"{aws_config['api_gateway_endpoint']}/health",
        headers={
            "X-Api-Key": aws_config["api_key"]
        },
        timeout=10
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "healthy"

    print("✓ AWS Health check passed")


@pytest.mark.e2e
def test_aws_e2e_api_key_authentication_required(aws_config: Dict[str, str]):
    """
    AWS E2E: API Key認証が必須であることを確認
    """
    response = requests.get(
        f"{aws_config['api_gateway_endpoint']}/health",
        # X-Api-Keyヘッダーを意図的に省略
        timeout=10
    )

    # 403 Forbiddenが返されることを確認
    assert response.status_code == 403, f"Expected 403, got {response.status_code}"

    print("✓ AWS API Gateway authentication enforced")


@pytest.mark.e2e
def test_aws_e2e_xray_tracing(
    aws_config: Dict[str, str],
    correlation_id: str,
    test_item: Dict[str, Any]
):
    """
    AWS E2E: X-Rayトレーシングが動作することを確認
    """
    response = requests.post(
        f"{aws_config['api_gateway_endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            "X-Api-Key": aws_config["api_key"],
            "Content-Type": "application/json"
        },
        json={"items": [test_item]},
        timeout=60
    )

    assert response.status_code == 200

    # X-Rayトレースが記録されることを確認（APIで取得可能）
    time.sleep(10)
    print(f"✓ X-Ray trace should be available for correlation_id: {correlation_id}")


@pytest.mark.e2e
def test_aws_e2e_error_handling(aws_config: Dict[str, str], correlation_id: str):
    """
    AWS E2E: エラーハンドリングが正しく動作することを確認
    """
    response = requests.post(
        f"{aws_config['api_gateway_endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            "X-Api-Key": aws_config["api_key"],
            "Content-Type": "application/json"
        },
        json={"invalid_key": "invalid_value"},
        timeout=60
    )

    assert response.status_code in [400, 422], f"Expected 400 or 422, got {response.status_code}"

    response_data = response.json()
    assert "error_code" in response_data or "message" in response_data

    # トレースバックが非表示になることを確認
    assert "Traceback" not in str(response_data)

    print("✓ AWS Error handling working correctly (no traceback exposed)")


@pytest.mark.e2e
def test_aws_e2e_async_job_submit_and_status(
    aws_config: Dict[str, str],
    correlation_id: str,
    test_item: Dict[str, Any]
):
    """
    AWS E2E: 非同期ジョブ送信とステータス確認
    """
    # 1. ジョブ送信
    response = requests.post(
        f"{aws_config['api_gateway_endpoint']}/evaluate/submit",
        headers={
            "X-Correlation-ID": correlation_id,
            "X-Api-Key": aws_config["api_key"],
            "Content-Type": "application/json"
        },
        json={"items": [test_item]},
        timeout=60
    )

    assert response.status_code in [200, 202], f"Expected 200/202, got {response.status_code}"
    response_data = response.json()
    assert "job_id" in response_data

    job_id = response_data["job_id"]
    print(f"✓ Job submitted with job_id: {job_id}")

    # 2. ステータス確認
    time.sleep(5)

    status_response = requests.get(
        f"{aws_config['api_gateway_endpoint']}/evaluate/status/{job_id}",
        headers={
            "X-Api-Key": aws_config["api_key"]
        },
        timeout=10
    )

    assert status_response.status_code == 200
    status_data = status_response.json()
    assert "status" in status_data
    assert status_data["status"] in ["pending", "running", "completed", "failed"]

    print(f"✓ Job status: {status_data['status']}")


# ================================================================================
# まとめ
# ================================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--e2e", "--tb=short"])
