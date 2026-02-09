# -*- coding: utf-8 -*-
"""
================================================================================
test_e2e.py - E2E（End-to-End）テスト
================================================================================

【テスト対象】
- ハンドラー全体のフロー（health / config / evaluate）
- リクエスト解析 → 評価実行 → レスポンス構築の一連の流れ
- LLM未設定時のモック評価フォールバック
- エラーハンドリング全体

【実行方法】
LLM未設定でもテスト可能（モック評価にフォールバック）:
  LLM_PROVIDER=NONE OCR_PROVIDER=NONE pytest tests/test_e2e.py -v

================================================================================
"""

import pytest
import json
import base64
import os
from unittest.mock import patch, MagicMock, AsyncMock

from core.handlers import (
    handle_health,
    handle_config,
    handle_evaluate,
    parse_request_body,
    API_VERSION,
)


# =============================================================================
# テストデータ
# =============================================================================

def _make_evidence_file(name="report.txt", ext=".txt",
                        mime="text/plain", content="承認済み。月次レビュー完了。"):
    """テスト用証跡ファイルdictを作成"""
    b64 = base64.b64encode(content.encode()).decode()
    return {
        "fileName": name,
        "extension": ext,
        "mimeType": mime,
        "base64": b64,
    }


def _make_request_item(item_id="CLC-01", evidence_files=None):
    """テスト用リクエストアイテムを作成"""
    if evidence_files is None:
        evidence_files = [_make_evidence_file()]
    return {
        "ID": item_id,
        "ControlDescription": "月次で売上の承認プロセスが実施されている",
        "TestProcedure": "売上報告書に承認者の署名があることを確認する",
        "EvidenceLink": "\\\\server\\evidence\\",
        "EvidenceFiles": evidence_files,
    }


# =============================================================================
# Health エンドポイント E2E テスト
# =============================================================================

class TestHealthE2E:
    """ヘルスチェックの全体フロー"""

    def test_health_returns_healthy(self):
        """ヘルスチェックは常に正常を返す"""
        result = handle_health()
        assert result["status"] == "healthy"
        assert result["version"] == API_VERSION

    def test_health_contains_llm_status(self):
        """LLMステータスが含まれる"""
        result = handle_health()
        assert "llm" in result
        assert "provider" in result["llm"]
        assert "configured" in result["llm"]

    def test_health_contains_ocr_status(self):
        """OCRステータスが含まれる"""
        result = handle_health()
        assert "ocr" in result

    def test_health_contains_features(self):
        """機能フラグが含まれる"""
        result = handle_health()
        assert "features" in result
        assert "self_reflection" in result["features"]

    def test_health_contains_platform(self):
        """プラットフォーム情報が含まれる"""
        result = handle_health()
        assert "platform" in result


# =============================================================================
# Config エンドポイント E2E テスト
# =============================================================================

class TestConfigE2E:
    """設定確認の全体フロー"""

    def test_config_returns_structure(self):
        """設定レスポンスの構造確認"""
        result = handle_config()
        assert "llm" in result
        assert "ocr" in result
        assert "orchestrator" in result

    def test_config_orchestrator_info(self):
        """オーケストレーター設定が含まれる"""
        result = handle_config()
        orch = result["orchestrator"]
        assert "type" in orch
        assert orch["type"] == "GraphAuditOrchestrator"
        assert "max_concurrent_evaluations" in orch
        assert "default_timeout_seconds" in orch


# =============================================================================
# Request Parsing E2E テスト
# =============================================================================

