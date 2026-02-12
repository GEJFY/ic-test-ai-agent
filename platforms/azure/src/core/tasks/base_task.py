"""
================================================================================
base_task.py - 監査タスクの基底クラス
================================================================================

【概要】
全ての監査タスク（A1〜A8）の共通基底クラスを定義します。
このモジュールは内部統制テスト評価AIシステムのコア部分です。

【含まれるクラス】
- TaskType: タスクタイプの列挙型（A1〜A8）
- TaskResult: タスク実行結果を格納するデータクラス
- EvidenceFile: 証跡ファイル情報を格納するデータクラス
- AuditContext: 監査コンテキスト（統制情報・テスト手続き・証跡）
- BaseAuditTask: 全タスクの抽象基底クラス

【タスクタイプ一覧】
A1: 意味検索（セマンティックサーチ）
A2: 画像認識 + 情報抽出
A3: 構造化データ抽出
A4: 段階的推論 + 計算
A5: 意味検索 + 推論
A6: 複数文書統合理解
A7: パターン分析（時系列）
A8: SoD検出（職務分掌）

【使用例】
```python
from core.tasks.base_task import BaseAuditTask, TaskType, AuditContext

# コンテキストの作成
context = AuditContext.from_request(request_item)

# タスクの実行（各タスククラスで実装）
result = await task.execute(context)
```

================================================================================
"""
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging

# Import core types from the new module to avoid circular dependencies
from core.types import TaskType, TaskResult, EvidenceFile, AuditContext

# ロガーの設定（モジュール名でログを識別）
logger = logging.getLogger(__name__)


class BaseAuditTask(ABC):
    """
    監査タスクの抽象基底クラス

    全ての監査タスク（A1〜A8）はこのクラスを継承して実装します。
    共通のインターフェースを提供し、タスクの一貫性を保証します。

    Attributes:
        task_type (TaskType): タスクタイプ（サブクラスで定義）
        task_name (str): タスクの日本語名（サブクラスで定義）
        description (str): タスクの説明（サブクラスで定義）
        llm: LangChain の ChatModel インスタンス

    Abstract Methods:
        execute(context): タスクを実行し結果を返す

    Example:
        >>> class MyTask(BaseAuditTask):
        ...     task_type = TaskType.A1_SEMANTIC_SEARCH
        ...     task_name = "意味検索"
        ...     description = "証跡からキーワードを検索"
        ...
        ...     async def execute(self, context):
        ...         # タスク固有の処理
        ...         return self._create_result(...)

    Note:
        - LLM は初期化時に注入されます（依存性注入パターン）
        - execute() は非同期メソッドです（async/await）
    """

    # サブクラスで必ず定義するクラス属性
    task_type: TaskType  # タスクタイプ（例: TaskType.A1_SEMANTIC_SEARCH）
    task_name: str       # 日本語名（例: "意味検索"）
    description: str     # 説明文（例: "キーワードに頼らない意味的検索"）

    def __init__(self, llm=None):
        """
        タスクを初期化

        Args:
            llm: LangChain の ChatModel インスタンス
                 （例: ChatOpenAI, AzureChatOpenAI）
                 None の場合、LLM を使用しない簡易処理になります

        Note:
            LLM は AuditorOrchestrator から注入されます。
            テスト時は None を渡してモック動作が可能です。
        """
        self.llm = llm

        # タスク初期化のログ
        if hasattr(self, 'task_name'):
            logger.debug(f"タスク '{self.task_name}' を初期化しました "
                        f"(LLM: {'設定済み' if llm else '未設定'})")

    @abstractmethod
    async def execute(self, context: AuditContext) -> TaskResult:
        """
        監査タスクを実行（サブクラスで実装必須）

        各タスクタイプ固有のロジックをここに実装します。
        非同期処理により、複数のLLM呼び出しを効率的に行えます。

        Args:
            context (AuditContext): 監査コンテキスト
                - 統制記述
                - テスト手続き
                - 証跡ファイル

        Returns:
            TaskResult: タスクの実行結果
                - success: 成功/失敗
                - reasoning: 判断理由
                - confidence: 信頼度
                - evidence_references: 参照した証跡

        Raises:
            Exception: LLM呼び出しエラー、ファイル処理エラーなど

        Note:
            エラーが発生した場合は、success=False の TaskResult を
            返すことを推奨します（例外を投げるより安全）。
        """
        pass

    def get_task_info(self) -> dict:
        """
        タスクのメタ情報を取得

        プランナーがタスクを選択する際に使用します。

        Returns:
            dict: タスク情報
                - type: タスクタイプ（"A1"等）
                - name: 日本語名
                - description: 説明文
        """
        return {
            "type": self.task_type.value,
            "name": self.task_name,
            "description": self.description,
        }

    def _create_result(
        self,
        success: bool,
        result: Any,
        reasoning: str,
        confidence: float = 0.0,
        evidence_refs: Optional[List[str]] = None,
    ) -> TaskResult:
        """
        TaskResult を生成するヘルパーメソッド

        サブクラスで結果を返す際に使用します。
        必要な属性を自動的に設定します。

        Args:
            success (bool): タスクの成功/失敗
            result (Any): タスク固有の詳細結果
            reasoning (str): 判断理由（日本語）
            confidence (float): 信頼度（0.0〜1.0）
            evidence_refs (List[str]): 参照した証跡の一覧

        Returns:
            TaskResult: 生成されたタスク結果

        Example:
            >>> return self._create_result(
            ...     success=True,
            ...     result={"matches": found_items},
            ...     reasoning="3件の関連記述を発見しました",
            ...     confidence=0.85,
            ...     evidence_refs=["report.pdf"]
            ... )
        """
        # 結果生成のログ
        status = "成功" if success else "要確認"
        logger.info(f"[{self.task_type.value}:{self.task_name}] "
                   f"結果: {status} (信頼度: {confidence:.2f})")

        return TaskResult(
            task_type=self.task_type,
            task_name=self.task_name,
            success=success,
            result=result,
            reasoning=reasoning,
            confidence=confidence,
            evidence_references=evidence_refs or [],
        )
