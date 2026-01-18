"""
================================================================================
a5_semantic_reasoning.py - A5: 意味検索 + 推論タスク
================================================================================

【概要】
規程の抽象的な要求事項と実際の実施記録が意図に沿っているかを
判定するタスクです。AIが自律的に判定基準を定義して評価します。

【主な機能】
- 抽象的な規程要求の具体的基準への分解
- 金額基準・専門家関与・承認プロセス等の判定基準定義
- 証跡内容と基準の照合
- コンプライアンスレベルの評価

【典型的なユースケース】
- 「重要取引は適切に審査」→ 何が「重要」で何が「適切」かを定義
- 「経営層の承認を得る」→ 誰が「経営層」で「承認」の証跡は何かを確認
- 「定期的にレビュー」→ 「定期的」の頻度と「レビュー」の内容を検証

【使用例】
```python
from core.tasks.a5_semantic_reasoning import SemanticReasoningTask
from core.tasks.base_task import AuditContext

# タスクを初期化
task = SemanticReasoningTask(llm=llm)

# 評価を実行
result = await task.execute(context)

# 準拠レベルを確認
assessment = result.result["overall_assessment"]
print(f"準拠レベル: {assessment['compliance_level']}")
print(f"満たした基準: {assessment['criteria_met']}/{assessment['criteria_total']}")
```

【処理フロー】
1. 規程要求を解析し判定基準を定義
2. 証跡から関連情報を抽出
3. 各基準に対する準拠状況を評価
4. 総合的なコンプライアンスレベルを判定

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

SEMANTIC_REASONING_PROMPT = """あなたは内部統制監査の専門家です。
規程の抽象的な要求事項と、実際の実施記録が意図に沿っているかを判定してください。

【重要な指示】
1. 規程の抽象的な要求（「重要取引は適切に審査」等）を具体的な判定基準に分解
2. AIが自律的に以下の判定基準を定義して評価：
   - 金額基準（重要性の閾値）
   - 専門家の関与（必要な資格・経験）
   - 承認プロセス（承認者の適格性、タイミング）
   - 文書化要件（記録の完全性）
3. 実際の記録がこれらの基準を満たしているか判定
4. 証跡の具体的な記載内容を引用して説明

【統制記述（規程要求）】
{control_description}

【テスト手続き】
{test_procedure}

【実施記録・エビデンス】
{evidence_data}

