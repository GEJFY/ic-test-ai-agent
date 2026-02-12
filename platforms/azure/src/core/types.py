"""
================================================================================
types.py - Core Data Structures and Types
================================================================================

Defines the fundamental data structures used across the auditing system.
Moved from base_task.py to avoid circular imports and package initialization issues.
"""

"""
================================================================================
types.py - コアデータ構造と型定義
================================================================================

監査システム全体で使用される基本的なデータ構造を定義します。
循環参照とパッケージ初期化の問題を回避するため、base_task.py から移動しました。
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class TaskType(Enum):
    """
    監査タスクタイプの列挙型
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
    """
    file_name: str
    extension: str
    mime_type: str
    base64_content: str

    @classmethod
    def from_dict(cls, data: dict) -> "EvidenceFile":
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
    """
    item_id: str
    control_description: str
    test_procedure: str
    evidence_link: str
    evidence_files: List[EvidenceFile]
    additional_context: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_request(cls, item: dict) -> "AuditContext":
        evidence_files = [
            EvidenceFile.from_dict(ef)
            for ef in item.get("EvidenceFiles", [])
        ]
        item_id = item.get("ID", "unknown")
        # logger.info(f"[{item_id}] AuditContext generated: {len(evidence_files)} files")

        return cls(
            item_id=item_id,
            control_description=item.get("ControlDescription", ""),
            test_procedure=item.get("TestProcedure", ""),
            evidence_link=item.get("EvidenceLink", ""),
            evidence_files=evidence_files,
        )

@dataclass
class AuditResult:
    """
    最終監査結果
    """
    item_id: str
    evaluation_result: bool
    judgment_basis: str
    document_reference: str
    file_name: str
    evidence_files_info: List[Dict[str, str]] = field(default_factory=list)
    task_results: List[TaskResult] = field(default_factory=list)
    execution_plan: Optional[Any] = None # ExecutionPlanが他で定義されている場合の循環参照を回避
    confidence: float = 0.0
    plan_review_summary: str = ""
    judgment_review_summary: str = ""

    def to_response_dict(self, include_debug: bool = True) -> dict:
        # ExecutionPlanの定義欠落を避けるための簡易実装
        # 実際の実装ではexecution_planの型に注意が必要
        return {
            "itemId": self.item_id,
            "evaluationResult": self.evaluation_result,
            "judgmentBasis": self.judgment_basis,
            "documentReference": self.document_reference,
            "evidenceFilesInfo": self.evidence_files_info,
             # ... other fields as needed
        }
