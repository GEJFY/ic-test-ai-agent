"""
================================================================================
a8_sod_detection.py - A8: 競合検出（SoD/職務分掌）タスク
================================================================================

【概要】
システム権限リストや業務フローを分析し、職務分掌（Segregation of Duties）の
違反を検出するタスクです。権限の競合や不適切な権限集中を識別します。

【主な機能】
- 申請/承認の分離確認
- 競合する権限の組み合わせ検出
- リスクレベルの評価
- 補完統制の有無確認
- 改善提案の生成

【典型的なSoD違反パターン】
- 同一人物が「仕訳入力」と「仕訳承認」を保持
- 同一人物が「発注」と「検収」を実施
- 同一人物が「マスタ変更」と「トランザクション入力」を実施
- 同一人物が「ユーザー作成」と「権限付与」を実施

【使用例】
```python
from core.tasks.a8_sod_detection import SoDDetectionTask
from core.tasks.base_task import AuditContext

# タスクを初期化
task = SoDDetectionTask(llm=llm)

# 評価を実行
result = await task.execute(context)

# 違反サマリーを確認
if result.result:
    summary = result.result["violation_summary"]
    print(f"分析ユーザー数: {summary['total_users_analyzed']}")
    print(f"違反ユーザー数: {summary['users_with_violations']}")
    print(f"高リスク違反: {summary['high_risk_violations']}件")
```

【処理フロー】
1. 職務分掌ルールを定義
2. 権限データを分析
3. 競合権限の組み合わせを検出
4. リスクレベルを評価
5. 補完統制を考慮した総合評価

================================================================================
"""
import logging
import base64
from typing import List
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .base_task import BaseAuditTask, TaskType, TaskResult, AuditContext

# =============================================================================
# ログ設定
# =============================================================================

logger = logging.getLogger(__name__)

# =============================================================================
# プロンプトテンプレート
# =============================================================================

SOD_DETECTION_PROMPT = """あなたは内部統制監査の専門家で、職務分掌（SoD: Segregation of Duties）の専門家です。
システム権限リストや業務フローを分析し、職務分掌の違反を検出してください。

【重要な指示】
1. 「申請」と「承認」の分離を確認
2. 以下の典型的なSoD違反パターンを検出：
   - 同一人物が「仕訳入力」と「仕訳承認」の両方の権限を保持
   - 同一人物が「発注」と「検収」の両方を実施
   - 同一人物が「マスタ変更」と「トランザクション入力」を実施
3. 権限の組み合わせによるリスクを評価
4. 補完統制（軽減措置）の有無を確認

【統制記述】
{control_description}

【テスト手続き】
{test_procedure}

【権限・業務データ】
{authority_data}

【出力形式】
以下のJSON形式で回答してください：
{{
    "sod_rules": [
        {{
            "rule_id": "ルールID",
            "rule_name": "ルール名",
            "conflicting_functions": ["機能A", "機能B"],
            "risk_description": "このSoD違反のリスク",
            "severity": "高/中/低"
        }}
    ],
    "authority_analysis": [
        {{
            "user_id": "ユーザーID",
            "user_name": "ユーザー名",
            "department": "部署",
            "authorities": ["保有権限リスト"],
            "sod_violations": [
                {{
                    "rule_id": "違反ルールID",
                    "conflicting_authorities": ["競合権限A", "競合権限B"],
                    "violation_type": "直接保有/兼務/代理",
                    "risk_level": "高/中/低"
                }}
            ]
        }}
    ],
    "violation_summary": {{
        "total_users_analyzed": 分析ユーザー数,
        "users_with_violations": 違反ユーザー数,
        "total_violations": 総違反件数,
        "high_risk_violations": 高リスク違反数,
        "medium_risk_violations": 中リスク違反数,
        "low_risk_violations": 低リスク違反数
    }},
    "compensating_controls": [
        {{
            "control_name": "補完統制名",
            "description": "説明",
            "mitigated_violations": ["軽減される違反"],
            "effectiveness": "有効/部分的/無効"
        }}
    ],
    "overall_assessment": {{
        "sod_compliance_level": "準拠/概ね準拠/要改善/非準拠",
        "key_risks": ["主要リスク"],
        "recommendations": ["改善提案"]
    }},
    "confidence": 0.0-1.0,
    "reasoning": "評価結果の総括"
}}
"""


# =============================================================================
# メインクラス: SoDDetectionTask
# =============================================================================

