# -*- coding: utf-8 -*-
"""
================================================================================
test_integration_models.py - 各LLMモデルの結合テスト
================================================================================

【テスト対象】
登録された全LLMモデルの接続・推論テスト

【対応モデル】
- Azure Foundry: GPT-5.2, GPT-5-nano, Claude Opus 4.6
- AWS Bedrock: Claude Opus 4.6, Claude Sonnet 4.5, Claude Haiku 4.5
- GCP Vertex AI: Gemini 3 Pro, Gemini 3 Flash
- Local (Ollama): phi4:3.8b (軽量のみ)

【実行方法】
pytest tests/test_integration_models.py -v -m llm

================================================================================
"""

import pytest
import os
import sys
import time
from datetime import datetime
from typing import Dict, Any, List

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
# テスト結果記録用
# =============================================================================

TEST_RESULTS: List[Dict[str, Any]] = []

def record_test_result(
    provider: str,
    model: str,
    success: bool,
    response_time_ms: float,
    error: str = None
):
    """テスト結果を記録"""
    TEST_RESULTS.append({
        "timestamp": datetime.now().isoformat(),
        "provider": provider,
        "model": model,
        "success": success,
        "response_time_ms": response_time_ms,
        "error": error
    })


def get_test_summary() -> str:
    """テスト結果サマリーを取得"""
    if not TEST_RESULTS:
        return "No tests executed"

    lines = ["# LLM Model Integration Test Results", ""]
    lines.append(f"Executed at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append("")
    lines.append("| Provider | Model | Status | Response Time |")
    lines.append("|----------|-------|--------|---------------|")

    for r in TEST_RESULTS:
        status = "✅ Pass" if r["success"] else f"❌ Fail: {r.get('error', 'Unknown')[:30]}"
        lines.append(f"| {r['provider']} | {r['model']} | {status} | {r['response_time_ms']:.0f}ms |")

    return "\n".join(lines)


# =============================================================================
# Azure Foundry モデルテスト
# =============================================================================

class TestAzureFoundryModels:
    """Azure Foundry全モデルの結合テスト"""

    @pytest.fixture
    def check_azure_foundry_config(self):
        """Azure Foundry設定確認"""
        provider = os.getenv("LLM_PROVIDER")
        endpoint = os.getenv("AZURE_FOUNDRY_ENDPOINT")
        api_key = os.getenv("AZURE_FOUNDRY_API_KEY")

        if provider != "AZURE_FOUNDRY":
            pytest.skip("LLM_PROVIDER is not AZURE_FOUNDRY")
        if not endpoint or not api_key:
            pytest.skip("Azure Foundry configuration is incomplete")

        return True

    def _test_model(self, model_name: str, description: str):
        """モデルテストの共通ロジック"""
        from infrastructure.llm_factory import LLMFactory, LLMConfigError

        start_time = time.time()
        try:
            model = LLMFactory.create_chat_model(model=model_name)
            response = model.invoke("Say 'OK' in one word.")
            elapsed_ms = (time.time() - start_time) * 1000

            assert response is not None
            assert hasattr(response, 'content')

            record_test_result("AZURE_FOUNDRY", model_name, True, elapsed_ms)
            print(f"\n✅ {model_name} ({description}): {elapsed_ms:.0f}ms")
            print(f"   Response: {response.content[:50]}...")
            return True

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            record_test_result("AZURE_FOUNDRY", model_name, False, elapsed_ms, str(e)[:100])
            print(f"\n❌ {model_name} ({description}): {e}")
            return False

    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.llm
    def test_gpt_5_2(self, check_azure_foundry_config):
        """GPT-5.2 フラッグシップモデルテスト"""
        assert self._test_model("gpt-5.2", "フラッグシップ")

    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.llm
    def test_gpt_5_nano(self, check_azure_foundry_config):
        """GPT-5 Nano 高速モデルテスト"""
        assert self._test_model("gpt-5-nano", "高速・低コスト")

    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.llm
    def test_gpt_5(self, check_azure_foundry_config):
        """GPT-5 標準モデルテスト"""
        assert self._test_model("gpt-5", "標準")

    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.llm
    def test_claude_opus_4_6_azure(self, check_azure_foundry_config):
        """Claude Opus 4.6 (Azure Foundry経由) テスト"""
        assert self._test_model("claude-opus-4-6", "Anthropic最高性能")

    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.llm
    def test_claude_sonnet_4_5_azure(self, check_azure_foundry_config):
        """Claude Sonnet 4.5 (Azure Foundry経由) テスト"""
        assert self._test_model("claude-sonnet-4-5", "Anthropicバランス型")

    @pytest.mark.integration
    @pytest.mark.azure
    @pytest.mark.llm
    def test_claude_haiku_4_5_azure(self, check_azure_foundry_config):
        """Claude Haiku 4.5 (Azure Foundry経由) テスト"""
        assert self._test_model("claude-haiku-4-5", "Anthropic高速")


# =============================================================================
# AWS Bedrock モデルテスト
# =============================================================================

class TestAWSBedrockModels:
    """AWS Bedrock全モデルの結合テスト"""

    @pytest.fixture
    def check_aws_config(self):
        """AWS設定確認"""
        provider = os.getenv("LLM_PROVIDER")
        region = os.getenv("AWS_REGION")

        if provider != "AWS":
            pytest.skip("LLM_PROVIDER is not AWS")
        if not region:
            pytest.skip("AWS configuration is incomplete")

        return True

    def _test_model(self, model_id: str, description: str):
        """モデルテストの共通ロジック"""
        from infrastructure.llm_factory import LLMFactory

        start_time = time.time()
        try:
            model = LLMFactory.create_chat_model(model=model_id)
            response = model.invoke("Say 'OK' in one word.")
            elapsed_ms = (time.time() - start_time) * 1000

            assert response is not None
            assert hasattr(response, 'content')

            record_test_result("AWS", model_id, True, elapsed_ms)
            print(f"\n✅ {model_id} ({description}): {elapsed_ms:.0f}ms")
            print(f"   Response: {response.content[:50]}...")
            return True

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            record_test_result("AWS", model_id, False, elapsed_ms, str(e)[:100])
            print(f"\n❌ {model_id} ({description}): {e}")
            return False

    @pytest.mark.integration
    @pytest.mark.aws
    @pytest.mark.llm
    def test_claude_opus_4_6(self, check_aws_config):
        """Claude Opus 4.6 テスト"""
        assert self._test_model(
            "global.anthropic.claude-opus-4-6-v1",
            "最高性能"
        )

    @pytest.mark.integration
    @pytest.mark.aws
    @pytest.mark.llm
    def test_claude_opus_4_5(self, check_aws_config):
        """Claude Opus 4.5 テスト"""
        assert self._test_model(
            "global.anthropic.claude-opus-4-5-v1",
            "高性能"
        )

    @pytest.mark.integration
    @pytest.mark.aws
    @pytest.mark.llm
    def test_claude_sonnet_4_5(self, check_aws_config):
        """Claude Sonnet 4.5 テスト"""
        assert self._test_model(
            "global.anthropic.claude-sonnet-4-5-v1",
            "バランス型"
        )

    @pytest.mark.integration
    @pytest.mark.aws
    @pytest.mark.llm
    def test_claude_haiku_4_5(self, check_aws_config):
        """Claude Haiku 4.5 テスト"""
        assert self._test_model(
            "global.anthropic.claude-haiku-4-5-v1",
            "高速・低コスト"
        )

    @pytest.mark.integration
    @pytest.mark.aws
    @pytest.mark.llm
    def test_claude_opus_4_6_jp(self, check_aws_config):
        """Claude Opus 4.6 (日本リージョン) テスト"""
        assert self._test_model(
            "jp.anthropic.claude-opus-4-6-v1",
            "日本リージョン"
        )


# =============================================================================
# GCP Vertex AI モデルテスト
# =============================================================================

class TestGCPVertexAIModels:
    """GCP Vertex AI全モデルの結合テスト"""

    @pytest.fixture
    def check_gcp_config(self):
        """GCP設定確認"""
        provider = os.getenv("LLM_PROVIDER")
        project_id = os.getenv("GCP_PROJECT_ID")

        if provider != "GCP":
            pytest.skip("LLM_PROVIDER is not GCP")
        if not project_id:
            pytest.skip("GCP configuration is incomplete")

        return True

    def _test_model(self, model_name: str, description: str):
        """モデルテストの共通ロジック"""
        from infrastructure.llm_factory import LLMFactory

        start_time = time.time()
        try:
            model = LLMFactory.create_chat_model(model=model_name)
            response = model.invoke("Say 'OK' in one word.")
            elapsed_ms = (time.time() - start_time) * 1000

            assert response is not None
            assert hasattr(response, 'content')

            record_test_result("GCP", model_name, True, elapsed_ms)
            print(f"\n✅ {model_name} ({description}): {elapsed_ms:.0f}ms")
            print(f"   Response: {response.content[:50]}...")
            return True

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            record_test_result("GCP", model_name, False, elapsed_ms, str(e)[:100])
            print(f"\n❌ {model_name} ({description}): {e}")
            return False

    @pytest.mark.integration
    @pytest.mark.gcp
    @pytest.mark.llm
    def test_gemini_3_pro(self, check_gcp_config):
        """Gemini 3 Pro テスト"""
        assert self._test_model("gemini-3-pro", "高度な推論")

    @pytest.mark.integration
    @pytest.mark.gcp
    @pytest.mark.llm
    def test_gemini_3_flash(self, check_gcp_config):
        """Gemini 3 Flash テスト"""
        assert self._test_model("gemini-3-flash", "コスト効率")


# =============================================================================
# ローカル (Ollama) モデルテスト - 軽量のみ
# =============================================================================

class TestLocalModels:
    """ローカルLLM（Ollama）の結合テスト - 軽量モデルのみ"""

    @pytest.fixture
    def check_local_config(self):
        """Ollama設定確認"""
        provider = os.getenv("LLM_PROVIDER")

        if provider != "LOCAL":
            pytest.skip("LLM_PROVIDER is not LOCAL")

        # Ollamaが動作しているか確認
        import socket
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        host = base_url.replace("http://", "").replace("https://", "").split(":")[0]
        port = int(base_url.split(":")[-1].replace("/", ""))

        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((host, port))
            sock.close()
            if result != 0:
                pytest.skip("Ollama server is not running")
        except Exception:
            pytest.skip("Cannot connect to Ollama server")

        return True

    def _test_model(self, model_name: str, description: str):
        """モデルテストの共通ロジック"""
        from infrastructure.llm_factory import LLMFactory

        start_time = time.time()
        try:
            model = LLMFactory.create_chat_model(model=model_name)
            response = model.invoke("Say 'OK' in one word.")
            elapsed_ms = (time.time() - start_time) * 1000

            assert response is not None
            assert hasattr(response, 'content')

            record_test_result("LOCAL", model_name, True, elapsed_ms)
            print(f"\n✅ {model_name} ({description}): {elapsed_ms:.0f}ms")
            print(f"   Response: {response.content[:50]}...")
            return True

        except Exception as e:
            elapsed_ms = (time.time() - start_time) * 1000
            record_test_result("LOCAL", model_name, False, elapsed_ms, str(e)[:100])
            print(f"\n❌ {model_name} ({description}): {e}")
            return False

    @pytest.mark.integration
    @pytest.mark.local
    @pytest.mark.llm
    def test_phi4_lightweight(self, check_local_config):
        """Phi-4 3.8B 超軽量モデルテスト"""
        assert self._test_model("phi4:3.8b", "超軽量")

    @pytest.mark.integration
    @pytest.mark.local
    @pytest.mark.llm
    def test_mistral_lightweight(self, check_local_config):
        """Mistral 7B 軽量モデルテスト"""
        assert self._test_model("mistral:7b", "軽量高速")


# =============================================================================
# テスト結果出力
# =============================================================================

@pytest.fixture(scope="session", autouse=True)
def print_test_summary(request):
    """テストセッション終了時にサマリーを出力"""
    yield
    if TEST_RESULTS:
        print("\n" + "="*60)
        print(get_test_summary())
        print("="*60)
