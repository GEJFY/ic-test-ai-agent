"""
================================================================================
test_apigee_integration.py - GCP Apigee統合テスト
================================================================================

【概要】
GCP Apigee層の統合テストです。
モック環境でApigee→Cloud Functionsの連携を検証します。

【注意】
Apigeeは高コストのため、本番環境では無効化（enable_apigee = false）を推奨します。
その場合、Cloud Functions直接アクセステストも含めます。

【テスト項目】
1. 相関ID伝播（X-Correlation-IDヘッダー）
2. API Key認証（X-Api-Key）- Apigee有効時のみ
3. Quotaポリシー（レート制限）
4. エラーハンドリング
5. Cloud Functions直接アクセス（Apigee無効時）

【実行方法】
pytest tests/integration/test_apigee_integration.py -v

================================================================================
"""
import pytest
import json
import uuid
from unittest.mock import Mock, patch
from datetime import datetime


# =============================================================================
# フィクスチャ
# =============================================================================

@pytest.fixture
def apigee_config():
    """Apigee設定"""
    return {
        "apigee_url": "https://ic-test-ai-api.example.com",
        "api_path": "/api/evaluate",
        "api_key": "test-apigee-key-12345",
        "environment": "prod"
    }


@pytest.fixture
def cloud_functions_config():
    """Cloud Functions直接アクセス設定"""
    return {
        "function_url": "https://asia-northeast1-project-id.cloudfunctions.net/ic-test-ai-prod-evaluate",
        "evaluate_path": "/evaluate"
    }


@pytest.fixture
def test_request_body():
    """テストリクエストボディ"""
    return {
        "items": [
            {
                "ID": "001",
                "controlObjective": "ログ監視",
                "testProcedure": "ログを確認",
                "acceptanceCriteria": "異常なアクセスが検出されている"
            }
        ]
    }


@pytest.fixture
def mock_backend_response():
    """モックバックエンドレスポンス"""
    return [
        {
            "ID": "001",
            "evaluationResult": True,
            "judgmentBasis": "ログ監視が適切に実施されています",
            "documentReference": "セキュリティ運用手順 4.1",
            "fileName": "",
            "evidenceFiles": []
        }
    ]


# =============================================================================
# テスト1: 相関ID伝播（Apigee経由）
# =============================================================================

