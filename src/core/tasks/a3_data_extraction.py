"""
================================================================================
a3_data_extraction.py - A3: 構造化データ抽出タスク
================================================================================

【概要】
複雑な表データから数値を抽出し、単位・科目名を正規化して
異なるソース間での突合（照合）を行うタスクです。

【主な機能】
- 表形式データからの数値抽出
- 単位の正規化（百万円→円、千円→円など）
- 科目名の正規化（売上高/Revenue/売上を同一として認識）
- 複数ソース間での数値突合
- 差異の検出と重要性評価

【対応ファイル形式】
- テキスト系: .csv, .txt, .json, .xml
- ドキュメント: .pdf, .docx, .xlsx（DocumentProcessor経由）

【使用例】
```python
from core.tasks.a3_data_extraction import DataExtractionTask
from core.tasks.base_task import AuditContext

# タスクを初期化
task = DataExtractionTask(llm=llm)

# 評価を実行
result = await task.execute(context)

# 突合結果を確認
if result.success:
    reconciliation = result.result["reconciliation"]
    for item in reconciliation:
        print(f"{item['item_name']}: {'一致' if item['match'] else '不一致'}")
```

【処理フロー】
1. 証跡ファイルからテキストを抽出
2. LLMで表データを解析し数値を抽出
3. 単位・科目名を正規化
4. 異なるソース間で数値を突合
5. 差異の有無と重要性を判定

================================================================================
"""
import logging
import base64
from typing import List, Dict, Any
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from .base_task import BaseAuditTask, TaskType, TaskResult, AuditContext

# プロンプトをprompts.pyからインポート
from ..prompts import A3_DATA_EXTRACTION_PROMPT

# =============================================================================
# ログ設定
# =============================================================================

logger = logging.getLogger(__name__)


# =============================================================================
# メインクラス: DataExtractionTask
# =============================================================================

