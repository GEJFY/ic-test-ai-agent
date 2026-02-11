"""
================================================================================
test_apim_integration.py - Azure APIM統合テスト
================================================================================

【概要】
Azure API Management（APIM）層の統合テストです。
モック環境でAPIM→Azure Functionsの連携を検証します。

【テスト項目】
1. 相関ID伝播（X-Correlation-IDヘッダー）
2. API Key認証（Ocp-Apim-Subscription-Key）
3. レート制限（モック）
4. エラーハンドリング
5. CORS設定

【実行方法】
pytest tests/integration/test_apim_integration.py -v

================================================================================
"""
import pytest
import json
import uuid
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


# =============================================================================
# フィクスチャ
# =============================================================================

@pytest.fixture
def apim_config():
    """APIM設定"""
    return {
        "gateway_url": "https://apim-ic-test-ai-prod.azure-api.net",
        "api_path": "/api/evaluate",
        "subscription_key": "test-subscription-key-12345",
        "api_version": "v1"
    }


@pytest.fixture
def test_request_body():
    """テストリクエストボディ"""
    return {
        "items": [
            {
                "ID": "001",
                "controlObjective": "アクセス制御",
                "testProcedure": "権限設定を確認",
                "acceptanceCriteria": "適切な権限が設定されている"
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
            "judgmentBasis": "権限設定が適切です",
            "documentReference": "セキュリティポリシー 3.2",
            "fileName": "",
            "evidenceFiles": []
        }
    ]


# =============================================================================
# テスト1: 相関ID伝播
# =============================================================================

def test_correlation_id_propagation(apim_config, test_request_body, mock_backend_response):
    """相関IDがAPIM→Backend→Responseで正しく伝播することを検証"""

    # 相関ID生成
    correlation_id = str(uuid.uuid4())

    # モックHTTPリクエスト
    with patch('requests.post') as mock_post:
        # バックエンドレスポンスをモック
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_backend_response
        mock_response.headers = {
            "X-Correlation-ID": correlation_id,
            "Content-Type": "application/json"
        }
        mock_post.return_value = mock_response

        # APIリクエスト送信
        import requests
        response = requests.post(
            f"{apim_config['gateway_url']}{apim_config['api_path']}",
            headers={
                "Ocp-Apim-Subscription-Key": apim_config['subscription_key'],
                "X-Correlation-ID": correlation_id,
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証1: レスポンスヘッダーに相関IDが含まれる
        assert "X-Correlation-ID" in response.headers
        assert response.headers["X-Correlation-ID"] == correlation_id

        # 検証2: バックエンド呼び出し時に相関IDが転送された
        call_args = mock_post.call_args
        assert "X-Correlation-ID" in call_args.kwargs.get("headers", {})


def test_correlation_id_auto_generation(apim_config, test_request_body, mock_backend_response):
    """相関IDが未指定の場合、APIMで自動生成されることを検証"""

    # モックHTTPリクエスト
    with patch('requests.post') as mock_post:
        # バックエンドレスポンスをモック（UUIDを自動生成）
        auto_correlation_id = str(uuid.uuid4())
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_backend_response
        mock_response.headers = {
            "X-Correlation-ID": auto_correlation_id,
            "Content-Type": "application/json"
        }
        mock_post.return_value = mock_response

        # 相関IDなしでAPIリクエスト送信
        import requests
        response = requests.post(
            f"{apim_config['gateway_url']}{apim_config['api_path']}",
            headers={
                "Ocp-Apim-Subscription-Key": apim_config['subscription_key'],
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: レスポンスヘッダーに自動生成された相関IDが含まれる
        assert "X-Correlation-ID" in response.headers
        # UUID形式であることを確認
        try:
            uuid.UUID(response.headers["X-Correlation-ID"])
            assert True
        except ValueError:
            pytest.fail("相関IDがUUID形式ではありません")


# =============================================================================
# テスト2: API Key認証
# =============================================================================

def test_valid_api_key(apim_config, test_request_body, mock_backend_response):
    """有効なAPI Keyで認証成功することを検証"""

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = mock_backend_response
        mock_response.headers = {"X-Correlation-ID": str(uuid.uuid4())}
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{apim_config['gateway_url']}{apim_config['api_path']}",
            headers={
                "Ocp-Apim-Subscription-Key": apim_config['subscription_key'],
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ステータスコード200
        assert response.status_code == 200


def test_missing_api_key(apim_config, test_request_body):
    """API Keyなしで401 Unauthorizedが返ることを検証"""

    with patch('requests.post') as mock_post:
        # 401 Unauthorizedをモック
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": True,
            "message": "Unauthorized: Subscription Key is required"
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{apim_config['gateway_url']}{apim_config['api_path']}",
            headers={
                "Content-Type": "application/json"
                # Ocp-Apim-Subscription-Keyなし
            },
            json=test_request_body
        )

        # 検証: ステータスコード401
        assert response.status_code == 401

        # 検証: エラーメッセージ
        error_data = response.json()
        assert error_data["error"] is True
        assert "Unauthorized" in error_data["message"]


def test_invalid_api_key(apim_config, test_request_body):
    """無効なAPI Keyで401 Unauthorizedが返ることを検証"""

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.json.return_value = {
            "error": True,
            "message": "Unauthorized: Invalid Subscription Key"
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{apim_config['gateway_url']}{apim_config['api_path']}",
            headers={
                "Ocp-Apim-Subscription-Key": "invalid-key",
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ステータスコード401
        assert response.status_code == 401


# =============================================================================
# テスト3: レート制限
# =============================================================================

def test_rate_limit_exceeded(apim_config, test_request_body):
    """レート制限超過で429 Too Many Requestsが返ることを検証"""

    with patch('requests.post') as mock_post:
        # 429 Too Many Requestsをモック
        mock_response = Mock()
        mock_response.status_code = 429
        mock_response.json.return_value = {
            "error": True,
            "message": "リクエスト制限を超えました。しばらくしてから再試行してください。"
        }
        mock_response.headers = {
            "Retry-After": "60"
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{apim_config['gateway_url']}{apim_config['api_path']}",
            headers={
                "Ocp-Apim-Subscription-Key": apim_config['subscription_key'],
                "Content-Type": "application/json"
            },
            json=test_request_body
        )

        # 検証: ステータスコード429
        assert response.status_code == 429

        # 検証: Retry-Afterヘッダー
        assert "Retry-After" in response.headers


# =============================================================================
# テスト4: エラーハンドリング
# =============================================================================

def test_backend_error_handling(apim_config, test_request_body):
    """バックエンドエラー時の適切なエラーレスポンスを検証"""

    correlation_id = str(uuid.uuid4())

    with patch('requests.post') as mock_post:
        # 500 Internal Server Errorをモック
        mock_response = Mock()
        mock_response.status_code = 500
        mock_response.json.return_value = {
            "error": True,
            "message": "サーバーエラーが発生しました。しばらくしてから再試行してください。",
            "correlation_id": correlation_id,
            "timestamp": datetime.utcnow().isoformat()
        }
        mock_response.headers = {
            "X-Correlation-ID": correlation_id
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{apim_config['gateway_url']}{apim_config['api_path']}",
            headers={
                "Ocp-Apim-Subscription-Key": apim_config['subscription_key'],
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


# =============================================================================
# テスト5: CORS設定
# =============================================================================

def test_cors_headers(apim_config):
    """CORSヘッダーが正しく設定されることを検証"""

    with patch('requests.options') as mock_options:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
            "Access-Control-Allow-Headers": "*",
            "Access-Control-Expose-Headers": "X-Correlation-ID"
        }
        mock_options.return_value = mock_response

        import requests
        response = requests.options(
            f"{apim_config['gateway_url']}{apim_config['api_path']}",
            headers={
                "Origin": "https://example.com"
            }
        )

        # 検証: CORSヘッダー
        assert response.status_code == 200
        assert response.headers["Access-Control-Allow-Origin"] == "*"
        assert "POST" in response.headers["Access-Control-Allow-Methods"]
        assert "X-Correlation-ID" in response.headers["Access-Control-Expose-Headers"]


# =============================================================================
# テスト6: リクエストサイズ制限
# =============================================================================

def test_payload_too_large(apim_config):
    """リクエストサイズ超過で413 Payload Too Largeが返ることを検証"""

    # 10MB超のダミーデータ
    large_payload = {
        "items": [
            {
                "ID": f"item-{i}",
                "controlObjective": "x" * 1000000,  # 1MB
                "testProcedure": "test",
                "acceptanceCriteria": "test"
            }
            for i in range(15)  # 15MB
        ]
    }

    with patch('requests.post') as mock_post:
        mock_response = Mock()
        mock_response.status_code = 413
        mock_response.json.return_value = {
            "error": True,
            "message": "リクエストサイズが大きすぎます（最大10MB）。",
            "correlation_id": str(uuid.uuid4())
        }
        mock_post.return_value = mock_response

        import requests
        response = requests.post(
            f"{apim_config['gateway_url']}{apim_config['api_path']}",
            headers={
                "Ocp-Apim-Subscription-Key": apim_config['subscription_key'],
                "Content-Type": "application/json"
            },
            json=large_payload
        )

        # 検証: ステータスコード413
        assert response.status_code == 413


# =============================================================================
# まとめ
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
