"""
================================================================================
a6_multi_document.py - A6: 複数文書統合理解タスク
================================================================================

【概要】
複数の証跡文書を統合してプロセス全体を再構成し、
一貫性を評価するタスクです。バラバラな証跡から業務フローを理解します。

【主な機能】
- 複数文書の統合分析
- 時系列でのプロセス再構成
- 文書間の関連性（参照番号・日付・担当者）の紐付け
- 抜け漏れ・矛盾・時系列逆転の検出
- 完全性評価

【典型的なユースケース】
- 議事録 + 承認記録 + 配布記録の整合性確認
- 申請→審査→承認→実行のフロー確認
- 複数部署にまたがるプロセスの確認

【使用例】
```python
from core.tasks.a6_multi_document import MultiDocumentTask
from core.tasks.base_task import AuditContext

# タスクを初期化
task = MultiDocumentTask(llm=llm)

# 評価を実行
result = await task.execute(context)

# プロセスフローを確認
if result.success:
    timeline = result.result["process_reconstruction"]["timeline"]
    for event in timeline:
        print(f"{event['date']}: {event['event']}")
```

【処理フロー】
1. 各証跡文書を解析
2. 時系列でイベントを並べ替え
3. プロセスフローを再構成
4. 一貫性・完全性をチェック
5. 問題点を報告

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

MULTI_DOCUMENT_PROMPT = """あなたは内部統制監査の専門家です。
複数の証跡文書を統合して、プロセス全体を再構成し、一貫性を評価してください。

【重要な指示】
1. 議事録、承認記録、配布記録、メール、システム画面など、バラバラな証跡を統合
2. 各証跡の時系列を確認し、プロセスの流れを再構成
3. プロセス全体に不備（抜け漏れ、矛盾、逆転）がないか一貫性を確認
4. 証跡間の関連性（参照番号、日付、担当者等）を紐付け

【統制記述】
{control_description}

【テスト手続き】
{test_procedure}

【証跡文書一覧】
{evidence_documents}