class DataExtractionTask(BaseAuditTask):
    """
    A3: 構造化データ抽出タスク

    複雑な表データから数値を抽出し、単位・科目名を正規化して
    異なるソース間での突合を行います。

    【主な機能】
    - 表形式データの解析と数値抽出
    - 単位の正規化（百万円→円など）
    - 科目名の同義語認識
    - 複数ソース間での数値照合
    - 差異の重要性評価

    【処理フロー】
    1. DocumentProcessorで証跡からテキスト抽出
    2. LLMで表データを解析
    3. 抽出した数値を正規化
    4. ソース間で突合を実施
    5. 差異を評価して結果を返却

    Attributes:
        prompt: データ抽出用のプロンプトテンプレート
        parser: JSON出力パーサー

    使用例:
        ```python
        task = DataExtractionTask(llm=llm)
        result = await task.execute(context)
        ```
    """

    # タスク識別情報
    task_type = TaskType.A3_DATA_EXTRACTION
    task_name = "構造化データ抽出"
    description = "複雑な表から数値を抽出し、単位・科目名を正規化して突合を実施"

    def __init__(self, llm=None):
        """
        タスクを初期化

        Args:
            llm: LangChain ChatModel
        """
        super().__init__(llm)
        self.prompt = ChatPromptTemplate.from_template(A3_DATA_EXTRACTION_PROMPT)
        self.parser = JsonOutputParser()

        logger.debug("[A3] DataExtractionTask初期化完了")

    async def execute(self, context: AuditContext) -> TaskResult:
        """
        データ抽出と突合タスクを実行

        証跡ファイルからデータを抽出し、異なるソース間で
        数値の突合を行います。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            TaskResult: タスク実行結果
                - success: 全項目が一致した場合、または重要な差異がない場合True
                - result: 抽出データと突合結果
                - reasoning: 検証内容の説明
                - confidence: 信頼度

        Note:
            - 重要な差異がない場合は成功と判定
            - 差異率が小さい場合も成功と判定可能
        """
        logger.info(f"[A3] データ抽出開始: {context.item_id}")

        # LLMの確認
        if not self.llm:
            logger.warning("[A3] LLMが設定されていません")
            return self._create_result(
                success=False,
                result=None,
                reasoning="LLMが設定されていません",
                confidence=0.0
            )

        # データソースを準備
        data_sources = self._prepare_data_sources(context)

        if not data_sources:
            logger.warning("[A3] 抽出可能なデータソースがありません")
            return self._create_result(
                success=False,
                result=None,
                reasoning="抽出可能なデータソースが見つかりませんでした",
                confidence=0.0
            )

        logger.info(f"[A3] データソース準備完了: {len(data_sources)}文字")

        try:
            # LLMチェーンを構築して実行
            chain = self.prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "test_procedure": context.test_procedure,
                "data_sources": data_sources,
            })

            # 成功判定（突合結果に基づく）
            summary = result.get("summary", {})
            unmatched = summary.get("unmatched_count", 0)
            matched = summary.get("matched_count", 0)
            material_differences = summary.get("material_differences", [])

            # 成功条件: 全項目一致 または 重要な差異なし
            success = unmatched == 0 or len(material_differences) == 0

            logger.info(f"[A3] 突合結果: 一致{matched}件, 不一致{unmatched}件, "
                       f"重要差異{len(material_differences)}件")

            # reasoning を整形
            reasoning = self._format_reasoning(result.get("reasoning", ""))

            return self._create_result(
                success=success,
                result=result,
                reasoning=reasoning,
                confidence=result.get("confidence", 0.0),
                evidence_refs=self._get_source_names(context)
            )

        except Exception as e:
            logger.error(f"[A3] データ抽出エラー: {e}", exc_info=True)
            return self._create_result(
                success=False,
                result=None,
                reasoning=f"データ抽出中にエラーが発生: {str(e)}",
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

    def _prepare_data_sources(self, context: AuditContext) -> str:
        """
        データソースを準備

        DocumentProcessorを使用して証跡ファイルからテキストを抽出します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            str: 抽出されたデータソーステキスト
        """
        try:
            from ..document_processor import DocumentProcessor

            logger.debug("[A3] DocumentProcessorでテキスト抽出")

            # 全証跡ファイルからテキストを抽出
            extracted = DocumentProcessor.extract_all(context.evidence_files)

            # フォーマット
            sources = []
            for ec in extracted:
                content = ec.text_content
                # 長すぎる場合は切り詰め
                if len(content) > 10000:
                    content = content[:10000] + f"\n... (以下省略、全{len(ec.text_content)}文字)"

                sources.append(f"【ソース: {ec.file_name}】\n{content}")
                logger.debug(f"[A3] 抽出完了: {ec.file_name} ({len(ec.text_content)}文字)")

            # 統制記述もコンテキストとして追加
            if context.control_description:
                sources.append(f"【統制記述】\n{context.control_description}")

            return "\n\n".join(sources) if sources else ""

        except ImportError:
            logger.warning("[A3] DocumentProcessor利用不可、フォールバック処理を使用")
            return self._prepare_data_sources_fallback(context)

    def _prepare_data_sources_fallback(self, context: AuditContext) -> str:
        """
        フォールバック用のデータソース準備

        DocumentProcessorが利用できない場合の基本的なテキスト抽出。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            str: 抽出されたデータソーステキスト
        """
        sources = []

        for ef in context.evidence_files:
            ext = ef.extension.lower()

            # テキストファイルの場合はデコード
            if ext in ['.csv', '.txt', '.json']:
                try:
                    content = base64.b64decode(ef.base64_content).decode('utf-8')
                    sources.append(f"【ソース: {ef.file_name}】\n{content}")
                    logger.debug(f"[A3] フォールバック抽出: {ef.file_name}")
                except Exception as e:
                    logger.warning(f"[A3] 読み取りエラー: {ef.file_name} - {e}")
                    sources.append(f"【ソース: {ef.file_name}】\n[読み取りエラー]")
            else:
                sources.append(f"【ソース: {ef.file_name}】\n[{ext}ファイル - 内容解析が必要]")

        # 統制記述を追加
        if context.control_description:
            sources.append(f"【統制記述】\n{context.control_description}")

        return "\n\n".join(sources) if sources else ""

    def _get_source_names(self, context: AuditContext) -> List[str]:
        """
        ソースファイル名のリストを取得

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            List[str]: ファイル名のリスト
        """
        return [ef.file_name for ef in context.evidence_files]

    def _decode_text_file(self, evidence_file) -> str:
        """
        テキストファイルをBase64デコード（レガシーフォールバック用）

        Args:
            evidence_file: 証跡ファイル

        Returns:
            str: デコードされたテキスト内容
        """
        try:
            return base64.b64decode(evidence_file.base64_content).decode('utf-8')
        except Exception as e:
            logger.warning(f"[A3] デコードエラー: {e}")
            return ""