class SoDDetectionTask(BaseAuditTask):
    """
    A8: 競合検出（SoD/職務分掌）タスク

    システム権限リストや業務フローを分析し、
    職務分掌の違反を検出するタスクです。

    【主な機能】
    - SoDルールの定義
    - ユーザー権限の分析
    - 競合権限の検出
    - リスクレベルの評価
    - 補完統制の考慮

    【処理フロー】
    1. 業界標準のSoDルールを定義
    2. 権限マトリクスを分析
    3. 各ユーザーの権限を検証
    4. 違反を検出・分類
    5. 総合評価を返却

    Attributes:
        prompt: SoD検出用のプロンプトテンプレート
        parser: JSON出力パーサー

    使用例:
        ```python
        task = SoDDetectionTask(llm=llm)
        result = await task.execute(context)
        ```
    """

    # タスク識別情報
    task_type = TaskType.A8_SOD_DETECTION
    task_name = "競合検出ルール（SoD/職務分掌）"
    description = "システム権限を分析し、同一人物への競合権限付与（職務分掌違反）を検出"

    def __init__(self, llm=None):
        """
        タスクを初期化

        Args:
            llm: LangChain ChatModel
        """
        super().__init__(llm)
        self.prompt = ChatPromptTemplate.from_template(SOD_DETECTION_PROMPT)
        self.parser = JsonOutputParser()

        logger.debug("[A8] SoDDetectionTask初期化完了")

    async def execute(self, context: AuditContext) -> TaskResult:
        """
        SoD検出タスクを実行

        権限データを分析し、職務分掌違反を検出します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            TaskResult: タスク実行結果
                - success: 準拠/概ね準拠かつ高リスク違反がない場合True
                - result: SoDルール、権限分析、違反サマリー
                - reasoning: 評価結果の総括
                - confidence: 信頼度

        Note:
            - 高リスク違反がある場合は失敗と判定
            - 補完統制により軽減される場合は考慮
        """
        logger.info(f"[A8] SoD検出開始: {context.item_id}")

        # LLMの確認
        if not self.llm:
            logger.warning("[A8] LLMが設定されていません")
            return self._create_result(
                success=False,
                result=None,
                reasoning="LLMが設定されていません",
                confidence=0.0
            )

        # 権限データを抽出
        authority_data = self._extract_authority_data(context)
        logger.info(f"[A8] 権限データ準備完了: {len(authority_data)}文字")

        try:
            # LLMチェーンを構築して実行
            chain = self.prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.control_description,
                "test_procedure": context.test_procedure,
                "authority_data": authority_data,
            })

            # 成功判定（総合評価に基づく）
            assessment = result.get("overall_assessment", {})
            summary = result.get("violation_summary", {})

            compliance_level = assessment.get("sod_compliance_level", "")
            high_risk = summary.get("high_risk_violations", 0)
            total_violations = summary.get("total_violations", 0)
            users_with_violations = summary.get("users_with_violations", 0)
            recommendations = assessment.get("recommendations", [])

            # 成功条件: 準拠/概ね準拠 AND 高リスク違反なし
            success = compliance_level in ["準拠", "概ね準拠"] and high_risk == 0

            logger.info(f"[A8] 完了: 準拠レベル={compliance_level}, "
                       f"違反ユーザー={users_with_violations}人, "
                       f"総違反={total_violations}件, "
                       f"高リスク={high_risk}件")

            # 証跡参照として違反サマリーを生成
            authority_analysis = result.get("authority_analysis", [])
            evidence_refs = []
            for user in authority_analysis[:5]:
                violations = user.get("sod_violations", [])
                if violations:
                    user_name = user.get('user_name', 'Unknown')
                    evidence_refs.append(f"{user_name}: {len(violations)}件の違反")

            return self._create_result(
                success=success,
                result=result,
                reasoning=result.get("reasoning", ""),
                confidence=result.get("confidence", 0.0),
                evidence_refs=evidence_refs
            )

        except Exception as e:
            logger.error(f"[A8] SoD検出エラー: {e}", exc_info=True)
            return self._create_result(
                success=False,
                result=None,
                reasoning=f"SoD検出中にエラーが発生: {str(e)}",
                confidence=0.0
            )

    def _extract_authority_data(self, context: AuditContext) -> str:
        """
        権限データを抽出

        証跡ファイルから権限マトリクスや業務フローを抽出します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            str: 抽出された権限データ
        """
        data_parts = []

        # まず統制記述をコンテキストとして追加（SoD要件の特定用）
        if context.control_description:
            data_parts.append(f"【職務分掌の要件】\n{context.control_description}")

        # 証跡ファイルを処理（権限リスト、ユーザーマトリクス等）
        for ef in context.evidence_files:
            ext = ef.extension.lower()

            # テキスト系ファイルの場合
            if ext in ['.csv', '.txt', '.json', '.xml']:
                try:
                    content = base64.b64decode(ef.base64_content).decode('utf-8')
                    # 長すぎる場合は切り詰め
                    if len(content) > 8000:
                        content = content[:8000] + f"\n... (以下省略)"
                    data_parts.append(f"【{ef.file_name}】\n{content}")
                    logger.debug(f"[A8] 抽出完了: {ef.file_name}")
                except Exception as e:
                    logger.warning(f"[A8] 読み取りエラー: {ef.file_name} - {e}")
                    data_parts.append(f"【{ef.file_name}】\n[読み取り失敗]")

            # Excelファイルの場合（権限マトリクスの可能性が高い）
            elif ext in ['.xlsx', '.xls']:
                data_parts.append(f"【{ef.file_name}】\n[Excelファイル - 権限マトリクスの可能性]")
                logger.debug(f"[A8] Excel検出: {ef.file_name}")

            else:
                data_parts.append(f"【{ef.file_name}】\n[{ef.mime_type}]")

        return "\n\n".join(data_parts) if data_parts else "権限データなし"
