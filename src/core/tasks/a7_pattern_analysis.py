"""
================================================================================
a7_pattern_analysis.py - A7: パターン分析（時系列分析）タスク
================================================================================

【概要】
複数期間のデータから継続性とパターンを分析し、
記録の欠落や異常パターンを検出するタスクです。

【主な機能】
- 継続性要件（月次/四半期/年次）の特定
- 全期間のデータ網羅性チェック
- 記録欠落（ギャップ）の検出
- 異常値・外れ値の識別
- トレンド分析

【典型的なユースケース】
- 月次棚卸の継続実施確認
- 四半期レビューの実施記録確認
- 年度末決算プロセスの一貫性確認
- 定期的なアクセス権限レビューの確認

【使用例】
```python
from core.tasks.a7_pattern_analysis import PatternAnalysisTask
from core.tasks.base_task import AuditContext

# タスクを初期化
task = PatternAnalysisTask(llm=llm)

# 評価を実行
result = await task.execute(context)

# 欠落期間を確認
if result.result:
    gap_detection = result.result["gap_detection"]
    print(f"カバー率: {gap_detection['coverage_rate']:.0%}")
    print(f"欠落期間: {gap_detection['missing_periods']}")
```

【処理フロー】
1. 継続性要件を特定
2. 各期間のデータを分析
3. 欠落期間を検出
4. パターン・トレンドを分析
5. コンプライアンス評価を返却

================================================================================
"""
import logging
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .base_task import BaseAuditTask, TaskType, TaskResult, AuditContext
from ..document_processor import DocumentProcessor

# =============================================================================
# ログ設定
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# プロンプトテンプレート
# =============================================================================

PATTERN_ANALYSIS_PROMPT = """あなたは内部統制監査の専門家です。
複数期間のデータから継続性とパターンを分析し、抜け漏れを検出してください。

【重要な指示】
1. 「四半期ごと」「月次」などの継続性要件を特定
2. 複数期間のデータから実施パターンを分析
3. Q1からQ4、または1月から12月までの記録を網羅的にチェック
4. 特定の期間の記録欠落（抜け漏れ）を検出
5. 異常なパターン（突然の変化、不規則な間隔）を識別

【統制記述】
{control_description}

【テスト手続き】
{test_procedure}

【期間データ】
{period_data}

【出力形式】
以下のJSON形式で回答してください：
{{
    "continuity_requirement": {{
        "frequency": "四半期/月次/年次/週次/随時",
        "expected_periods": ["期待される期間のリスト"],
        "source": "要件の根拠"
    }},
    "period_analysis": [
        {{
            "period": "期間名（Q1/1月/2024年度等）",
            "record_exists": true/false,
            "record_date": "記録日（あれば）",
            "key_metrics": {{"指標名": 値}},
            "anomalies": ["異常事項"]
        }}
    ],
    "gap_detection": {{
        "missing_periods": ["欠落している期間"],
        "coverage_rate": 0.0-1.0,
        "gap_severity": "重大/中程度/軽微/なし"
    }},
    "pattern_analysis": {{
        "trend": "増加/減少/横ばい/不規則",
        "seasonality": "季節性の有無と説明",
        "outliers": [
            {{
                "period": "期間",
                "metric": "指標",
                "value": 値,
                "expected_range": "期待される範囲",
                "deviation": "偏差"
            }}
        ]
    }},
    "compliance_assessment": {{
        "continuity_maintained": true/false,
        "all_periods_documented": true/false,
        "pattern_consistent": true/false,
        "issues": ["発見された問題"]
    }},
    "confidence": 0.0-1.0,
    "reasoning": {{
        "verification_summary": "どの期間のデータを検証し、何が確認できたか",
        "evidence_details": "具体的な記録内容（日付、実施者、内容等を引用）",
        "conclusion": "継続性に関する結論とその根拠"
    }}
}}
"""


# =============================================================================
# メインクラス: PatternAnalysisTask
# =============================================================================

