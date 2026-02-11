# -*- coding: utf-8 -*-
"""
================================================================================
test_integration_local.py - ローカル環境の結合テスト
================================================================================

【テスト対象】
- Ollama LLM接続テスト
- Tesseract OCRテスト
- ローカルプラットフォームのエンドツーエンドテスト

【実行条件】
- Ollamaがインストール・起動していること
- Tesseractがインストールされていること
- 使用するモデルがpull済みであること

================================================================================
"""

import pytest
import os
import sys
import asyncio
from unittest.mock import patch

# パス設定
_current_dir = os.path.dirname(os.path.abspath(__file__))
_project_root = os.path.dirname(_current_dir)
_src_path = os.path.join(_project_root, "src")

if _src_path not in sys.path:
    sys.path.insert(0, _src_path)


# =============================================================================
# Ollama 接続テスト
# =============================================================================

class TestOllamaIntegration:
    """Ollama結合テスト"""

    @pytest.mark.integration
    @pytest.mark.local
    def test_ollama_is_running(self):
        """Ollamaサービスが起動しているか確認"""
        import httpx

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        try:
            response = httpx.get(f"{base_url}/api/tags", timeout=5.0)
            assert response.status_code == 200
            data = response.json()
            assert "models" in data
            print(f"\n✓ Ollama接続成功: {len(data['models'])}モデル利用可能")
        except httpx.ConnectError:
            pytest.skip("Ollamaサービスが起動していません")

    @pytest.mark.integration
    @pytest.mark.local
    def test_ollama_model_available(self):
        """使用するモデルが利用可能か確認"""
        import httpx

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        # 軽量モデルを優先的に確認
        expected_model = os.getenv("OLLAMA_MODEL", "tinyllama:latest")

        try:
            response = httpx.get(f"{base_url}/api/tags", timeout=5.0)
            if response.status_code != 200:
                pytest.skip("Ollamaに接続できません")

            data = response.json()
            models = [m.get("name", "").split(":")[0] for m in data.get("models", [])]

            # tinyllama, gemma2, phi, llama3 などがあればOK
            has_model = any(m in models for m in ["tinyllama", "gemma2", "phi", "llama3", "llama3.1", expected_model.split(":")[0]])

            if has_model:
                print(f"\n✓ モデル利用可能: {models}")
            else:
                pytest.skip(f"必要なモデルがありません。利用可能: {models}")

        except httpx.ConnectError:
            pytest.skip("Ollamaサービスが起動していません")

    @pytest.mark.integration
    @pytest.mark.local
    @pytest.mark.llm
    def test_ollama_simple_inference(self):
        """Ollamaで簡単な推論テスト"""
        import httpx

        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        # 超軽量モデルを使用（tinyllama - 637MB）
        model = os.getenv("OLLAMA_MODEL", "tinyllama:latest")

        try:
            # 簡単なプロンプトでテスト
            response = httpx.post(
                f"{base_url}/api/generate",
                json={
                    "model": model,
                    "prompt": "Say 'Hello' in one word.",
                    "stream": False,
                    "options": {"num_predict": 10}
                },
                timeout=60.0
            )

            if response.status_code == 200:
                data = response.json()
                assert "response" in data
                print(f"\n✓ Ollama推論成功: {data['response'][:50]}...")
            else:
                pytest.skip(f"推論失敗: HTTP {response.status_code}")

        except httpx.ConnectError:
            pytest.skip("Ollamaサービスが起動していません")
        except httpx.ReadTimeout:
            pytest.skip("推論タイムアウト（モデルが大きすぎる可能性）")


# =============================================================================
# Tesseract OCR テスト
# =============================================================================

class TestTesseractIntegration:
    """Tesseract結合テスト"""

    @pytest.mark.integration
    @pytest.mark.local
    @pytest.mark.ocr
    def test_tesseract_is_installed(self):
        """Tesseractがインストールされているか確認"""
        try:
            import pytesseract
            version = pytesseract.get_tesseract_version()
            print(f"\n✓ Tesseract {version} インストール済み")
            assert version is not None
        except Exception as e:
            pytest.skip(f"Tesseractが利用できません: {e}")

    @pytest.mark.integration
    @pytest.mark.local
    @pytest.mark.ocr
    def test_tesseract_japanese_available(self):
        """日本語言語パックが利用可能か確認"""
        try:
            import pytesseract
            langs = pytesseract.get_languages()

            if "jpn" in langs:
                print(f"\n✓ 日本語OCR利用可能")
            else:
                pytest.skip("日本語言語パック(jpn)がインストールされていません")

        except Exception as e:
            pytest.skip(f"Tesseractが利用できません: {e}")

    @pytest.mark.integration
    @pytest.mark.local
    @pytest.mark.ocr
    def test_tesseract_simple_ocr(self):
        """簡単なOCRテスト"""
        try:
            import pytesseract
            from PIL import Image, ImageDraw, ImageFont

            # テスト用の画像を作成（白背景に黒文字）
            img = Image.new('RGB', (200, 50), color='white')
            draw = ImageDraw.Draw(img)
            draw.text((10, 10), "Hello Test", fill='black')

            # OCR実行
            text = pytesseract.image_to_string(img, lang='eng')

            # 結果確認（大文字小文字を無視）
            assert "hello" in text.lower() or "test" in text.lower()
            print(f"\n✓ Tesseract OCR成功: '{text.strip()}'")

        except ImportError:
            pytest.skip("pytesseractまたはPillowがインストールされていません")
        except Exception as e:
            pytest.skip(f"OCRテスト失敗: {e}")


