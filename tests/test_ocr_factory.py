# -*- coding: utf-8 -*-
"""
================================================================================
test_ocr_factory.py - ocr_factory.pyのユニットテスト
================================================================================

【テスト対象】
- OCRProvider: プロバイダー列挙型
- OCRConfigError: 設定エラークラス
- OCRFactory: OCRファクトリークラス
- TesseractOCRClient: ローカルOCRクライアント

================================================================================
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock

from infrastructure.ocr_factory import (
    OCRProvider,
    OCRConfigError,
    OCRFactory,
    OCRResult,
    OCRTextElement,
    OCRTableCell,
    OCRTable,
    BaseOCRClient,
    TesseractOCRClient,
)


# =============================================================================
# OCRProvider テスト
# =============================================================================

class TestOCRProvider:
    """OCRProvider列挙型のテスト"""

    def test_all_providers_exist(self):
        """全プロバイダーが定義されているか"""
        expected_providers = ["AZURE", "AWS", "GCP", "TESSERACT", "NONE"]
        for provider in expected_providers:
            assert hasattr(OCRProvider, provider)

    def test_provider_values(self):
        """プロバイダー値の確認"""
        assert OCRProvider.AZURE.value == "AZURE"
        assert OCRProvider.AWS.value == "AWS"
        assert OCRProvider.GCP.value == "GCP"
        assert OCRProvider.TESSERACT.value == "TESSERACT"
        assert OCRProvider.NONE.value == "NONE"


# =============================================================================
# OCRConfigError テスト
# =============================================================================

class TestOCRConfigError:
    """OCRConfigErrorクラスのテスト"""

    def test_create_basic_error(self):
        """基本的なエラー作成"""
        error = OCRConfigError("設定エラー")
        assert str(error) == "設定エラー"


# =============================================================================
# データクラス テスト
# =============================================================================

class TestOCRDataClasses:
    """OCRデータクラスのテスト"""

    def test_ocr_text_element(self):
        """OCRTextElement作成"""
        element = OCRTextElement(
            text="テスト文字列",
            page_number=1,
            bounding_box=[0, 0, 100, 50],
            confidence=0.95,
            element_type="line"
        )
        assert element.text == "テスト文字列"
        assert element.page_number == 1
        assert element.confidence == 0.95

    def test_ocr_text_element_defaults(self):
        """OCRTextElementデフォルト値"""
        element = OCRTextElement(text="テスト")
        assert element.page_number == 1
        assert element.bounding_box is None
        assert element.confidence == 1.0
        assert element.element_type == "line"

    def test_ocr_table_cell(self):
        """OCRTableCell作成"""
        cell = OCRTableCell(
            row_index=0,
            column_index=0,
            text="セル内容",
            row_span=2,
            column_span=1
        )
        assert cell.text == "セル内容"
        assert cell.row_span == 2

    def test_ocr_table(self):
        """OCRTable作成"""
        cells = [
            OCRTableCell(row_index=0, column_index=0, text="A1"),
            OCRTableCell(row_index=0, column_index=1, text="B1"),
        ]
        table = OCRTable(
            table_id="table_0",
            page_number=1,
            row_count=2,
            column_count=2,
            cells=cells
        )
        assert table.table_id == "table_0"
        assert len(table.cells) == 2

    def test_ocr_result(self):
        """OCRResult作成"""
        result = OCRResult(
            text_content="抽出されたテキスト",
            page_count=3,
            provider="Tesseract OCR"
        )
        assert result.text_content == "抽出されたテキスト"
        assert result.page_count == 3
        assert result.error is None

    def test_ocr_result_with_error(self):
        """OCRResultエラー時"""
        result = OCRResult(
            text_content="",
            error="OCRエラーが発生しました",
            provider="Azure Document Intelligence"
        )
        assert result.error == "OCRエラーが発生しました"
        assert result.text_content == ""


# =============================================================================
# OCRFactory テスト
# =============================================================================

class TestOCRFactory:
    """OCRFactoryクラスのテスト"""

    def test_get_provider_default_none(self):
        """デフォルトはNONE"""
        with patch.dict(os.environ, {}, clear=True):
            provider = OCRFactory.get_provider()
            assert provider == OCRProvider.NONE

    def test_get_provider_azure(self):
        """Azureプロバイダー取得"""
        with patch.dict(os.environ, {"OCR_PROVIDER": "AZURE"}):
            provider = OCRFactory.get_provider()
            assert provider == OCRProvider.AZURE

    def test_get_provider_aws(self):
        """AWSプロバイダー取得"""
        with patch.dict(os.environ, {"OCR_PROVIDER": "AWS"}):
            provider = OCRFactory.get_provider()
            assert provider == OCRProvider.AWS

    def test_get_provider_gcp(self):
        """GCPプロバイダー取得"""
        with patch.dict(os.environ, {"OCR_PROVIDER": "GCP"}):
            provider = OCRFactory.get_provider()
            assert provider == OCRProvider.GCP

    def test_get_provider_tesseract(self):
        """TESSERACTプロバイダー取得"""
        with patch.dict(os.environ, {"OCR_PROVIDER": "TESSERACT"}):
            provider = OCRFactory.get_provider()
            assert provider == OCRProvider.TESSERACT

    def test_get_provider_none(self):
        """NONEプロバイダー取得"""
        with patch.dict(os.environ, {"OCR_PROVIDER": "NONE"}):
            provider = OCRFactory.get_provider()
            assert provider == OCRProvider.NONE

    def test_get_provider_invalid(self):
        """不正なプロバイダー名はNONEになる"""
        with patch.dict(os.environ, {"OCR_PROVIDER": "INVALID_PROVIDER"}):
            provider = OCRFactory.get_provider()
            assert provider == OCRProvider.NONE

    def test_get_config_status_none(self):
        """NONE設定状態の取得"""
        with patch.dict(os.environ, {"OCR_PROVIDER": "NONE"}, clear=True):
            # キャッシュをクリア
            OCRFactory._client_cache = None
            OCRFactory._cached_provider = None

            status = OCRFactory.get_config_status()
            assert status["provider"] == "NONE"
            assert status["configured"] is True

    def test_get_config_status_azure_missing_vars(self):
        """Azure設定不足の状態"""
        with patch.dict(os.environ, {"OCR_PROVIDER": "AZURE"}, clear=True):
            # キャッシュをクリア
            OCRFactory._client_cache = None
            OCRFactory._cached_provider = None

            status = OCRFactory.get_config_status()
            assert status["provider"] == "AZURE"
            if not status["configured"]:
                assert "AZURE_DI_ENDPOINT" in status.get("missing_vars", [])

    def test_get_ocr_client_none(self):
        """NONE指定時はNoneを返す"""
        with patch.dict(os.environ, {"OCR_PROVIDER": "NONE"}, clear=True):
            OCRFactory._client_cache = None
            OCRFactory._cached_provider = None

            client = OCRFactory.get_ocr_client()
            assert client is None

    def test_required_env_vars_azure(self):
        """Azure必須環境変数"""
        required = OCRFactory.REQUIRED_ENV_VARS.get(OCRProvider.AZURE, [])
        assert "AZURE_DI_ENDPOINT" in required
        assert "AZURE_DI_KEY" in required

    def test_required_env_vars_tesseract(self):
        """Tesseractは必須環境変数なし"""
        required = OCRFactory.REQUIRED_ENV_VARS.get(OCRProvider.TESSERACT, [])
        assert len(required) == 0

    def test_get_provider_info(self):
        """プロバイダー情報取得"""
        info = OCRFactory.get_provider_info()

        assert "AZURE" in info
        assert "AWS" in info
        assert "GCP" in info
        assert "TESSERACT" in info
        assert "NONE" in info

        assert info["TESSERACT"]["name"] == "Tesseract OCR"
        assert "TESSERACT_CMD" in info["TESSERACT"]["optional_env_vars"]


# =============================================================================
# TesseractOCRClient テスト
# =============================================================================

class TestTesseractOCRClient:
    """TesseractOCRClientのテスト"""

    def test_provider_name(self):
        """プロバイダー名"""
        client = TesseractOCRClient()
        assert client.provider_name == "Tesseract OCR"

    def test_default_language(self):
        """デフォルト言語設定"""
        with patch.dict(os.environ, {}, clear=True):
            client = TesseractOCRClient()
            assert client.lang == "jpn+eng"

    def test_custom_language(self):
        """カスタム言語設定"""
        with patch.dict(os.environ, {"TESSERACT_LANG": "eng"}):
            client = TesseractOCRClient()
            assert client.lang == "eng"

    def test_custom_cmd_path(self):
        """カスタムコマンドパス"""
        with patch.dict(os.environ, {"TESSERACT_CMD": "/custom/path/tesseract"}):
            client = TesseractOCRClient()
            assert client.tesseract_cmd == "/custom/path/tesseract"

    def test_extract_text_not_configured(self):
        """未設定時のエラー処理"""
        client = TesseractOCRClient()
        client._configured = False

        result = client.extract_text(b"dummy data")
        assert result.error == "Tesseract OCR がインストールされていません"
        assert result.text_content == ""

    @pytest.mark.integration
    def test_is_configured_check(self):
        """設定確認（Tesseractがインストールされている場合のみパス）"""
        client = TesseractOCRClient()
        # is_configured()を呼び出してエラーにならないことを確認
        result = client.is_configured()
        # 結果はTesseractのインストール状態による
        assert isinstance(result, bool)


# =============================================================================
# 統合テスト
# =============================================================================

class TestOCRFactoryIntegration:
    """OCRFactoryの統合テスト"""

    @pytest.mark.integration
    def test_config_status_format(self):
        """設定状態の形式確認"""
        status = OCRFactory.get_config_status()

        # 必須フィールドの確認
        assert "provider" in status
        assert "configured" in status
        assert isinstance(status["configured"], bool)

    @pytest.mark.integration
    def test_multiple_provider_detection(self):
        """複数プロバイダーの検出"""
        providers_to_test = [
            ("AZURE", OCRProvider.AZURE),
            ("AWS", OCRProvider.AWS),
            ("GCP", OCRProvider.GCP),
            ("TESSERACT", OCRProvider.TESSERACT),
            ("NONE", OCRProvider.NONE),
        ]

        for env_value, expected_provider in providers_to_test:
            with patch.dict(os.environ, {"OCR_PROVIDER": env_value}):
                provider = OCRFactory.get_provider()
                assert provider == expected_provider, f"Failed for {env_value}"

    @pytest.mark.integration
    def test_tesseract_config_status(self):
        """Tesseract設定状態の取得"""
        env_vars = {
            "OCR_PROVIDER": "TESSERACT",
            "TESSERACT_LANG": "jpn+eng"
        }
        with patch.dict(os.environ, env_vars):
            OCRFactory._client_cache = None
            OCRFactory._cached_provider = None

            status = OCRFactory.get_config_status()
            assert status["provider"] == "TESSERACT"
            # Tesseractは必須環境変数がないのでmissing_varsは空
            assert len(status.get("missing_vars", [])) == 0


# =============================================================================
# ローカル/オンプレミス環境テスト
# =============================================================================

class TestLocalOCREnvironment:
    """ローカル/オンプレミス環境でのOCRテスト"""

    def test_tesseract_no_required_vars(self):
        """Tesseractは必須環境変数がない"""
        required_vars = OCRFactory.REQUIRED_ENV_VARS.get(OCRProvider.TESSERACT, [])
        assert len(required_vars) == 0

    def test_tesseract_optional_vars(self):
        """Tesseractの任意環境変数"""
        info = OCRFactory.get_provider_info()
        tesseract_info = info["TESSERACT"]

        assert "TESSERACT_CMD" in tesseract_info["optional_env_vars"]
        assert "TESSERACT_LANG" in tesseract_info["optional_env_vars"]

    def test_local_ocr_with_default_settings(self):
        """デフォルト設定でのローカルOCR"""
        env_vars = {"OCR_PROVIDER": "TESSERACT"}
        with patch.dict(os.environ, env_vars, clear=True):
            provider = OCRFactory.get_provider()
            assert provider == OCRProvider.TESSERACT

    def test_local_ocr_custom_language(self):
        """カスタム言語設定でのローカルOCR"""
        env_vars = {
            "OCR_PROVIDER": "TESSERACT",
            "TESSERACT_LANG": "jpn"
        }
        with patch.dict(os.environ, env_vars):
            client = TesseractOCRClient()
            assert client.lang == "jpn"

    @pytest.mark.integration
    def test_tesseract_client_creation(self):
        """TesseractクライアントをOCRFactoryから取得"""
        env_vars = {"OCR_PROVIDER": "TESSERACT"}
        with patch.dict(os.environ, env_vars):
            OCRFactory._client_cache = None
            OCRFactory._cached_provider = None

            client = OCRFactory.get_ocr_client()
            # Tesseractがインストールされていなくてもエラーにならないことを確認
            # クライアントはNone（未インストール）またはTesseractOCRClient（インストール済み）
            if client is not None:
                assert isinstance(client, TesseractOCRClient)