【出力形式】
以下のJSON形式で回答してください：
{{
    "document_analysis": [
        {{
            "document_name": "文書名",
            "document_type": "文書種別（議事録/承認記録/メール等）",
            "date": "文書の日付",
            "key_information": "抽出した重要情報",
            "related_documents": ["関連する他の文書名"],
            "process_step": "このプロセスでの位置づけ"
        }}
    ],
    "process_reconstruction": {{
        "timeline": [
            {{
                "sequence": 1,
                "date": "YYYY-MM-DD",
                "event": "イベント/アクション",
                "document_source": "根拠文書",
                "actors": ["関係者"]
            }}
        ],
        "process_flow": "プロセス全体の流れの説明"
    }},
    "consistency_check": {{
        "timeline_consistent": true/false,
        "no_gaps": true/false,
        "no_contradictions": true/false,
        "issues_found": [
            {{
                "issue_type": "抜け漏れ/矛盾/時系列逆転",
                "description": "問題の説明",
                "affected_documents": ["関連文書"],
                "severity": "高/中/低"
            }}
        ]
    }},
    "completeness_assessment": {{
        "expected_steps": ["期待されるプロセスステップ"],
        "documented_steps": ["文書化されているステップ"],
        "missing_steps": ["欠落しているステップ"],
        "completeness_score": 0.0-1.0
    }},
    "confidence": 0.0-1.0,
    "reasoning": {{
        "verification_summary": "何を検証して何が確認できたか（具体的に）",
        "evidence_details": "どの文書のどの部分で確認したか（具体的な記載を引用）",
        "conclusion": "結論とその根拠"
    }}
}}
"""


# =============================================================================
# メインクラス: MultiDocumentTask
# =============================================================================

class MultiDocumentTask(BaseAuditTask):
    """
    A6: 複数文書統合理解タスク

    複数の証跡文書を統合してプロセス全体を再構成し、
    一貫性と完全性を評価するタスクです。

    【主な機能】
    - 複数文書の時系列分析
    - プロセスフローの再構成
    - 文書間の関連性紐付け
    - 一貫性・完全性チェック
    - 問題点の検出

    【処理フロー】
    1. 各証跡文書を解析
    2. 時系列でイベントを整理
    3. プロセスフローを再構成
    4. 一貫性・完全性を評価
    5. 発見事項を報告

    Attributes:
        prompt: 複数文書統合用のプロンプトテンプレート
        parser: JSON出力パーサー

    使用例:
        ```python
        task = MultiDocumentTask(llm=llm)
        result = await task.execute(context)
        ```
    """

    # タスク識別情報
    task_type = TaskType.A6_MULTI_DOCUMENT
    task_name = "複数文書統合理解（マルチ文書理解）"
    description = "バラバラな証跡を統合してプロセスを再構成し、一貫性を確認"

    def __init__(self, llm=None):
        """
        タスクを初期化

        Args:
            llm: LangChain ChatModel
        """
        super().__init__(llm)
        self.prompt = ChatPromptTemplate.from_template(MULTI_DOCUMENT_PROMPT)
        self.parser = JsonOutputParser()

        logger.debug("[A6] MultiDocumentTask初期化完了")

    async def execute(self, context: AuditContext) -> TaskResult:
        """
        複数文書統合タスクを実行

        複数の証跡文書を分析し、プロセスの一貫性と完全性を評価します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            TaskResult: タスク実行結果
                - success: 時系列が一貫し、完全性スコアが0.7以上の場合True
                - result: 文書分析、プロセス再構成、一貫性チェック結果
                - reasoning: 検証内容の説明
                - confidence: 信頼度

        Note:
            - 矛盾がある場合は失敗と判定
            - 完全性スコアが低い場合も失敗と判定
        """
        logger.info(f"[A6] 複数文書統合開始: {context.item_id}")

        # LLMの確認
        if not self.llm:
            logger.warning("[A6] LLMが設定されていません")
            return self._create_result(
                success=False,
                result=None,
                reasoning="LLMが設定されていません",
                confidence=0.0
            )

        # 証跡文書の確認
        if len(context.evidence_files) < 1:
            logger.warning("[A6] 証跡文書がありません")
            return self._create_result(
                success=False,
                result=None,
                reasoning="複数文書統合には証跡文書が必要です",
                confidence=0.0
            )

        logger.info(f"[A6] 処理対象文書: {len(context.evidence_files)}件")

        # 文書を準備
        evidence_documents = self._prepare_documents(context)

        try:
            # LLMチェーンを構築して実行
            chain = self.prompt | self.llm | self.parser

            result = await chain.ainvoke({
                "control_description": context.control_description,
                "test_procedure": context.test_procedure,
                "evidence_documents": evidence_documents,
            })

            # 成功判定（一貫性と完全性に基づく）
            consistency = result.get("consistency_check", {})
            completeness = result.get("completeness_assessment", {})

            timeline_ok = consistency.get("timeline_consistent", False)
            no_gaps = consistency.get("no_gaps", False)
            no_contradictions = consistency.get("no_contradictions", False)
            completeness_score = completeness.get("completeness_score", 0.0)
            issues_found = consistency.get("issues_found", [])

            # 成功条件: 時系列一貫 AND 矛盾なし AND 完全性スコア >= 0.7
            success = timeline_ok and no_contradictions and completeness_score >= 0.7

            logger.info(f"[A6] 完了: 時系列一貫={'OK' if timeline_ok else 'NG'}, "
                       f"矛盾={'なし' if no_contradictions else 'あり'}, "
                       f"完全性スコア={completeness_score:.2f}, "
                       f"問題点={len(issues_found)}件")

            # 証跡参照としてタイムラインを生成
            timeline = result.get("process_reconstruction", {}).get("timeline", [])
            evidence_refs = [
                f"{t.get('date', '')}: {t.get('event', '')} ({t.get('document_source', '')})"
                for t in timeline[:5]
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
            logger.error(f"[A6] 複数文書統合エラー: {e}", exc_info=True)
            return self._create_result(
                success=False,
                result=None,
                reasoning=f"複数文書統合中にエラーが発生: {str(e)}",
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

    def _prepare_documents(self, context: AuditContext) -> str:
        """
        文書サマリーを準備

        DocumentProcessorを使用して証跡文書からテキストを抽出します。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            str: フォーマット済みの文書サマリー
        """
        try:
            from ..document_processor import DocumentProcessor

            logger.debug("[A6] DocumentProcessorで文書を抽出")

            # 全証跡ファイルからテキストを抽出
            extracted = DocumentProcessor.extract_all(context.evidence_files)

            # 文書番号付きでフォーマット
            docs = []
            for i, ec in enumerate(extracted, 1):
                content = ec.text_content
                # 長すぎる場合は切り詰め
                if len(content) > 5000:
                    content = content[:5000] + f"\n... (以下省略、全{len(ec.text_content)}文字)"

                doc_info = f"【文書{i}: {ec.file_name}】\n"
                doc_info += f"  種別: {ec.file_type}\n"
                if ec.page_count:
                    doc_info += f"  ページ数: {ec.page_count}\n"
                doc_info += f"  内容:\n{content}"
                docs.append(doc_info)

                logger.debug(f"[A6] 文書{i}: {ec.file_name} ({len(ec.text_content)}文字)")

            return "\n\n".join(docs) if docs else "証跡文書なし"

        except ImportError:
            logger.warning("[A6] DocumentProcessor利用不可、フォールバック処理を使用")
            return self._prepare_documents_fallback(context)

    def _prepare_documents_fallback(self, context: AuditContext) -> str:
        """
        フォールバック用の文書準備

        DocumentProcessorが利用できない場合の基本的なテキスト抽出。

        Args:
            context (AuditContext): 監査コンテキスト

        Returns:
            str: フォーマット済みの文書サマリー
        """
        docs = []

        for i, ef in enumerate(context.evidence_files, 1):
            doc_info = f"【文書{i}: {ef.file_name}】\n"
            doc_info += f"  種別: {ef.mime_type}\n"

            # テキストコンテンツを抽出
            ext = ef.extension.lower()
            if ext in ['.txt', '.csv', '.json', '.xml', '.log', '.eml']:
                try:
                    content = base64.b64decode(ef.base64_content).decode('utf-8')
                    doc_info += f"  内容:\n{content[:3000]}"
                    logger.debug(f"[A6] フォールバック抽出: 文書{i} {ef.file_name}")
                except Exception as e:
                    logger.warning(f"[A6] デコードエラー: {ef.file_name} - {e}")
                    doc_info += "  内容: [デコード失敗]"
            else:
                doc_info += f"  内容: [バイナリファイル - 画像認識が必要]"

            docs.append(doc_info)

        return "\n\n".join(docs)
