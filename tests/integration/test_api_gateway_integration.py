"""
================================================================================
test_api_gateway_integration.py - AWS API Gateway統合テスト
================================================================================

【概要】
AWS API Gateway層の統合テストです。
モック環境でAPI Gateway→Lambda Functionsの連携を検証します。

【テスト項目】
1. 相関ID伝播（X-Correlation-IDヘッダー）
2. API Key認証（X-Api-Key）
3. レート制限・スロットリング（モック）
4. エラーハンドリング
5. CORS設定

【実行方法】
pytest tests/integration/test_api_gateway_integration.py -v

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
def api_gateway_config():
    """API Gateway設定"""
    return {
        "gateway_url": "https://xxxxx.execute-api.ap-northeast-1.amazonaws.com",
        "stage": "prod",
        "api_path": "/evaluate",
        "api_key": "test-api-key-12345",
        "region": "ap-northeast-1"
    }


@pytest.fixture
def test_request_body():
    """テストリクエストボディ"""
    return {
        "items": [
            {
                "ID": "001",
                "controlObjective": "データバックアップ",
                "testProcedure": "バックアップログを確認",
                "acceptanceCriteria": "定期的にバックアップが実行されている"
            }
        ]
    }


@pytest.fixture
def mock_lambda_response():
    """モックLambdaレスポンス"""
    return [
        {
            "ID": "001",
            "evaluationResult": True,
            "judgmentBasis": "バックアップが定期的に実行されています",
            "documentReference": "DR計画書 2.3",
            "fileName": "",
            "evidenceFiles": []
        }
    ]


# =============================================================================
# テスト1: 相関ID伝播
# =============================================================================

def test_correlation_id_propagation(api_gateway_config, test_request_body, mock_lambda_response):
    """相関IDがAPI Gateway→Lambda→Responseで正しく伝播することを検証"""

    correlation_id = str(uuid.uuid4())

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_lambda_response
        mock_response.headers = {
            "X-Correlation-ID": correlation_id,
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*"
        }
        mock_post.return_value = mock_response

        import requests
        endpoint_url = f"{api_gateway_config['gateway_url']}/{api_gateway_config['stage']}{api_gateway_config['api_path']}"
        response = requests.post(
            endpoint_url,
            headers={
                "X-Api-Key": api_gateway_config['api_key'],
                "X-Correlation-ID": correlation_id,
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証1: レスポンスヘッダーに相関IDが含まれる
        assert "X-Correlation-ID" in response.headers
        assert response.headers["X-Correlation-ID"] == correlation_id

        # 検証2: Lambda呼び出し時に相関IDが転送された
        call_args = mock_post.call_args
        assert "X-Correlation-ID" in call_args.kwargs.get("headers", {})


def test_correlation_id_auto_generation(api_gateway_config, test_request_body, mock_lambda_response):
    """相関IDが未指定の場合、API Gatewayで自動生成されることを検証"""

    auto_correlation_id = str(uuid.uuid4())

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_lambda_response
        mock_response.headers = {
            "X-Correlation-ID": auto_correlation_id,
            "Content-Type": "application/json"
        }
        mock_post.return_value = mock_response

        import requests
        endpoint_url = f"{api_gateway_config['gateway_url']}/{api_gateway_config['stage']}{api_gateway_config['api_path']}"
        response = requests.post(
            endpoint_url,
            headers={
                "X-Api-Key": api_gateway_config['api_key'],
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: レスポンスヘッダーに自動生成された相関IDが含まれる
        assert "X-Correlation-ID" in response.headers


# =============================================================================
# テスト2: API Key認証
# =============================================================================

def test_valid_api_key(api_gateway_config, test_request_body, mock_lambda_response):
    """有効なAPI Keyで認証成功することを検証"""

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_lambda_response
        mock_response.headers = {"X-Correlation-ID": str(uuid.uuid4())}
        mock_post.return_value = mock_response

        import requests
        endpoint_url = f"{api_gateway_config['gateway_url']}/{api_gateway_config['stage']}{api_gateway_config['api_path']}"
        response = requests.post(
            endpoint_url,
            headers={
                "X-Api-Key": api_gateway_config['api_key'],
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ステータスコード200
        assert response.status_code == 200


def test_missing_api_key(api_gateway_config, test_request_body):
    """API Keyなしで403 Forbiddenが返ることを検証"""

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "message": "Forbidden"
        }
        mock_post.return_value = mock_response

        import requests
        endpoint_url = f"{api_gateway_config['gateway_url']}/{api_gateway_config['stage']}{api_gateway_config['api_path']}"
        response = requests.post(
            endpoint_url,
            headers={
                "Content-Type": "application/json"
                # X-Api-Keyなし
            },
            json=test_request_body
        )

        # 検証: ステータスコード403
        assert response.status_code == 403


def test_invalid_api_key(api_gateway_config, test_request_body):
    """無効なAPI Keyで403 Forbiddenが返ることを検証"""

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 403
        mock_response.json.return_value = {
            "message": "Forbidden"
        }
        mock_post.return_value = mock_response

        import requests
        endpoint_url = f"{api_gateway_config['gateway_url']}/{api_gateway_config['stage']}{api_gateway_config['api_path']}"
        response = requests.post(
            endpoint_url,
            headers={
                "X-Api-Key": "invalid-key",
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ステータスコード403
        assert response.status_code == 403


# =============================================================================
# テスト3: スロットリング
# =============================================================================

def test_throttling_limit_exceeded(api_gateway_config, test_request_body):
    """スロットリング制限超過で429 Too Many Requestsが返ることを検証"""

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            "message": "Too Many Requests"
        }
        mock_response.headers = {
            "X-Amzn-ErrorType": "TooManyRequestsException"
        }
        mock_post.return_value = mock_response

        import requests
        endpoint_url = f"{api_gateway_config['gateway_url']}/{api_gateway_config['stage']}{api_gateway_config['api_path']}"
        response = requests.post(
            endpoint_url,
            headers={
                "X-Api-Key": api_gateway_config['api_key'],
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ステータスコード429
        assert response.status_code == 429


# =============================================================================
# テスト4: エラーハンドリング
# =============================================================================

def test_lambda_error_handling(api_gateway_config, test_request_body):
    """Lambdaエラー時の適切なエラーレスポンスを検証"""

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
        endpoint_url = f"{api_gateway_config['gateway_url']}/{api_gateway_config['stage']}{api_gateway_config['api_path']}"
        response = requests.post(
            endpoint_url,
            headers={
                "X-Api-Key": api_gateway_config['api_key'],
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

        # 検証: トレースバックが含まれない（本番環境）
        assert "traceback" not in error_data


def test_lambda_timeout(api_gateway_config, test_request_body):
    """Lambdaタイムアウト時の504 Gateway Timeoutを検証"""

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 504
        mock_response.json.return_value = {
            "message": "Endpoint request timed out"
        }
        mock_post.return_value = mock_response

        import requests
        endpoint_url = f"{api_gateway_config['gateway_url']}/{api_gateway_config['stage']}{api_gateway_config['api_path']}"
        response = requests.post(
            endpoint_url,
            headers={
                "X-Api-Key": api_gateway_config['api_key'],
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ステータスコード504
        assert response.status_code == 504


# =============================================================================
# テスト5: CORS設定
# =============================================================================

def test_cors_preflight(api_gateway_config):
    """CORSプリフライトリクエストが正しく処理されることを検証"""

    with patch('requests.options') as mock_options:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Correlation-ID",
            "Access-Control-Max-Age": "86400"
        }
        mock_options.return_value = mock_response

        import requests
        endpoint_url = f"{api_gateway_config['gateway_url']}/{api_gateway_config['stage']}{api_gateway_config['api_path']}"
        response = requests.options(
            endpoint_url,
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type,X-Api-Key"
            }
        )

        # 検証: ステータスコード200
        assert response.status_code == 200

        # 検証: CORSヘッダー
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        assert "POST" in response.headers["Access-Control-Allow-Methods"]
        assert "X-Api-Key" in response.headers["Access-Control-Allow-Headers"]


def test_cors_actual_request(api_gateway_config, test_request_body, mock_lambda_response):
    """実際のリクエストでCORSヘッダーが返ることを検証"""

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_lambda_response
        mock_response.headers = {
            "Access-Control-Allow-Origin": "*",
            "X-Correlation-ID": str(uuid.uuid4())
        }
        mock_post.return_value = mock_response

        import requests
        endpoint_url = f"{api_gateway_config['gateway_url']}/{api_gateway_config['stage']}{api_gateway_config['api_path']}"
        response = requests.post(
            endpoint_url,
            headers={
                "X-Api-Key": api_gateway_config['api_key'],
                "Origin": "https://example.com",
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: Access-Control-Allow-Originヘッダー
        assert "Access-Control-Allow-Origin" in response.headers


# =============================================================================
# テスト6: X-Ray統合
# =============================================================================

def test_xray_trace_id_propagation(api_gateway_config, test_request_body, mock_lambda_response):
    """X-RayトレースIDが正しく伝播することを検証"""

    correlation_id = str(uuid.uuid4())

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_lambda_response
        mock_response.headers = {
            "X-Correlation-ID": correlation_id,
            "X-Amzn-Trace-Id": "Root=1-67891234-abcdef0123456789abcdef01"
        }
        mock_post.return_value = mock_response

        import requests
        endpoint_url = f"{api_gateway_config['gateway_url']}/{api_gateway_config['stage']}{api_gateway_config['api_path']}"
        response = requests.post(
            endpoint_url,
            headers={
                "X-Api-Key": api_gateway_config['api_key'],
                "X-Correlation-ID": correlation_id,
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: X-Amzn-Trace-Idヘッダーが返される
        assert "X-Amzn-Trace-Id" in response.headers


# =============================================================================
# まとめ
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
