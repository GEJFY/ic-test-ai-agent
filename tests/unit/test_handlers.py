# -*- coding: utf-8 -*-
"""
================================================================================
test_handlers.py - handlers.pyのユニットテスト
================================================================================

【テスト対象】
- EvaluationError: 評価エラークラス
- LLMConfigurationError: LLM設定エラークラス
- get_llm_instances(): LLMインスタンス取得
- get_orchestrator(): オーケストレーター取得
- evaluate_single_item(): 単一項目評価
- mock_evaluate(): モック評価
- handle_evaluate(): 評価ハンドラー
- handle_health(): ヘルスチェック
- handle_config(): 設定確認

================================================================================
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime

from core.handlers import (
    EvaluationError,
    LLMConfigurationError,
    get_llm_instances,
    get_orchestrator,
    evaluate_single_item,
    mock_evaluate,
    _create_error_result,
    DEFAULT_TIMEOUT_SECONDS,
    MAX_CONCURRENT_EVALUATIONS,
    API_VERSION
)


# =============================================================================
# EvaluationError テスト
# =============================================================================

class TestEvaluationError:
    """EvaluationErrorクラスのテスト"""

    def test_create_evaluation_error(self):
        """基本的なエラー作成"""
        error = EvaluationError(
            message="テストエラー",
            item_id="CLC-01"
        )
        assert error.message == "テストエラー"
        assert error.item_id == "CLC-01"
        assert error.original_error is None

    def test_evaluation_error_with_original(self):
        """元のエラー付きで作成"""
        original = ValueError("元のエラー")
        error = EvaluationError(
            message="ラップしたエラー",
            item_id="CLC-02",
            original_error=original
        )
        assert error.original_error == original

    def test_evaluation_error_str(self):
        """文字列表現"""
        error = EvaluationError("テスト", "CLC-03")
        assert str(error) == "[CLC-03] テスト"

    def test_evaluation_error_default_item_id(self):
        """デフォルトのitem_id"""
        error = EvaluationError("エラー")
        assert error.item_id == "unknown"


# =============================================================================
# LLMConfigurationError テスト
# =============================================================================

class TestLLMConfigurationError:
    """LLMConfigurationErrorクラスのテスト"""

    def test_create_llm_config_error(self):
        """LLM設定エラー作成"""
        error = LLMConfigurationError("LLM未設定")
        assert str(error) == "LLM未設定"


# =============================================================================
# 定数テスト
# =============================================================================

class TestConstants:
    """定数のテスト"""

    def test_default_timeout(self):
        """デフォルトタイムアウト値"""
        assert DEFAULT_TIMEOUT_SECONDS == 300

    def test_max_concurrent(self):
        """最大同時実行数"""
        assert MAX_CONCURRENT_EVALUATIONS == 10

    def test_api_version(self):
        """APIバージョン形式"""
        assert API_VERSION is not None
        assert "." in API_VERSION


# =============================================================================
# get_llm_instances テスト
# =============================================================================

class TestGetLLMInstances:
    """get_llm_instances()のテスト"""

    @patch('infrastructure.llm_factory.LLMFactory')
    def test_llm_configured(self, mock_factory):
        """LLM設定済みの場合"""
        mock_factory.get_config_status.return_value = {
            "configured": True,
            "provider": "AZURE_FOUNDRY",
            "model": "gpt-4o-mini"
        }
        mock_factory.create_chat_model.return_value = Mock()
        mock_factory.create_vision_model.return_value = Mock()

        # 実際の環境変数に依存するため、結果は環境による
        llm, vision_llm = get_llm_instances()
        # LLMが返されるか、Noneが返される（環境依存）

    def test_llm_not_configured_without_env(self):
        """LLM未設定の場合（環境変数なし）"""
        with patch.dict('os.environ', {}, clear=True):
            # 環境変数がない場合は (None, None) を返す
            llm, vision_llm = get_llm_instances()
            assert llm is None
            assert vision_llm is None

    def test_llm_returns_tuple(self):
        """get_llm_instancesがタプルを返す"""
        result = get_llm_instances()
        assert isinstance(result, tuple)
        assert len(result) == 2


# =============================================================================
# get_orchestrator テスト
# =============================================================================

class TestGetOrchestrator:
    """get_orchestrator()のテスト"""

    @patch('core.graph_orchestrator.GraphAuditOrchestrator')
    def test_get_orchestrator_success(self, mock_orchestrator_class):
        """オーケストレーター取得成功"""
        mock_llm = Mock()
        mock_vision_llm = Mock()
        mock_orchestrator = Mock()
        mock_orchestrator_class.return_value = mock_orchestrator

        result = get_orchestrator(mock_llm, mock_vision_llm)

        # GraphAuditOrchestratorのインスタンスが返される
        assert result is not None

    def test_get_orchestrator_returns_orchestrator(self):
        """get_orchestratorがオーケストレーターを返す"""
        from core.graph_orchestrator import GraphAuditOrchestrator

        result = get_orchestrator(None, None)

        assert isinstance(result, GraphAuditOrchestrator)


# =============================================================================
# evaluate_single_item テスト
# =============================================================================

class TestEvaluateSingleItem:
    """evaluate_single_item()のテスト"""

    @pytest.fixture
    def mock_orchestrator(self):
        """オーケストレーターモック"""
        mock = Mock()
        mock_result = Mock()
        mock_result.evaluation_result = True
        mock_result.to_response_dict.return_value = {
            "ID": "CLC-01",
            "evaluationResult": True,
            "judgmentBasis": "統制は有効です",
            "documentReference": "承認書.pdf p.1",
            "fileName": "承認書.pdf",
            "evidenceFiles": ["承認書.pdf"]
        }
        mock.evaluate = AsyncMock(return_value=mock_result)
        return mock

    @pytest.mark.asyncio
    async def test_evaluate_success(self, mock_orchestrator, sample_request_item):
        """評価成功"""
        result = await evaluate_single_item(
            mock_orchestrator,
            sample_request_item,
            timeout_seconds=60
        )

        assert result["ID"] == "CLC-01"
        assert result["evaluationResult"] is True
        mock_orchestrator.evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_timeout(self, sample_request_item):
        """評価タイムアウト"""
        mock_orchestrator = Mock()

        async def slow_evaluate(context):
            await asyncio.sleep(10)

        mock_orchestrator.evaluate = slow_evaluate

        result = await evaluate_single_item(
            mock_orchestrator,
            sample_request_item,
            timeout_seconds=0.1
        )

        assert result["ID"] == "CLC-01"
        assert result["evaluationResult"] is False
        assert "タイムアウト" in result["judgmentBasis"]

    @pytest.mark.asyncio
    async def test_evaluate_error(self, sample_request_item):
        """評価エラー"""
        mock_orchestrator = Mock()
        mock_orchestrator.evaluate = AsyncMock(
            side_effect=ValueError("テストエラー")
        )

        result = await evaluate_single_item(
            mock_orchestrator,
            sample_request_item,
            timeout_seconds=60
        )

        assert result["ID"] == "CLC-01"
        assert result["evaluationResult"] is False
        assert "エラー" in result["judgmentBasis"]
        assert "_debug" in result


# =============================================================================
# _create_error_result テスト
# =============================================================================

class TestCreateErrorResult:
    """_create_error_result()のテスト"""

    def test_create_basic_error_result(self):
        """基本的なエラー結果"""
        result = _create_error_result(
            item_id="CLC-01",
            error_type="test_error",
            message="テストエラーメッセージ"
        )

        assert result["ID"] == "CLC-01"
        assert result["evaluationResult"] is False
        assert result["judgmentBasis"] == "テストエラーメッセージ"
        assert "_debug" in result
        assert result["_debug"]["error"] == "test_error"

    def test_create_error_result_with_details(self):
        """詳細情報付きエラー結果"""
        result = _create_error_result(
            item_id="CLC-02",
            error_type="timeout",
            message="タイムアウト",
            details={"timeout_seconds": 300, "elapsed": 350.5}
        )

        assert result["_debug"]["timeout_seconds"] == 300
        assert result["_debug"]["elapsed"] == 350.5


# =============================================================================
# mock_evaluate テスト
# =============================================================================

class TestMockEvaluate:
    """mock_evaluate()のテスト"""

    def test_mock_evaluate_single_item(self, sample_request_item):
        """単一項目のモック評価"""
        results = mock_evaluate([sample_request_item])

        assert len(results) == 1
        assert results[0]["ID"] == "CLC-01"
        assert "evaluationResult" in results[0]
        assert "judgmentBasis" in results[0]
        assert "モック" in results[0]["judgmentBasis"]

    def test_mock_evaluate_multiple_items(self, sample_request_item):
        """複数項目のモック評価"""
        items = [
            {**sample_request_item, "ID": "CLC-01"},
            {**sample_request_item, "ID": "CLC-02"},
            {**sample_request_item, "ID": "CLC-03"}
        ]
        results = mock_evaluate(items)

        assert len(results) == 3
        assert results[0]["ID"] == "CLC-01"
        assert results[1]["ID"] == "CLC-02"
        assert results[2]["ID"] == "CLC-03"

    def test_mock_evaluate_empty_list(self):
        """空のリスト"""
        results = mock_evaluate([])
        assert results == []

    def test_mock_evaluate_no_evidence(self):
        """証跡なしの項目"""
        item = {
            "ID": "CLC-99",
            "ControlDescription": "テスト統制",
            "TestProcedure": "テスト手続き",
            "EvidenceFiles": []
        }
        results = mock_evaluate([item])

        assert len(results) == 1
        assert results[0]["ID"] == "CLC-99"


# =============================================================================
# 統合テスト
# =============================================================================

class TestHandlersIntegration:
    """ハンドラーの統合テスト"""

    @pytest.mark.asyncio
    @patch('core.handlers.get_llm_instances')
    @patch('core.handlers.get_orchestrator')
    async def test_full_evaluation_flow(
        self,
        mock_get_orchestrator,
        mock_get_llm,
        sample_request_item
    ):
        """完全な評価フロー"""
        # LLMモック
        mock_llm = Mock()
        mock_vision_llm = Mock()
        mock_get_llm.return_value = (mock_llm, mock_vision_llm)

        # オーケストレーターモック
        mock_orchestrator = Mock()
        mock_result = Mock()
        mock_result.evaluation_result = True
        mock_result.to_response_dict.return_value = {
            "ID": "CLC-01",
            "evaluationResult": True,
            "judgmentBasis": "統制有効",
            "documentReference": "",
            "fileName": "",
            "evidenceFiles": []
        }
        mock_orchestrator.evaluate = AsyncMock(return_value=mock_result)
        mock_get_orchestrator.return_value = mock_orchestrator

        # 評価実行
        result = await evaluate_single_item(
            mock_orchestrator,
            sample_request_item
        )

        assert result["ID"] == "CLC-01"
        assert result["evaluationResult"] is True

    @pytest.mark.asyncio
    async def test_error_recovery(self, sample_request_item):
        """エラーからの回復"""
        mock_orchestrator = Mock()

        # 最初の呼び出しはエラー、2回目は成功
        call_count = 0

        async def conditional_evaluate(context):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ValueError("一時的なエラー")
            mock_result = Mock()
            mock_result.evaluation_result = True
            mock_result.to_response_dict.return_value = {
                "ID": context.item_id,
                "evaluationResult": True,
                "judgmentBasis": "成功",
                "documentReference": "",
                "fileName": "",
                "evidenceFiles": []
            }
            return mock_result

        mock_orchestrator.evaluate = conditional_evaluate

        # 1回目: エラー
        result1 = await evaluate_single_item(
            mock_orchestrator,
            sample_request_item
        )
        assert result1["evaluationResult"] is False

        # 2回目: 成功
        result2 = await evaluate_single_item(
            mock_orchestrator,
            sample_request_item
        )
        assert result2["evaluationResult"] is True