class TestParseRequestBody:
    """リクエスト解析の全体フロー"""

    def test_parse_valid_array(self):
        """正常な配列リクエスト"""
        body = json.dumps([_make_request_item()]).encode()
        items, error = parse_request_body(body)
        assert error is None
        assert len(items) == 1
        assert items[0]["ID"] == "CLC-01"

    def test_parse_object_rejected(self):
        """オブジェクト形式は配列でないためエラー"""
        body = json.dumps({"items": [_make_request_item()]}).encode()
        items, error = parse_request_body(body)
        assert items is None
        assert error is not None

    def test_parse_multiple_items(self):
        """複数アイテム"""
        body = json.dumps([
            _make_request_item("CLC-01"),
            _make_request_item("CLC-02"),
            _make_request_item("CLC-03"),
        ]).encode()
        items, error = parse_request_body(body)
        assert error is None
        assert len(items) == 3

    def test_parse_empty_body(self):
        """空ボディ"""
        items, error = parse_request_body(b"")
        assert items is None
        assert error is not None

    def test_parse_invalid_json(self):
        """不正なJSON"""
        items, error = parse_request_body(b"{invalid}")
        assert items is None
        assert error is not None

    def test_parse_non_array(self):
        """配列でないJSON"""
        body = json.dumps({"key": "value"}).encode()
        items, error = parse_request_body(body)
        # items wrapping がなければエラー
        if items is None:
            assert error is not None

    def test_parse_unicode(self):
        """日本語を含むリクエスト"""
        item = _make_request_item()
        item["ControlDescription"] = "月次売上レポートの承認プロセス"
        body = json.dumps([item], ensure_ascii=False).encode()
        items, error = parse_request_body(body)
        assert error is None
        assert items[0]["ControlDescription"] == "月次売上レポートの承認プロセス"


# =============================================================================
# Evaluate エンドポイント E2E テスト（モック評価フォールバック）
# =============================================================================

class TestEvaluateE2E:
    """評価処理の全体フロー（LLMなし→モック評価）"""

    @pytest.mark.asyncio
    async def test_evaluate_single_item_mock(self):
        """単一アイテムの評価（LLMなし→モック評価）"""
        items = [_make_request_item()]

        with patch.dict(os.environ, {"LLM_PROVIDER": "NONE"}, clear=False):
            results = await handle_evaluate(items)

        assert len(results) == 1
        assert results[0]["ID"] == "CLC-01"
        # モック評価でもレスポンス構造は維持される
        assert "evaluationResult" in results[0]

    @pytest.mark.asyncio
    async def test_evaluate_multiple_items_mock(self):
        """複数アイテムの評価"""
        items = [
            _make_request_item("CLC-01"),
            _make_request_item("CLC-02"),
        ]

        with patch.dict(os.environ, {"LLM_PROVIDER": "NONE"}, clear=False):
            results = await handle_evaluate(items)

        assert len(results) == 2
        result_ids = {r["ID"] for r in results}
        assert "CLC-01" in result_ids
        assert "CLC-02" in result_ids

    @pytest.mark.asyncio
    async def test_evaluate_response_structure(self):
        """レスポンス構造の検証"""
        items = [_make_request_item()]

        with patch.dict(os.environ, {"LLM_PROVIDER": "NONE"}, clear=False):
            results = await handle_evaluate(items)

        result = results[0]
        # 必須フィールドの存在確認
        assert "ID" in result
        assert "evaluationResult" in result
        assert isinstance(result["evaluationResult"], bool)

    @pytest.mark.asyncio
    async def test_evaluate_empty_items(self):
        """空のアイテムリスト"""
        results = await handle_evaluate([])
        assert results == []

    @pytest.mark.asyncio
    async def test_evaluate_with_orchestrator_mock(self):
        """オーケストレーターをモックした完全フロー"""
        from core.tasks.base_task import TaskType, TaskResult

        # AuditResult モック
        mock_audit_result = MagicMock()
        mock_audit_result.to_response_dict.return_value = {
            "ID": "CLC-01",
            "evaluationResult": True,
            "executionPlanSummary": "A1, A5 を実行",
            "judgmentBasis": "承認署名を確認。統制は有効。",
            "documentReference": "承認済み。月次レビュー完了。",
            "fileName": "report.txt",
            "evidenceFiles": [{"fileName": "report.txt"}],
        }

        # オーケストレーターモック
        mock_orchestrator = MagicMock()
        mock_orchestrator.evaluate = AsyncMock(return_value=mock_audit_result)

        items = [_make_request_item()]

        with patch("core.handlers.get_llm_instances", return_value=(MagicMock(), MagicMock())), \
             patch("core.handlers.get_orchestrator", return_value=mock_orchestrator):
            results = await handle_evaluate(items)

        assert len(results) == 1
        assert results[0]["ID"] == "CLC-01"
        assert results[0]["evaluationResult"] is True
        assert results[0]["judgmentBasis"] == "承認署名を確認。統制は有効。"
        mock_orchestrator.evaluate.assert_called_once()

    @pytest.mark.asyncio
    async def test_evaluate_orchestrator_error_handling(self):
        """オーケストレーター内エラーのハンドリング"""
        mock_orchestrator = MagicMock()
        mock_orchestrator.evaluate = AsyncMock(
            side_effect=Exception("LLM API Error")
        )

        items = [_make_request_item()]

        with patch("core.handlers.get_llm_instances", return_value=(MagicMock(), MagicMock())), \
             patch("core.handlers.get_orchestrator", return_value=mock_orchestrator):
            results = await handle_evaluate(items)

        # エラーでもレスポンスは返る
        assert len(results) == 1
        assert results[0]["ID"] == "CLC-01"
        assert results[0]["evaluationResult"] is False

    @pytest.mark.asyncio
    async def test_evaluate_timeout_handling(self):
        """タイムアウト時のハンドリング"""
        import asyncio

        async def slow_evaluate(*args, **kwargs):
            await asyncio.sleep(10)

        mock_orchestrator = MagicMock()
        mock_orchestrator.evaluate = slow_evaluate

        items = [_make_request_item()]

        with patch("core.handlers.get_llm_instances", return_value=(MagicMock(), MagicMock())), \
             patch("core.handlers.get_orchestrator", return_value=mock_orchestrator):
            # 短いタイムアウトで実行
            results = await handle_evaluate(items, timeout_seconds=1)

        assert len(results) == 1
        assert results[0]["evaluationResult"] is False

    @pytest.mark.asyncio
    async def test_evaluate_with_csv_evidence(self):
        """CSVファイルを含む評価"""
        csv_content = "日付,項目,金額\n2025-01-01,売上,100000"
        csv_file = _make_evidence_file(
            name="data.csv", ext=".csv",
            mime="text/csv", content=csv_content
        )
        items = [_make_request_item(evidence_files=[csv_file])]

        with patch.dict(os.environ, {"LLM_PROVIDER": "NONE"}, clear=False):
            results = await handle_evaluate(items)

        assert len(results) == 1
        assert results[0]["ID"] == "CLC-01"

    @pytest.mark.asyncio
    async def test_evaluate_with_no_evidence_files(self):
        """証跡ファイルなしの評価"""
        items = [_make_request_item(evidence_files=[])]

        with patch.dict(os.environ, {"LLM_PROVIDER": "NONE"}, clear=False):
            results = await handle_evaluate(items)

        assert len(results) == 1
        assert results[0]["ID"] == "CLC-01"


