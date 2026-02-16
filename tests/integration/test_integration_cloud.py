# -*- coding: utf-8 -*-
"""
================================================================================
test_integration_cloud.py - クラウド環境の結合テスト
================================================================================

【テスト対象】
- Azure Foundry LLM認証・接続テスト
- Azure Storage 認証・接続テスト
- AWS/GCP 認証テスト（設定されている場合）

【実行条件】
- .envファイルに認証情報が設定されていること
- 対象のクラウドサービスにアクセス可能なこと

================================================================================
"""

import pytest
import os
import sys

# パス設定
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
_src_path = os.path.join(_project_root, "src")

if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

# 環境変数を読み込み
from dotenv import load_dotenv
_env_path = os.path.join(_project_root, ".env")
if os.path.exists(_env_path):
    load_dotenv(_env_path)


# =============================================================================
# Azure Foundry テスト
# =============================================================================

class TestAzureIntegration:
    """Azure AI Foundry LLMの結合テスト"""

    @pytest.fixture
    def check_azure_config(self):
        """Azure AI Foundry設定確認"""
        provider = os.getenv("LLM_PROVIDER")
        endpoint = os.getenv("AZURE_ENDPOINT") or os.getenv("AZURE_FOUNDRY_ENDPOINT")
        api_key = os.getenv("AZURE_API_KEY") or os.getenv("AZURE_FOUNDRY_API_KEY")
        model = os.getenv("AZURE_MODEL") or os.getenv("AZURE_FOUNDRY_MODEL")

        if provider not in ("AZURE", "AZURE_FOUNDRY"):
            pytest.skip("LLM_PROVIDER is not AZURE")
        if not endpoint or not api_key or not model:
            pytest.skip("Azure configuration is incomplete")

        return {"endpoint": endpoint, "model": model}

    @pytest.mark.integration
    @pytest.mark.azure
    def test_azure_foundry_config_status(self, check_azure_config):
        """Azure Foundry設定状態確認"""
        from infrastructure.llm_factory import LLMFactory, LLMProvider

        status = LLMFactory.get_config_status()

        assert status["provider"] == "AZURE"
        assert status["configured"] is True
        print(f"\n✓ Azure AI Foundry設定確認: model={check_azure_config['model']}")

    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.llm
    def test_azure_foundry_create_model(self, check_azure_config):
        """Azure Foundryモデル作成テスト"""
        from infrastructure.llm_factory import LLMFactory

        try:
            model = LLMFactory.create_chat_model()
            assert model is not None
            print(f"\n✓ Azure Foundryモデル作成成功")
        except Exception as e:
            pytest.fail(f"モデル作成失敗: {e}")

    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.llm
    def test_azure_foundry_simple_inference(self, check_azure_config):
        """Azure Foundry簡単な推論テスト"""
        from infrastructure.llm_factory import LLMFactory

        try:
            model = LLMFactory.create_chat_model()

            # 簡単なプロンプトでテスト
            response = model.invoke("Say 'Hello' in one word.")

            assert response is not None
            assert hasattr(response, 'content')
            print(f"\n✓ Azure Foundry推論成功: {response.content[:50]}...")

        except Exception as e:
            pytest.fail(f"推論失敗: {e}")


# =============================================================================
# Azure Storage テスト
# =============================================================================

class TestAzureStorageIntegration:
    """Azure Storageの結合テスト"""

    @pytest.fixture
    def check_azure_storage_config(self):
        """Azure Storage設定確認"""
        connection_string = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
        storage_provider = os.getenv("JOB_STORAGE_PROVIDER")

        if storage_provider != "AZURE":
            pytest.skip("JOB_STORAGE_PROVIDER is not AZURE")
        if not connection_string:
            pytest.skip("Azure Storage connection string not configured")

        return True

    @pytest.mark.integration
    @pytest.mark.azure
    def test_azure_table_storage_connection(self, check_azure_storage_config):
        """Azure Table Storage接続テスト"""
        try:
            from infrastructure.job_storage import get_job_storage

            storage = get_job_storage()
            assert storage is not None
            print(f"\n✓ Azure Table Storage接続成功")

        except ImportError as e:
            pytest.skip(f"azure-data-tables未インストール: {e}")
        except Exception as e:
            pytest.fail(f"接続失敗: {e}")

    @pytest.mark.integration
    @pytest.mark.azure
    def test_azure_storage_job_operations(self, check_azure_storage_config):
        """Azure Storageジョブ操作テスト"""
        import asyncio

        async def run_test():
            from infrastructure.job_storage import get_job_storage

            storage = get_job_storage()

            # テスト用ジョブを作成（APIに合わせた引数）
            test_items = [{"id": "TEST-001", "controlDescription": "テスト"}]

            job = await storage.create_job(
                tenant_id="test-tenant",
                items=test_items
            )

            assert job is not None
            assert job.job_id is not None

            # ジョブを取得
            retrieved = await storage.get_job(job.job_id)
            assert retrieved is not None
            assert retrieved.job_id == job.job_id

            print(f"\n✓ Azure Storageジョブ操作成功: {job.job_id}")
            return job.job_id

        try:
            asyncio.run(run_test())

        except ImportError as e:
            pytest.skip(f"azure-data-tables未インストール: {e}")
        except Exception as e:
            pytest.fail(f"ジョブ操作失敗: {e}")


