"""
================================================================================
a1_semantic_search.py - A1: 意味検索（セマンティックサーチ）タスク
================================================================================

【概要】
キーワードの完全一致に頼らず、LLMの言語理解能力を活用して
証跡内の関連する記述を意味的に検索するタスクです。

【使用場面】
- 規程に記載された概念が証跡に含まれているか確認したい場合
- 類似表現や言い換えを含めて検索したい場合
- 例：「誠実性」→「倫理観」「正直な姿勢」等も検出

【処理フロー】
1. 証跡ファイルからテキストを抽出（DocumentProcessor使用）
2. 統制記述・テスト手続きと証跡テキストをLLMに送信
3. 意味的に関連する記述を特定
4. 検索結果をTaskResultとして返却

【入力】
- context.control_description: 統制記述
- context.test_procedure: テスト手続き
- context.evidence_files: 証跡ファイル（Base64エンコード）

【出力】
- TaskResult
  - success: 関連性スコア0.5以上かつマッチ1件以上でTrue
  - confidence: 全体的な関連性スコア（0.0〜1.0）
  - reasoning: 検証内容・証跡・結論の要約
  - evidence_references: マッチしたテキスト（最大3件）

【使用例】
```python
from core.tasks.a1_semantic_search import SemanticSearchTask

task = SemanticSearchTask(llm=chat_model)
result = await task.execute(context)

if result.success:
    print(f"関連記述が見つかりました: {result.reasoning}")
else:
    print(f"関連記述が見つかりませんでした: {result.reasoning}")
```

================================================================================
"""
import logging
from typing import List

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .base_task import BaseAuditTask, TaskType, TaskResult, AuditContext

# ロガーの設定
logger = logging.getLogger(__name__)


# =============================================================================
# LLMプロンプト定義
# =============================================================================

SEMANTIC_SEARCH_PROMPT = """あなたは内部統制監査の専門家です。
与えられた統制記述とテスト手続きに基づいて、エビデンス内の関連する記述を意味的に検索してください。

【重要な指示】
- キーワードの完全一致に頼らず、意味的な類似性で判断してください
- 例：「誠実性」という単語がなくても「倫理観」「正直な姿勢」「誠意ある対応」などの類似表現を検知
- 同義語、言い換え、関連概念も含めて検索してください

【統制記述】
{control_description}

【テスト手続き】
{test_procedure}

【検索対象テキスト】
{evidence_text}

【出力形式】
以下のJSON形式で回答してください：
{{
    "found_matches": [
        {{
            "original_term": "検索対象の概念",
            "matched_text": "エビデンス内で見つかった関連テキスト",
            "similarity_type": "完全一致/同義語/関連概念/言い換え",
            "confidence": 0.0-1.0の信頼度
        }}
    ],
    "overall_relevance": 0.0-1.0の全体的な関連性スコア,
    "reasoning": {{
        "verification_summary": "何を検索して何が見つかったか",
        "evidence_details": "見つかった記述の具体的な内容と出典（ファイル名含む）",
        "conclusion": "検索結果に基づく結論"
    }}
}}
"""


# =============================================================================
# タスククラス
# =============================================================================