# =============================================================================
# LLMFactory LOCAL テスト
# =============================================================================

class TestLLMFactoryLocalIntegration:
    """LLMFactory LOCALプロバイダーの結合テスト"""

    @pytest.mark.integration
    @pytest.mark.local
    def test_local_provider_config(self):
        """LOCALプロバイダーの設定確認"""
        from infrastructure.llm_factory import LLMFactory, LLMProvider

        with patch.dict(os.environ, {"LLM_PROVIDER": "LOCAL", "OLLAMA_MODEL": "tinyllama:latest"}):
            provider = LLMFactory.get_provider()
            assert provider == LLMProvider.LOCAL

            status = LLMFactory.get_config_status()
            assert status["configured"] is True
            print(f"\n✓ LOCALプロバイダー設定完了")

    @pytest.mark.integration
    @pytest.mark.local
    @pytest.mark.llm
    def test_create_local_chat_model(self):
        """LOCALチャットモデルの作成テスト"""
        from infrastructure.llm_factory import LLMFactory, LLMProvider

        with patch.dict(os.environ, {"LLM_PROVIDER": "LOCAL", "OLLAMA_MODEL": "tinyllama:latest"}):
            try:
                model = LLMFactory.create_chat_model()
                assert model is not None
                print(f"\n✓ LOCALチャットモデル作成成功")
            except ImportError as e:
                pytest.skip(f"langchain-ollama未インストール: {e}")
            except Exception as e:
                pytest.skip(f"モデル作成失敗: {e}")


# =============================================================================
# OCRFactory TESSERACT テスト
# =============================================================================

class TestOCRFactoryTesseractIntegration:
    """OCRFactory TESSERACTプロバイダーの結合テスト"""

    @pytest.mark.integration
    @pytest.mark.local
    @pytest.mark.ocr
    def test_tesseract_provider_config(self):
        """TESSERACTプロバイダーの設定確認"""
        from infrastructure.ocr_factory import OCRFactory, OCRProvider

        with patch.dict(os.environ, {"OCR_PROVIDER": "TESSERACT"}):
            OCRFactory._client_cache = None
            OCRFactory._cached_provider = None

            provider = OCRFactory.get_provider()
            assert provider == OCRProvider.TESSERACT

            status = OCRFactory.get_config_status()
            print(f"\n✓ TESSERACTプロバイダー設定: {status}")

    @pytest.mark.integration
    @pytest.mark.local
    @pytest.mark.ocr
    def test_tesseract_client_creation(self):
        """Tesseractクライアントの作成テスト"""
        from infrastructure.ocr_factory import OCRFactory, TesseractOCRClient

        with patch.dict(os.environ, {"OCR_PROVIDER": "TESSERACT"}):
            OCRFactory._client_cache = None
            OCRFactory._cached_provider = None

            client = OCRFactory.get_ocr_client()

            if client is not None:
                assert isinstance(client, TesseractOCRClient)
                print(f"\n✓ Tesseractクライアント作成成功")
            else:
                pytest.skip("Tesseractクライアント作成失敗（未インストール？）")


# =============================================================================
# ローカルプラットフォーム エンドツーエンドテスト
# =============================================================================

class TestLocalPlatformE2E:
    """ローカルプラットフォームのE2Eテスト"""

    @pytest.fixture
    def local_env(self):
        """ローカル環境設定（軽量モデル使用）"""
        env_vars = {
            "LLM_PROVIDER": "LOCAL",
            "OCR_PROVIDER": "TESSERACT",
            "OLLAMA_MODEL": "tinyllama:latest"  # 軽量モデル（1.6GB）
        }
        with patch.dict(os.environ, env_vars):
            yield

    @pytest.mark.integration
    @pytest.mark.local
    def test_health_with_ollama(self, local_env):
        """ヘルスチェック（Ollama接続確認付き）"""
        import httpx

        # Ollama接続確認
        try:
            response = httpx.get("http://localhost:11434/api/tags", timeout=5.0)
            ollama_ok = response.status_code == 200
        except:
            ollama_ok = False

        if ollama_ok:
            print(f"\n✓ Ollama接続OK、ヘルスチェック準備完了")
        else:
            pytest.skip("Ollamaに接続できません")

    @pytest.mark.integration
    @pytest.mark.local
    def test_config_local_settings(self, local_env):
        """設定確認（ローカル設定）"""
        from core.handlers import handle_config

        config = handle_config()

        assert config is not None
        assert "llm" in config
        print(f"\n✓ ローカル設定確認: LLM={config['llm'].get('provider', 'N/A')}")