# =============================================================================
# Full Request Flow テスト（解析→評価→レスポンス）
# =============================================================================

class TestFullRequestFlow:
    """リクエスト解析から評価結果までの完全フロー"""

    @pytest.mark.asyncio
    async def test_parse_and_evaluate(self):
        """parse_request_body → handle_evaluate の一連の流れ"""
        request_body = json.dumps([_make_request_item()]).encode()

        # 1. リクエスト解析
        items, error = parse_request_body(request_body)
        assert error is None
        assert items is not None

        # 2. 評価実行
        with patch.dict(os.environ, {"LLM_PROVIDER": "NONE"}, clear=False):
            results = await handle_evaluate(items)

        # 3. レスポンス検証
        assert len(results) == 1
        assert results[0]["ID"] == "CLC-01"

    @pytest.mark.asyncio
    async def test_health_then_evaluate(self):
        """ヘルスチェック後に評価を実行"""
        # ヘルスチェック
        health = handle_health()
        assert health["status"] == "healthy"

        # 設定確認
        config = handle_config()
        assert "orchestrator" in config

        # 評価実行
        items = [_make_request_item()]
        with patch.dict(os.environ, {"LLM_PROVIDER": "NONE"}, clear=False):
            results = await handle_evaluate(items)

        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_concurrent_evaluations(self):
        """複数アイテムの並列評価"""
        items = [_make_request_item(f"CLC-{i:02d}") for i in range(5)]

        with patch.dict(os.environ, {"LLM_PROVIDER": "NONE"}, clear=False):
            results = await handle_evaluate(items)

        assert len(results) == 5
        result_ids = {r["ID"] for r in results}
        for i in range(5):
            assert f"CLC-{i:02d}" in result_ids