class SemanticSearchTask(BaseAuditTask):
    """
    A1: 意味検索（セマンティックサーチ）タスク

    LLMの言語理解能力を活用し、キーワードの完全一致に頼らずに
    関連する記述を意味的に検索します。

    Attributes:
        task_type: TaskType.A1_SEMANTIC_SEARCH
        task_name: "意味検索（セマンティックサーチ）"
        description: タスクの説明

    Example:
        >>> task = SemanticSearchTask(llm=chat_model)
        >>> result = await task.execute(context)
        >>> print(f"成功: {result.success}, 信頼度: {result.confidence}")
    """

    # タスク識別情報
    task_type = TaskType.A1_SEMANTIC_SEARCH
    task_name = "意味検索（セマンティックサーチ）"
    description = "キーワードの完全一致に頼らず、意味的な類似性で関連記述を特定"

    def __init__(self, llm=None):
        """
        タスクを初期化

        Args:
            llm: LangChain の ChatModel インスタンス
        """
        super().__init__(llm)

        # プロンプトテンプレートとパーサーを設定
        self.prompt = ChatPromptTemplate.from_template(SEMANTIC_SEARCH_PROMPT)
        self.parser = JsonOutputParser()

        logger.debug(f"[A1] {self.task_name} を初期化しました")

    async def execute(self, context: AuditContext) -> TaskResult:
        """
        意味検索を実行

        統制記述・テスト手続きに関連する記述を証跡から検索します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            TaskResult: 検索結果
                - success: 関連記述が見つかった場合 True
                - confidence: 全体的な関連性スコア
                - reasoning: 検証内容の要約
                - evidence_references: マッチしたテキスト

        Note:
            - 関連性スコア0.5以上かつマッチ1件以上で成功と判定
            - テキストは10,000文字に制限して処理
        """
        logger.info(f"[A1] 意味検索開始: {context.item_id}")

        # --------------------------------------------------
        # 前提条件チェック
        # --------------------------------------------------
        if not self.llm:
            logger.warning("[A1] LLMが設定されていません")
            return self._create_result(
                success=False,
                result=None,
                reasoning="LLMが設定されていません",
                confidence=0.0
            )

        # --------------------------------------------------
        # 証跡テキストの抽出
        # --------------------------------------------------
        logger.debug(f"[A1] 証跡ファイル数: {len(context.evidence_files)}")
        evidence_text = self._extract_evidence_text(context.evidence_files)

        if not evidence_text:
            logger.warning("[A1] エビデンステキストが見つかりませんでした")
            return self._create_result(
                success=False,
                result=None,
                reasoning="エビデンステキストが見つかりませんでした",
                confidence=0.0
            )

        logger.info(f"[A1] 抽出したテキスト: {len(evidence_text):,}文字")

        # --------------------------------------------------
        # LLMによる意味検索実行
        # --------------------------------------------------
        try:
            logger.debug("[A1] LLMに意味検索を依頼中...")

            # LangChainチェーンを構築・実行
            chain = self.prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.control_description,
                "test_procedure": context.test_procedure,
                "evidence_text": evidence_text[:10000],  # テキスト長を制限
            })

            # --------------------------------------------------
            # 結果の解析
            # --------------------------------------------------
            overall_relevance = result.get("overall_relevance", 0.0)
            found_matches = result.get("found_matches", [])

            logger.info(f"[A1] 検索結果: 関連性={overall_relevance:.2f}, "
                       f"マッチ数={len(found_matches)}")

            # reasoningのフォーマット（辞書形式と文字列形式の両方に対応）
            reasoning_data = result.get("reasoning", "")
            if isinstance(reasoning_data, dict):
                reasoning_parts = []
                if reasoning_data.get("verification_summary"):
                    reasoning_parts.append(
                        f"検証: {reasoning_data['verification_summary']}"
                    )
                if reasoning_data.get("evidence_details"):
                    reasoning_parts.append(
                        f"証跡: {reasoning_data['evidence_details']}"
                    )
                if reasoning_data.get("conclusion"):
                    reasoning_parts.append(
                        f"結論: {reasoning_data['conclusion']}"
                    )
                reasoning = " / ".join(reasoning_parts) if reasoning_parts else ""
            else:
                reasoning = str(reasoning_data)

            # 成功判定: 関連性0.5以上かつマッチ1件以上
            is_success = overall_relevance >= 0.5 and len(found_matches) > 0

            if is_success:
                logger.info(f"[A1] 関連記述を発見: {len(found_matches)}件")
            else:
                logger.info("[A1] 十分な関連記述が見つかりませんでした")

            return self._create_result(
                success=is_success,
                result=result,
                reasoning=reasoning,
                confidence=overall_relevance,
                evidence_refs=[
                    m.get("matched_text", "")[:100]
                    for m in found_matches[:3]
                ]
            )

        except Exception as e:
            logger.error(f"[A1] 意味検索中にエラーが発生: {e}")
            return self._create_result(
                success=False,
                result=None,
                reasoning=f"意味検索中にエラーが発生: {str(e)}",
                confidence=0.0
            )

    def _extract_evidence_text(self, evidence_files: List) -> str:
        """
        証跡ファイルからテキストを抽出

        DocumentProcessor を使用して、PDF・Excel等からテキストを抽出します。
        DocumentProcessor が利用できない場合はフォールバック処理を使用。

        Args:
            evidence_files (List): EvidenceFile オブジェクトのリスト

        Returns:
            str: 抽出されたテキスト（空文字の場合もあり）
        """
        try:
            from ..document_processor import DocumentProcessor

            logger.debug("[A1] DocumentProcessor でテキスト抽出中...")

            # 全証跡ファイルからテキストを抽出
            extracted = DocumentProcessor.extract_all(evidence_files)

            # LLMプロンプト用にフォーマット
            formatted_text = DocumentProcessor.format_for_prompt(
                extracted,
                max_chars_per_file=10000
            )

            logger.debug(f"[A1] 抽出完了: {len(formatted_text):,}文字")
            return formatted_text

        except ImportError:
            logger.warning("[A1] DocumentProcessor が利用できません。"
                          "フォールバック処理を使用します")
            return self._extract_evidence_text_fallback(evidence_files)

    def _extract_evidence_text_fallback(self, evidence_files: List) -> str:
        """
        フォールバック: 基本的なテキスト抽出

        DocumentProcessor が利用できない場合の代替処理です。
        テキストファイル（.txt, .csv, .json等）のみ対応。

        Args:
            evidence_files (List): EvidenceFile オブジェクトのリスト

        Returns:
            str: 抽出されたテキスト

        Note:
            PDF・Excelファイルは処理できません。
        """
        import base64

        logger.debug("[A1] フォールバック処理でテキスト抽出中...")

        texts = []
        supported_extensions = ['.txt', '.csv', '.json', '.xml', '.log']

        for ef in evidence_files:
            ext = ef.extension.lower()
            if ext in supported_extensions:
                try:
                    content = base64.b64decode(ef.base64_content).decode('utf-8')
                    texts.append(f"[{ef.file_name}]\n{content}")
                    logger.debug(f"[A1] 抽出成功: {ef.file_name}")
                except Exception as e:
                    logger.warning(f"[A1] 抽出失敗: {ef.file_name} - {e}")
            else:
                logger.debug(f"[A1] スキップ（未対応形式）: {ef.file_name}")

        result = "\n\n".join(texts) if texts else ""
        logger.debug(f"[A1] フォールバック抽出完了: {len(result):,}文字")

        return result
