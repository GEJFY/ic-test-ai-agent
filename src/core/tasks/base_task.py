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
from dataclasses import dataclass, field
from enum import Enum
import logging

# ロガーの設定（モジュール名でログを識別）
logger = logging.getLogger(__name__)


class TaskType(Enum):
    """
    監査タスクタイプの列挙型

    各タスクタイプは内部統制テストで必要な特定の検証能力を表します。
    プランナーがテスト手続きを分析し、適切なタスクを選択します。

    Attributes:
        A1_SEMANTIC_SEARCH: 意味検索 - キーワードに頼らない意味的な文書検索
        A2_IMAGE_RECOGNITION: 画像認識 - 承認印・署名・日付の抽出
        A3_DATA_EXTRACTION: データ抽出 - 表からの数値抽出と突合
        A4_STEPWISE_REASONING: 段階的推論 - 複雑な計算の検証
        A5_SEMANTIC_REASONING: 意味推論 - 規程要件との整合性判定
        A6_MULTI_DOCUMENT: 複数文書統合 - 複数証跡からプロセス再構成
        A7_PATTERN_ANALYSIS: パターン分析 - 継続性・記録欠落の検出
        A8_SOD_DETECTION: SoD検出 - 職務分掌違反の検出
    """
    A1_SEMANTIC_SEARCH = "A1"
    A2_IMAGE_RECOGNITION = "A2"
    A3_DATA_EXTRACTION = "A3"
    A4_STEPWISE_REASONING = "A4"
    A5_SEMANTIC_REASONING = "A5"
    A6_MULTI_DOCUMENT = "A6"
    A7_PATTERN_ANALYSIS = "A7"
    A8_SOD_DETECTION = "A8"


@dataclass
class TaskResult:
    """
    監査タスクの実行結果を格納するデータクラス

    各タスクの実行後、この形式で結果が返されます。
    最終的な判断根拠の生成に使用されます。

    Attributes:
        task_type (TaskType): 実行したタスクのタイプ
        task_name (str): タスクの日本語名（例: "意味検索"）
        success (bool): タスクの成功/失敗
        result (Any): タスク固有の詳細結果（JSON形式のデータ）
        reasoning (str): タスクの判断理由（日本語）
        confidence (float): 信頼度スコア（0.0〜1.0）
        evidence_references (List[str]): 参照した証跡の一覧
        sub_results (List[TaskResult]): サブタスクの結果（複合タスク用）

    Example:
        >>> result = TaskResult(
        ...     task_type=TaskType.A1_SEMANTIC_SEARCH,
        ...     task_name="意味検索",
        ...     success=True,
        ...     result={"found_matches": [...]},
        ...     reasoning="統制記述に関連する記載を証跡から発見",
        ...     confidence=0.85,
        ...     evidence_references=["監査報告書.pdf"]
        ... )
    """
    task_type: TaskType
    task_name: str
    success: bool
    result: Any
    reasoning: str
    confidence: float = 0.0
    evidence_references: List[str] = field(default_factory=list)
    sub_results: List["TaskResult"] = field(default_factory=list)

    def to_dict(self) -> dict:
        """
        JSON シリアライズ用に辞書形式に変換

        API レスポンスやデバッグ出力で使用します。

        Returns:
            dict: タスク結果の辞書表現
        """
        return {
            "taskType": self.task_type.value,
            "taskName": self.task_name,
            "success": self.success,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "evidenceReferences": self.evidence_references,
        }


@dataclass
class EvidenceFile:
    """
    証跡ファイルのデータ構造

    Excel マクロから送信される証跡ファイルの情報を格納します。
    ファイル内容は Base64 エンコードされた状態で受け取ります。

    Attributes:
        file_name (str): ファイル名（例: "承認書_2025年度.pdf"）
        extension (str): 拡張子（例: ".pdf"）
        mime_type (str): MIME タイプ（例: "application/pdf"）
        base64_content (str): Base64 エンコードされたファイル内容

    Note:
        ファイルサイズが大きい場合、base64_content も大きくなります。
        DocumentProcessor でテキスト抽出後、元データは破棄可能です。
    """
    file_name: str
    extension: str
    mime_type: str
    base64_content: str

    @classmethod
    def from_dict(cls, data: dict) -> "EvidenceFile":
        """
        API リクエストの辞書から EvidenceFile インスタンスを生成

        Excel マクロから送信されるJSONフォーマットに対応しています。

        Args:
            data (dict): 証跡ファイルの辞書データ
                - fileName: ファイル名
                - extension: 拡張子
                - mimeType: MIME タイプ
                - base64: Base64 エンコードされた内容

        Returns:
            EvidenceFile: 生成されたインスタンス

        Example:
            >>> data = {
            ...     "fileName": "report.pdf",
            ...     "extension": ".pdf",
            ...     "mimeType": "application/pdf",
            ...     "base64": "JVBERi0xLj..."
            ... }
            >>> ef = EvidenceFile.from_dict(data)
        """
        return cls(
            file_name=data.get("fileName", ""),
            extension=data.get("extension", ""),
            mime_type=data.get("mimeType", ""),
            base64_content=data.get("base64", ""),
        )


@dataclass
class AuditContext:
    """
    監査タスク実行のコンテキスト情報

    1つの内部統制テスト項目に対する全ての情報を保持します。
    各タスクはこのコンテキストを受け取って処理を実行します。

    Attributes:
        item_id (str): テスト項目ID（例: "CLC-01"）
        control_description (str): 統制記述（何を統制しているか）
        test_procedure (str): テスト手続き（何を確認するか）
        evidence_link (str): 証跡フォルダのパス（元のExcel上のパス）
        evidence_files (List[EvidenceFile]): 証跡ファイルのリスト
        additional_context (Dict): 追加のコンテキスト情報（将来拡張用）

    Note:
        - control_description: 「月次で売上の承認が行われている」等
        - test_procedure: 「承認印があることを確認する」等
        - evidence_files: PDF/Excel等の証跡ファイル
    """
    item_id: str
    control_description: str
    test_procedure: str
    evidence_link: str
    evidence_files: List[EvidenceFile]
    additional_context: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_request(cls, item: dict) -> "AuditContext":
        """
        API リクエストの辞書から AuditContext インスタンスを生成

        Excel マクロから送信されるJSONフォーマットを解析します。

        Args:
            item (dict): テスト項目の辞書データ
                - ID: テスト項目ID
                - ControlDescription: 統制記述
                - TestProcedure: テスト手続き
                - EvidenceLink: 証跡フォルダパス
                - EvidenceFiles: 証跡ファイルの配列

        Returns:
            AuditContext: 生成されたコンテキスト

        Example:
            >>> item = {
            ...     "ID": "CLC-01",
            ...     "ControlDescription": "月次売上承認",
            ...     "TestProcedure": "承認印を確認",
            ...     "EvidenceFiles": [...]
            ... }
            >>> context = AuditContext.from_request(item)
        """
        # 証跡ファイルをEvidenceFileオブジェクトに変換
        evidence_files = [
            EvidenceFile.from_dict(ef)
            for ef in item.get("EvidenceFiles", [])
        ]

        # ログ出力（デバッグ用）
        item_id = item.get("ID", "unknown")
        logger.info(f"[{item_id}] AuditContext を生成: "
                    f"証跡ファイル数={len(evidence_files)}")

        return cls(
            item_id=item_id,
            control_description=item.get("ControlDescription", ""),
            test_procedure=item.get("TestProcedure", ""),
            evidence_link=item.get("EvidenceLink", ""),
            evidence_files=evidence_files,
        )


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
                 （例: AzureChatOpenAI (Azure AI Foundry)）
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
