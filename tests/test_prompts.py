# -*- coding: utf-8 -*-
"""
================================================================================
test_prompts.py - prompts.py のユニットテスト
================================================================================

【テスト対象】
- PromptManager の各メソッド
- テンプレート変数の展開
- ユーザーフィードバックの挿入

================================================================================
"""

import pytest

from core.prompts import (
    PromptManager,
    PLANNER_PROMPT,
    PLAN_REVIEW_PROMPT,
    JUDGMENT_PROMPT,
    JUDGMENT_REVIEW_PROMPT,
    PLAN_REFINE_PROMPT,
    JUDGMENT_REFINE_PROMPT,
    A1_SEMANTIC_SEARCH_PROMPT,
    A2_IMAGE_RECOGNITION_PROMPT,
    A3_DATA_EXTRACTION_PROMPT,
    A4_STEPWISE_REASONING_PROMPT,
    A5_SEMANTIC_REASONING_PROMPT,
    A6_MULTI_DOCUMENT_PROMPT,
    A7_PATTERN_ANALYSIS_PROMPT,
    A8_SOD_DETECTION_PROMPT,
)


class TestPromptConstants:
    """プロンプト定数の存在・内容テスト"""

    def test_planner_prompt_exists(self):
        assert len(PLANNER_PROMPT) > 100
        assert "{user_feedback_section}" in PLANNER_PROMPT

    def test_plan_review_prompt_exists(self):
        assert len(PLAN_REVIEW_PROMPT) > 100

    def test_judgment_prompt_exists(self):
        assert len(JUDGMENT_PROMPT) > 100

    def test_task_prompts_exist(self):
        """A1-A8 プロンプトが定義されている"""
        prompts = [
            A1_SEMANTIC_SEARCH_PROMPT,
            A2_IMAGE_RECOGNITION_PROMPT,
            A3_DATA_EXTRACTION_PROMPT,
            A4_STEPWISE_REASONING_PROMPT,
            A5_SEMANTIC_REASONING_PROMPT,
            A6_MULTI_DOCUMENT_PROMPT,
            A7_PATTERN_ANALYSIS_PROMPT,
            A8_SOD_DETECTION_PROMPT,
        ]
        for p in prompts:
            assert isinstance(p, str)
            assert len(p) > 50


class TestPromptManager:
    """PromptManager のテスト"""

    def setup_method(self):
        self.pm = PromptManager()

    def test_init(self):
        """初期化"""
        assert self.pm is not None

    # -------------------------------------------------------------------------
    # ユーザーフィードバックセクション
    # -------------------------------------------------------------------------

    def test_format_user_feedback_none(self):
        """None → 空文字列"""
        assert self.pm._format_user_feedback_section(None) == ""

    def test_format_user_feedback_empty(self):
        """空文字列 → 空文字列"""
        assert self.pm._format_user_feedback_section("") == ""
        assert self.pm._format_user_feedback_section("  ") == ""

    def test_format_user_feedback_with_content(self):
        """フィードバックあり"""
        result = self.pm._format_user_feedback_section("リスク評価を重視")
        assert "リスク評価を重視" in result
        assert "ユーザーからの追加指示" in result

    # -------------------------------------------------------------------------
    # get_*_prompt メソッド
    # -------------------------------------------------------------------------

    def test_get_planner_prompt_no_feedback(self):
        """計画プロンプト（フィードバックなし）"""
        result = self.pm.get_planner_prompt()
        assert isinstance(result, str)
        assert "{user_feedback_section}" not in result

    def test_get_planner_prompt_with_feedback(self):
        """計画プロンプト（フィードバックあり）"""
        result = self.pm.get_planner_prompt(user_feedback="詳細に分析")
        assert "詳細に分析" in result

    def test_get_plan_review_prompt(self):
        result = self.pm.get_plan_review_prompt()
        assert isinstance(result, str)

    def test_get_judgment_prompt(self):
        result = self.pm.get_judgment_prompt()
        assert isinstance(result, str)

    def test_get_judgment_review_prompt(self):
        result = self.pm.get_judgment_review_prompt()
        assert isinstance(result, str)

    def test_get_plan_refine_prompt(self):
        result = self.pm.get_plan_refine_prompt()
        assert isinstance(result, str)

    def test_get_judgment_refine_prompt(self):
        result = self.pm.get_judgment_refine_prompt()
        assert isinstance(result, str)

    def test_get_result_aggregation_additional(self):
        result = self.pm.get_result_aggregation_additional()
        assert isinstance(result, str)

    # -------------------------------------------------------------------------
    # get_task_prompt
    # -------------------------------------------------------------------------

    def test_get_task_prompt_all_types(self):
        """A1-A8 全タイプのプロンプト取得"""
        for task_type in ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8"]:
            result = self.pm.get_task_prompt(task_type)
            assert isinstance(result, str)
            assert len(result) > 50

    def test_get_task_prompt_invalid(self):
        """無効なタスクタイプ"""
        with pytest.raises(ValueError, match="無効なタスクタイプ"):
            self.pm.get_task_prompt("A99")

    # -------------------------------------------------------------------------
    # 個別タスクプロンプトメソッド
    # -------------------------------------------------------------------------

    def test_get_a1_prompt(self):
        assert self.pm.get_a1_semantic_search_prompt() == A1_SEMANTIC_SEARCH_PROMPT

    def test_get_a2_prompt(self):
        assert self.pm.get_a2_image_recognition_prompt() == A2_IMAGE_RECOGNITION_PROMPT

    def test_get_a3_prompt(self):
        assert self.pm.get_a3_data_extraction_prompt() == A3_DATA_EXTRACTION_PROMPT

    def test_get_a4_prompt(self):
        assert self.pm.get_a4_stepwise_reasoning_prompt() == A4_STEPWISE_REASONING_PROMPT

    def test_get_a5_prompt(self):
        assert self.pm.get_a5_semantic_reasoning_prompt() == A5_SEMANTIC_REASONING_PROMPT

    def test_get_a6_prompt(self):
        assert self.pm.get_a6_multi_document_prompt() == A6_MULTI_DOCUMENT_PROMPT

    def test_get_a7_prompt(self):
        assert self.pm.get_a7_pattern_analysis_prompt() == A7_PATTERN_ANALYSIS_PROMPT

    def test_get_a8_prompt(self):
        assert self.pm.get_a8_sod_detection_prompt() == A8_SOD_DETECTION_PROMPT


class TestPromptFeedbackIntegration:
    """フィードバックが全プロンプトに正しく挿入されるかテスト"""

    def setup_method(self):
        self.pm = PromptManager()

    def test_all_orchestrator_prompts_accept_feedback(self):
        """オーケストレーター系プロンプトすべてにフィードバック挿入可能"""
        methods = [
            self.pm.get_planner_prompt,
            self.pm.get_plan_review_prompt,
            self.pm.get_judgment_prompt,
            self.pm.get_judgment_review_prompt,
            self.pm.get_plan_refine_prompt,
            self.pm.get_judgment_refine_prompt,
        ]
        feedback = "テスト用フィードバック_XYZ"

        for method in methods:
            result = method(user_feedback=feedback)
            assert "テスト用フィードバック_XYZ" in result, \
                f"{method.__name__} にフィードバックが挿入されていません"