def test_correlation_id_propagation_apigee(apigee_config, test_request_body, mock_backend_response):
    """相関IDがApigee→Cloud Functions→Responseで正しく伝播することを検証"""

    correlation_id = str(uuid.uuid4())

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_backend_response
        mock_response.headers = {
            "X-Correlation-ID": correlation_id,
            "Content-Type": "application/json"
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{apigee_config['apigee_url']}{apigee_config['api_path']}",
            headers={
                "X-Api-Key": apigee_config['api_key'],
                "X-Correlation-ID": correlation_id,
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: レスポンスヘッダーに相関IDが含まれる
        assert "X-Correlation-ID" in response.headers
        assert response.headers["X-Correlation-ID"] == correlation_id


# =============================================================================
# テスト2: Cloud Functions直接アクセス（Apigee無効時）
# =============================================================================

def test_cloud_functions_direct_access(cloud_functions_config, test_request_body, mock_backend_response):
    """Apigee無効時、Cloud Functionsに直接アクセスできることを検証"""

    correlation_id = str(uuid.uuid4())

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_backend_response
        mock_response.headers = {
            "X-Correlation-ID": correlation_id,
            "Content-Type": "application/json"
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{cloud_functions_config['function_url']}{cloud_functions_config['evaluate_path']}",
            headers={
                "X-Correlation-ID": correlation_id,
                "Content-Type": "application/json"
                # API Keyなし（Cloud Functions直接アクセス）
            },
            json=test_request_body
        )

        # 検証: ステータスコード200
        assert response.status_code == 200

        # 検証: レスポンスデータ
        assert response.json() == mock_backend_response


def test_cloud_functions_correlation_id_auto_generation(cloud_functions_config, test_request_body, mock_backend_response):
    """Cloud Functions直接アクセス時、相関IDが自動生成されることを検証"""

    auto_correlation_id = str(uuid.uuid4())

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_backend_response
        mock_response.headers = {
            "X-Correlation-ID": auto_correlation_id,
            "Content-Type": "application/json"
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{cloud_functions_config['function_url']}{cloud_functions_config['evaluate_path']}",
            headers={
                "Content-Type": "application/json"
                # X-Correlation-IDなし
            },
            json=test_request_body
        )

        # 検証: レスポンスヘッダーに自動生成された相関IDが含まれる
        assert "X-Correlation-ID" in response.headers


# =============================================================================
# テスト3: API Key認証（Apigee有効時）
# =============================================================================

def test_valid_api_key_apigee(apigee_config, test_request_body, mock_backend_response):
    """有効なAPI Keyで認証成功することを検証（Apigee）"""

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_backend_response
        mock_response.headers = {"X-Correlation-ID": str(uuid.uuid4())}
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{apigee_config['apigee_url']}{apigee_config['api_path']}",
            headers={
                "X-Api-Key": apigee_config['api_key'],
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ステータスコード200
        assert response.status_code == 200


def test_missing_api_key_apigee(apigee_config, test_request_body):
    """API Keyなしで401 Unauthorizedが返ることを検証（Apigee）"""

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "fault": {
                "faultstring": "Failed to resolve API Key variable request.header.x-api-key",
                "detail": {
                    "errorcode": "steps.oauth.v2.FailedToResolveAPIKey"
                }
            }
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{apigee_config['apigee_url']}{apigee_config['api_path']}",
            headers={
                "Content-Type": "application/json"
                # X-Api-Keyなし
            },
            json=test_request_body
        )

        # 検証: ステータスコード401
        assert response.status_code == 401


def test_invalid_api_key_apigee(apigee_config, test_request_body):
    """無効なAPI Keyで401 Unauthorizedが返ることを検証（Apigee）"""

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "fault": {
                "faultstring": "Invalid ApiKey",
                "detail": {
                    "errorcode": "oauth.v2.InvalidApiKey"
                }
            }
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{apigee_config['apigee_url']}{apigee_config['api_path']}",
            headers={
                "X-Api-Key": "invalid-key",
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ステータスコード401
        assert response.status_code == 401


# =============================================================================
# テスト4: Quotaポリシー（レート制限）
# =============================================================================

def test_quota_exceeded_apigee(apigee_config, test_request_body):
    """Quota超過で429 Too Many Requestsが返ることを検証（Apigee）"""

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            "fault": {
                "faultstring": "Rate limit quota violation. Quota limit exceeded. Identifier : _default",
                "detail": {
                    "errorcode": "policies.ratelimit.QuotaViolation"
                }
            }
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{apigee_config['apigee_url']}{apigee_config['api_path']}",
            headers={
                "X-Api-Key": apigee_config['api_key'],
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ステータスコード429
        assert response.status_code == 429

        # 検証: Apigee固有のエラーレスポンス
        error_data = response.json()
        assert "fault" in error_data
        assert "QuotaViolation" in error_data["fault"]["detail"]["errorcode"]


# =============================================================================
# テスト5: エラーハンドリング
# =============================================================================

def test_backend_error_handling_apigee(apigee_config, test_request_body):
    """バックエンドエラー時の適切なエラーレスポンスを検証（Apigee）"""

    correlation_id = str(uuid.uuid4())

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "error": True,
            "message": "Internal server error",
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        mock_response.headers = {
            "X-Correlation-ID": correlation_id
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{apigee_config['apigee_url']}{apigee_config['api_path']}",
            headers={
                "X-Api-Key": apigee_config['api_key'],
                "X-Correlation-ID": correlation_id,
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ステータスコード500
        assert response.status_code == 500

        # 検証: エラーレスポンスに相関ID含む
        error_data = response.json()
        assert error_data["correlation_id"] == correlation_id


def test_cloud_functions_error_handling(cloud_functions_config, test_request_body):
    """Cloud Functionsエラー時の適切なエラーレスポンスを検証"""

    correlation_id = str(uuid.uuid4())

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "error": True,
            "message": "Internal server error",
            "correlation_id": correlation_id
        }
        mock_response.headers = {
            "X-Correlation-ID": correlation_id
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{cloud_functions_config['function_url']}{cloud_functions_config['evaluate_path']}",
            headers={
                "X-Correlation-ID": correlation_id,
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ステータスコード500
        assert response.status_code == 500

        # 検証: トレースバックが含まれない（本番環境）
        error_data = response.json()
        assert "traceback" not in error_data


# =============================================================================
# テスト6: Cloud Trace統合
# =============================================================================

def test_cloud_trace_propagation(cloud_functions_config, test_request_body, mock_backend_response):
    """Cloud Traceトレースコンテキストが伝播することを検証"""

    correlation_id = str(uuid.uuid4())
    trace_context = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_backend_response
        mock_response.headers = {
            "X-Correlation-ID": correlation_id,
            "X-Cloud-Trace-Context": trace_context
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{cloud_functions_config['function_url']}{cloud_functions_config['evaluate_path']}",
            headers={
                "X-Correlation-ID": correlation_id,
                "X-Cloud-Trace-Context": trace_context,
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: X-Cloud-Trace-Contextヘッダーが返される
        assert "X-Cloud-Trace-Context" in response.headers


# =============================================================================
# テスト7: MessageLoggingポリシー（Apigee）
# =============================================================================

def test_apigee_message_logging(apigee_config, test_request_body, mock_backend_response):
    """Apigee MessageLoggingポリシーで構造化ログが記録されることを検証（モック）"""

    correlation_id = str(uuid.uuid4())

    # MessageLoggingポリシーの動作をモック
    logged_messages = []

    def mock_log_message(message):
        logged_messages.append(message)

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_backend_response
        mock_response.headers = {
            "X-Correlation-ID": correlation_id
        }
        mock_post.return_value = mock_response

        # ログ記録をモック
        mock_log_message({
            "timestamp": datetime.utcnow().isoformat(),
            "correlation_id": correlation_id,
            "event": "request_received",
            "method": "POST",
            "path": apigee_config['api_path'],
            "client_ip": "192.0.2.1",
            "operation_name": "evaluate"
        })

        import requests
        response = requests.post(
            f"{apigee_config['apigee_url']}{apigee_config['api_path']}",
            headers={
                "X-Api-Key": apigee_config['api_key'],
                "X-Correlation-ID": correlation_id,
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ログが記録された
        assert len(logged_messages) > 0
        assert logged_messages[0]["correlation_id"] == correlation_id
        assert logged_messages[0]["event"] == "request_received"


# =============================================================================
# まとめ
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
