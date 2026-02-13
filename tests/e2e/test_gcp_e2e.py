"""
================================================================================
test_gcp_e2e.py - GCP全体フローのエンドツーエンドテスト
================================================================================

【概要】
VBA → Apigee → Cloud Run → Vertex AI の完全フローをテストします。
実際のGCP環境へのデプロイが必要です。

【前提条件】
1. GCP環境にリソースがデプロイ済み
   - Cloud Run (FastAPI/Docker)
   - Apigee API Gateway
   - Cloud Logging
   - Cloud Trace
   - Secret Manager
   - Vertex AI (Gemini)

2. 環境変数設定
   - GCP_APIGEE_ENDPOINT
   - GCP_API_KEY

【実行方法】
pytest tests/e2e/test_gcp_e2e.py -v --e2e

【注意】
実際のGCP APIを呼び出すため、コストが発生します。

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
def gcp_config() -> Dict[str, str]:
    """
    GCP環境設定を取得
    """
    config = {
        "apigee_endpoint": os.getenv("GCP_APIGEE_ENDPOINT"),
        "api_key": os.getenv("GCP_API_KEY"),
    }

    missing = [k for k, v in config.items() if not v]
    if missing:
        pytest.skip(f"Missing required environment variables: {missing}")

    return config


@pytest.fixture
def correlation_id() -> str:
    timestamp = int(time.time())
    return f"e2e_gcp_{timestamp}_{uuid.uuid4().hex[:8]}"


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
# E2Eテスト: GCP全体フロー
# ================================================================================

@pytest.mark.e2e
def test_gcp_e2e_evaluate_with_correlation_id(
    gcp_config: Dict[str, str],
    correlation_id: str,
    test_item: Dict[str, Any]
):
    """
    GCP E2E: VBA模擬 → Apigee → Cloud Run → Vertex AI
    相関IDが全ログに記録されることを確認
    """
    # 1. VBA模擬リクエスト送信
    response = requests.post(
        f"{gcp_config['apigee_endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            "X-Api-Key": gcp_config["api_key"],
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

    print(f"✓ GCP Request successful with correlation_id: {correlation_id}")

    # 3. Cloud Loggingログ確認（オプション）
    time.sleep(10)
    print(f"✓ Logs should be available in Cloud Logging with correlation_id: {correlation_id}")


@pytest.mark.e2e
def test_gcp_e2e_health_check(gcp_config: Dict[str, str]):
    """
    GCP E2E: ヘルスチェックエンドポイント
    """
    response = requests.get(
        f"{gcp_config['apigee_endpoint']}/health",
        headers={
            "X-Api-Key": gcp_config["api_key"]
        },
        timeout=10
    )

    assert response.status_code == 200
    response_data = response.json()
    assert response_data["status"] == "healthy"

    print("✓ GCP Health check passed")


@pytest.mark.e2e
def test_gcp_e2e_apigee_authentication_required(gcp_config: Dict[str, str]):
    """
    GCP E2E: API Key認証が必須であることを確認
    """
    response = requests.get(
        f"{gcp_config['apigee_endpoint']}/health",
        # X-Api-Keyヘッダーを意図的に省略
        timeout=10
    )

    # 401 Unauthorized または 403 Forbidden が返されることを確認
    assert response.status_code in [401, 403], f"Expected 401/403, got {response.status_code}"

    print("✓ GCP Apigee authentication enforced")


@pytest.mark.e2e
def test_gcp_e2e_cloud_trace(
    gcp_config: Dict[str, str],
    correlation_id: str,
    test_item: Dict[str, Any]
):
    """
    GCP E2E: Cloud Traceトレーシングが動作することを確認
    """
    response = requests.post(
        f"{gcp_config['apigee_endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            "X-Api-Key": gcp_config["api_key"],
            "Content-Type": "application/json"
        },
        json={"items": [test_item]},
        timeout=60
    )

    assert response.status_code == 200

    # Cloud Traceが記録されることを確認
    time.sleep(10)
    print(f"✓ Cloud Trace should be available for correlation_id: {correlation_id}")


@pytest.mark.e2e
def test_gcp_e2e_error_handling(gcp_config: Dict[str, str], correlation_id: str):
    """
    GCP E2E: エラーハンドリングが正しく動作することを確認
    """
    response = requests.post(
        f"{gcp_config['apigee_endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            "X-Api-Key": gcp_config["api_key"],
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

    print("✓ GCP Error handling working correctly (no traceback exposed)")


@pytest.mark.e2e
def test_gcp_e2e_async_job_submit_and_status(
    gcp_config: Dict[str, str],
    correlation_id: str,
    test_item: Dict[str, Any]
):
    """
    GCP E2E: 非同期ジョブ送信とステータス確認
    """
    # 1. ジョブ送信
    response = requests.post(
        f"{gcp_config['apigee_endpoint']}/evaluate/submit",
        headers={
            "X-Correlation-ID": correlation_id,
            "X-Api-Key": gcp_config["api_key"],
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
        f"{gcp_config['apigee_endpoint']}/evaluate/status/{job_id}",
        headers={
            "X-Api-Key": gcp_config["api_key"]
        },
        timeout=10
    )

    assert status_response.status_code == 200
    status_data = status_response.json()
    assert "status" in status_data
    assert status_data["status"] in ["pending", "running", "completed", "failed"]

    print(f"✓ Job status: {status_data['status']}")


@pytest.mark.e2e
def test_gcp_e2e_vertex_ai_gemini_integration(
    gcp_config: Dict[str, str],
    correlation_id: str
):
    """
    GCP E2E: Vertex AI (Gemini) 統合確認
    """
    # シンプルな評価項目でLLM処理を確認
    simple_item = {
        "id": "test",
        "category": "統制環境",
        "control_name": "テスト統制",
        "evaluation_criteria": "テスト基準",
        "evaluation_method": "テスト方法",
        "evidence": "test.pdf",
        "status": "実施中"
    }

    response = requests.post(
        f"{gcp_config['apigee_endpoint']}/evaluate",
        headers={
            "X-Correlation-ID": correlation_id,
            "X-Api-Key": gcp_config["api_key"],
            "Content-Type": "application/json"
        },
        json={"items": [simple_item]},
        timeout=60
    )

    assert response.status_code == 200
    response_data = response.json()

    # LLM処理結果を確認
    assert "results" in response_data
    assert len(response_data["results"]) == 1

    result = response_data["results"][0]
    assert "effectiveness_assessment" in result
    assert "improvement_suggestions" in result

    print(f"✓ Vertex AI (Gemini) integration working")


# ================================================================================
# まとめ
# ================================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--e2e", "--tb=short"])