【出力形式】
以下のJSON形式で回答してください：
{{
    "requirement_analysis": {{
        "abstract_requirement": "規程の抽象的な要求",
        "interpreted_criteria": [
            {{
                "criterion_name": "判定基準名",
                "description": "基準の説明",
                "threshold_or_standard": "具体的な閾値・基準",
                "rationale": "この基準を設定した根拠"
            }}
        ]
    }},
    "evidence_evaluation": [
        {{
            "criterion_name": "判定基準名",
            "evidence_found": "発見されたエビデンスの具体的な記載内容（引用）",
            "evidence_source": "証跡ファイル名とその箇所",
            "meets_criterion": true/false,
            "gap_analysis": "基準との差異（あれば）"
        }}
    ],
    "overall_assessment": {{
        "compliance_level": "完全準拠/概ね準拠/一部不備/重大な不備",
        "criteria_met": 満たした基準数,
        "criteria_total": 総基準数,
        "key_findings": ["主要な発見事項"]
    }},
    "confidence": 0.0-1.0,
    "reasoning": {{
        "verification_summary": "何を検証して何が確認できたか（具体的に）",
        "evidence_details": "どの証跡のどの部分で確認したか（引用含む）",
        "conclusion": "結論とその根拠"
    }}
}}
"""


# =============================================================================
# メインクラス: SemanticReasoningTask
# =============================================================================

class SemanticReasoningTask(BaseAuditTask):
    """
    A5: 意味検索 + 推論タスク

    抽象的な規程要求と実際の実施記録の整合性を、
    AIが自律的に判定基準を定義して評価するタスクです。

    【主な機能】
    - 抽象的な規程要求の解析
    - 具体的な判定基準の自動定義
    - 証跡との照合と準拠状況評価
    - コンプライアンスレベルの判定

    【処理フロー】
    1. 規程の抽象的な要求を解析
    2. 判定基準（金額・承認者・頻度等）を定義
    3. 証跡から関連情報を抽出
    4. 各基準との照合を実施
    5. 総合的な準拠レベルを判定

    Attributes:
        prompt: 意味推論用のプロンプトテンプレート
        parser: JSON出力パーサー

    使用例:
        ```python
        task = SemanticReasoningTask(llm=llm)
        result = await task.execute(context)
        ```
    """

    # タスク識別情報
    task_type = TaskType.A5_SEMANTIC_REASONING
    task_name = "意味検索 + 推論"
    description = "抽象的な規程要求と実際の実施記録の整合性を判定基準を定義して評価"

    def __init__(self, llm=None):
        """
        タスクを初期化

        Args:
            llm: LangChain ChatModel
        """
        super().__init__(llm)
        self.prompt = ChatPromptTemplate.from_template(SEMANTIC_REASONING_PROMPT)
        self.parser = JsonOutputParser()

        logger.debug("[A5] SemanticReasoningTask初期化完了")

    async def execute(self, context: AuditContext) -> TaskResult:
        """
        意味推論タスクを実行

        規程要求と実施記録の整合性を評価し、
        コンプライアンスレベルを判定します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            TaskResult: タスク実行結果
                - success: 完全準拠または概ね準拠の場合True
                - result: 判定基準、評価結果、コンプライアンスレベル
                - reasoning: 検証内容の説明
                - confidence: 信頼度

        Note:
            - 「完全準拠」「概ね準拠」で成功と判定
            - 「一部不備」「重大な不備」で要確認と判定
        """
        logger.info(f"[A5] 意味推論開始: {context.item_id}")

        # LLMの確認
        if not self.llm:
            logger.warning("[A5] LLMが設定されていません")
            return self._create_result(
                success=False,
                result=None,
                reasoning="LLMが設定されていません",
                confidence=0.0
            )

        # 証跡データを抽出
        evidence_data = self._extract_evidence_data(context)
        logger.info(f"[A5] 証跡データ準備完了: {len(evidence_data)}文字")

        try:
            # LLMチェーンを構築して実行
            chain = self.prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.control_description,
                "test_procedure": context.test_procedure,
                "evidence_data": evidence_data,
            })

            # 成功判定（コンプライアンスレベルに基づく）
            assessment = result.get("overall_assessment", {})
            compliance_level = assessment.get("compliance_level", "")

            success = compliance_level in ["完全準拠", "概ね準拠"]

            # 統計情報
            criteria_met = assessment.get("criteria_met", 0)
            criteria_total = assessment.get("criteria_total", 0)
            key_findings = assessment.get("key_findings", [])

            logger.info(f"[A5] 完了: 準拠レベル = {compliance_level}, "
                       f"基準充足 = {criteria_met}/{criteria_total}, "
                       f"発見事項 = {len(key_findings)}件")

            # 証跡参照を構築
            evidence_refs = self._build_evidence_refs(result.get("evidence_evaluation", []))

            # reasoning を整形
            reasoning = self._format_reasoning(result.get("reasoning", ""))

            return self._create_result(
                success=success,
                result=result,
                reasoning=reasoning,
                confidence=result.get("confidence", 0.0),
                evidence_refs=evidence_refs[:5]  # 最大5件
            )

        except Exception as e:
            logger.error(f"[A5] 意味推論エラー: {e}", exc_info=True)
            return self._create_result(
                success=False,
                result=None,
                reasoning=f"意味推論中にエラーが発生: {str(e)}",
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

    def _build_evidence_refs(self, evidence_evaluation: List[dict]) -> List[str]:
        """
        証跡参照リストを構築

        各判定基準の評価結果から証跡参照を抽出します。

        Args:
            evidence_evaluation (List[dict]): 基準評価結果のリスト

        Returns:
            List[str]: 証跡参照のリスト
        """
        evidence_refs = []

        for eval_item in evidence_evaluation:
            # ソース情報があれば追加
            source = eval_item.get("evidence_source", "")
            if source:
                evidence_refs.append(source)
            # なければ発見したエビデンスの先頭部分を追加
            elif eval_item.get("evidence_found"):
                evidence_refs.append(eval_item.get("evidence_found", "")[:100])

        return evidence_refs

    def _extract_evidence_data(self, context: AuditContext) -> str:
        """
        証跡ファイルからデータを抽出

        DocumentProcessorを使用して証跡ファイルからテキストを抽出します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            str: 抽出されたエビデンスデータ
        """
        try:
            from ..document_processor import DocumentProcessor

            logger.debug("[A5] DocumentProcessorでテキスト抽出")

            # 全証跡ファイルからテキストを抽出
            extracted = DocumentProcessor.extract_all(context.evidence_files)

            # プロンプト用にフォーマット（ファイルあたり最大8000文字）
            return DocumentProcessor.format_for_prompt(extracted, max_chars_per_file=8000)

        except ImportError:
            logger.warning("[A5] DocumentProcessor利用不可、フォールバック処理を使用")
            return self._extract_evidence_data_fallback(context)

    def _extract_evidence_data_fallback(self, context: AuditContext) -> str:
        """
        フォールバック用のデータ抽出

        DocumentProcessorが利用できない場合の基本的なテキスト抽出。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            str: 抽出されたエビデンスデータ
        """
        data_parts = []

        for ef in context.evidence_files:
            ext = ef.extension.lower()

            # テキストファイルの場合はデコード
            if ext in ['.txt', '.csv', '.json', '.xml', '.log']:
                try:
                    content = base64.b64decode(ef.base64_content).decode('utf-8')
                    data_parts.append(f"[{ef.file_name}]\n{content[:5000]}")
                    logger.debug(f"[A5] フォールバック抽出: {ef.file_name}")
                except Exception as e:
                    logger.warning(f"[A5] 抽出エラー: {ef.file_name} - {e}")
                    data_parts.append(f"[{ef.file_name}] - 読み取りエラー")
            else:
                data_parts.append(f"[{ef.file_name}] - {ef.mime_type}")

        return "\n\n".join(data_parts) if data_parts else "エビデンスデータなし"