# =============================================================================
# AWS テスト
# =============================================================================

class TestAWSIntegration:
    """AWS Bedrockの結合テスト"""

    @pytest.fixture
    def check_aws_config(self):
        """AWS設定確認"""
        provider = os.getenv("LLM_PROVIDER")
        region = os.getenv("AWS_REGION")

        if provider != "AWS":
            pytest.skip("LLM_PROVIDER is not AWS")
        if not region:
            pytest.skip("AWS configuration is incomplete")

        return {"region": region}

    @pytest.mark.integration
    @pytest.mark.aws
    def test_aws_config_status(self, check_aws_config):
        """AWS設定状態確認"""
        from infrastructure.llm_factory import LLMFactory, LLMProvider

        status = LLMFactory.get_config_status()

        assert status["provider"] == "AWS"
        print(f"\n✓ AWS設定確認: region={check_aws_config['region']}")


# =============================================================================
# GCP テスト
# =============================================================================

class TestGCPIntegration:
    """GCP Vertex AIの結合テスト"""

    @pytest.fixture
    def check_gcp_config(self):
        """GCP設定確認"""
        provider = os.getenv("LLM_PROVIDER")
        project_id = os.getenv("GCP_PROJECT_ID")

        if provider != "GCP":
            pytest.skip("LLM_PROVIDER is not GCP")
        if not project_id:
            pytest.skip("GCP configuration is incomplete")

        return {"project_id": project_id}

    @pytest.mark.integration
    @pytest.mark.gcp
    def test_gcp_config_status(self, check_gcp_config):
        """GCP設定状態確認"""
        from infrastructure.llm_factory import LLMFactory, LLMProvider

        status = LLMFactory.get_config_status()

        assert status["provider"] == "GCP"
        print(f"\n✓ GCP設定確認: project={check_gcp_config['project_id']}")


# =============================================================================
# ハンドラー結合テスト
# =============================================================================

class TestHandlersIntegration:
    """共通ハンドラーの結合テスト"""

    @pytest.mark.integration
    def test_health_handler(self):
        """ヘルスハンドラーテスト"""
        from core.handlers import handle_health

        result = handle_health()

        assert result is not None
        assert "status" in result
        print(f"\n✓ ヘルスハンドラー: status={result['status']}")

    @pytest.mark.integration
    def test_config_handler(self):
        """設定ハンドラーテスト"""
        from core.handlers import handle_config

        result = handle_config()

        assert result is not None
        assert "llm" in result
        print(f"\n✓ 設定ハンドラー: provider={result['llm'].get('provider', 'N/A')}")

    @pytest.mark.integration
    @pytest.mark.llm
    def test_evaluate_handler_minimal(self):
        """評価ハンドラー最小テスト"""
        import asyncio
        from core.handlers import handle_evaluate

        # 最小限のテスト項目
        test_items = [{
            "id": "TEST-001",
            "controlDescription": "テスト統制",
            "testProcedure": "テスト手順",
            "evidenceText": "テスト証跡"
        }]

        try:
            result = asyncio.run(handle_evaluate(test_items))
            assert result is not None
            assert len(result) == 1
            print(f"\n✓ 評価ハンドラー: {len(result)}件処理完了")
        except Exception as e:
            # LLM未設定の場合はスキップ
            if "not configured" in str(e).lower() or "API" in str(e):
                pytest.skip(f"LLM未設定: {e}")
            raise