class PatternAnalysisTask(BaseAuditTask):
    """
    A7: パターン分析（時系列分析）タスク

    複数期間のデータから継続性とパターンを分析し、
    記録の欠落や異常パターンを検出するタスクです。

    【主な機能】
    - 継続性要件の特定
    - 期間ごとのデータ分析
    - 記録欠落の検出
    - トレンド・季節性の分析
    - 外れ値の識別

    【処理フロー】
    1. 統制から継続性要件を特定
    2. 証跡から期間データを抽出
    3. 各期間の記録有無を確認
    4. 欠落・異常を検出
    5. コンプライアンス評価を返却

    Attributes:
        prompt: パターン分析用のプロンプトテンプレート
        parser: JSON出力パーサー

    使用例:
        ```python
        task = PatternAnalysisTask(llm=llm)
        result = await task.execute(context)
        ```
    """

    # タスク識別情報
    task_type = TaskType.A7_PATTERN_ANALYSIS
    task_name = "パターン分析（時系列分析）"
    description = "複数期間のデータから継続性を確認し、記録欠落や異常パターンを検出"

    def __init__(self, llm=None):
        """
        タスクを初期化

        Args:
            llm: LangChain ChatModel
        """
        super().__init__(llm)
        self.prompt = ChatPromptTemplate.from_template(PATTERN_ANALYSIS_PROMPT)
        self.parser = JsonOutputParser()

        logger.debug("[A7] PatternAnalysisTask初期化完了")

    async def execute(self, context: AuditContext) -> TaskResult:
        """
        パターン分析タスクを実行

        複数期間のデータを分析し、継続性とパターンを評価します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            TaskResult: タスク実行結果
                - success: 継続性が維持され、カバー率が80%以上の場合True
                - result: 期間分析、ギャップ検出、パターン分析結果
                - reasoning: 検証内容の説明
                - confidence: 信頼度

        Note:
            - カバー率80%未満は失敗と判定
            - 継続性が維持されていない場合も失敗と判定
        """
        logger.info(f"[A7] パターン分析開始: {context.item_id}")

        # LLMの確認
        if not self.llm:
            logger.warning("[A7] LLMが設定されていません")
            return self._create_result(
                success=False,
                result=None,
                reasoning="LLMが設定されていません",
                confidence=0.0
            )

        # 期間データを抽出
        period_data = self._extract_period_data(context)
        logger.info(f"[A7] 期間データ準備完了: {len(period_data)}文字")

        try:
            # LLMチェーンを構築して実行
            chain = self.prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.control_description,
                "test_procedure": context.test_procedure,
                "period_data": period_data,
            })

            # 成功判定（コンプライアンス評価に基づく）
            compliance = result.get("compliance_assessment", {})
            gap_detection = result.get("gap_detection", {})

            continuity_ok = compliance.get("continuity_maintained", False)
            all_documented = compliance.get("all_periods_documented", False)
            pattern_ok = compliance.get("pattern_consistent", False)
            coverage = gap_detection.get("coverage_rate", 0.0)
            missing_periods = gap_detection.get("missing_periods", [])
            issues = compliance.get("issues", [])

            # 成功条件: 継続性維持 AND カバー率 >= 0.8
            success = continuity_ok and coverage >= 0.8

            logger.info(f"[A7] 完了: 継続性={'OK' if continuity_ok else 'NG'}, "
                       f"カバー率={coverage:.0%}, "
                       f"欠落期間={len(missing_periods)}件, "
                       f"問題点={len(issues)}件")

            # 証跡参照として期間分析を生成
            period_analysis = result.get("period_analysis", [])
            evidence_refs = [
                f"{p.get('period', '')}: {'記録あり' if p.get('record_exists') else '欠落'} ({p.get('record_date', 'N/A')})"
                for p in period_analysis[:6]
            ]

            # reasoning を整形
            reasoning = self._format_reasoning(result.get("reasoning", ""))

            return self._create_result(
                success=success,
                result=result,
                reasoning=reasoning,
                confidence=result.get("confidence", 0.0),
                evidence_refs=evidence_refs
            )

        except Exception as e:
            logger.error(f"[A7] パターン分析エラー: {e}", exc_info=True)
            return self._create_result(
                success=False,
                result=None,
                reasoning=f"パターン分析中にエラーが発生: {str(e)}",
                confidence=0.0
            )

    def _format_reasoning(self, reasoning_data) -> str:
        """
        reasoning データを文字列に整形

        Args:
            reasoning_data: LLMからの reasoning（文字列 or 辞書）

        Returns:
            str: 整形された reasoning 文字列
        """
        if isinstance(reasoning_data, dict):
            parts = []
            if reasoning_data.get("verification_summary"):
                parts.append(f"検証: {reasoning_data['verification_summary']}")
            if reasoning_data.get("evidence_details"):
                parts.append(f"証跡: {reasoning_data['evidence_details']}")
            if reasoning_data.get("conclusion"):
                parts.append(f"結論: {reasoning_data['conclusion']}")
            return " / ".join(parts) if parts else ""
        else:
            return str(reasoning_data)

    def _extract_period_data(self, context: AuditContext) -> str:
        """
        期間データを抽出・整理

        証跡ファイルから時系列データを抽出します。
        DocumentProcessorを使用して様々なファイル形式に対応。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            str: 抽出された期間データ
        """
        data_parts = []

        # まず統制記述をコンテキストとして追加（継続性要件の特定用）
        if context.control_description:
            data_parts.append(f"【統制の継続性要件】\n{context.control_description}")

        # 証跡ファイルをDocumentProcessorで処理
        for ef in context.evidence_files:
            try:
                # DocumentProcessorで統一的にテキスト抽出
                extracted = DocumentProcessor.extract_text(
                    file_name=ef.file_name,
                    extension=ef.extension,
                    base64_content=ef.base64_content,
                    mime_type=ef.mime_type,
                    use_di=True  # Document Intelligence があれば使用
                )

                content = extracted.text_content
                # 長すぎる場合は切り詰め
                if len(content) > 5000:
                    content = content[:5000] + f"\n... (以下省略)"

                data_parts.append(f"【{ef.file_name}】\n{content}")
                logger.debug(f"[A7] 抽出完了: {ef.file_name} (方法: {extracted.extraction_method})")

            except Exception as e:
                logger.warning(f"[A7] 読み取りエラー: {ef.file_name} - {e}")
                data_parts.append(f"【{ef.file_name}】\n[読み取り失敗: {str(e)}]")

        return "\n\n".join(data_parts) if data_parts else "期間データなし"
