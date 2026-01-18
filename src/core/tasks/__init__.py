"""
================================================================================
tasks - 監査評価タスクモジュール（A1-A8）
================================================================================

【概要】
内部統制テスト評価のための8つの専門タスクを提供します。
各タスクは特定の評価観点に特化しており、AuditOrchestratorによって
適切なタスクが自動選択・実行されます。

【タスク一覧】
A1: SemanticSearchTask - 意味検索（証跡とテスト手続きのマッチング）
A2: ImageRecognitionTask - 画像認識（PDF/スクリーンショット解析）
A3: DataExtractionTask - データ抽出（表データの突合・照合）
A4: StepwiseReasoningTask - 段階的推論（計算検証、Chain-of-Thought）
A5: SemanticReasoningTask - 意味推論（抽象的要件の準拠性評価）
A6: MultiDocumentTask - 複数文書統合（プロセス再構成、一貫性確認）
A7: PatternAnalysisTask - パターン分析（時系列、継続性、欠落検出）
A8: SoDDetectionTask - 競合検出（職務分掌違反、SoD分析）

【使用例】
```python
from core.tasks import SemanticSearchTask, ImageRecognitionTask
from core.tasks.base_task import AuditContext

# 個別タスクを直接使用する場合
task = SemanticSearchTask(llm=llm)
result = await task.execute(context)

# 通常はAuditOrchestratorを使用（自動タスク選択）
from core.auditor_agent import AuditOrchestrator
orchestrator = AuditOrchestrator(llm=llm, vision_llm=vision_llm)
result = await orchestrator.evaluate(context)
```

【タスク選択の仕組み】
AuditOrchestratorは以下の基準でタスクを自動選択:
- 証跡ファイルの種類（PDF/画像→A2、Excel/CSV→A3）
- テスト手続きのキーワード（「計算」「再計算」→A4）
- 統制記述の内容（「職務分掌」「SoD」→A8）
- 複数ファイルの有無（複数→A6、A7を考慮）

================================================================================
"""
# 監査タスクモジュール（A1-A8）
from .a1_semantic_search import SemanticSearchTask
from .a2_image_recognition import ImageRecognitionTask
from .a3_data_extraction import DataExtractionTask
from .a4_stepwise_reasoning import StepwiseReasoningTask
from .a5_semantic_reasoning import SemanticReasoningTask
from .a6_multi_document import MultiDocumentTask
from .a7_pattern_analysis import PatternAnalysisTask
from .a8_sod_detection import SoDDetectionTask

__all__ = [
    "SemanticSearchTask",       # A1: 意味検索
    "ImageRecognitionTask",     # A2: 画像認識
    "DataExtractionTask",       # A3: データ抽出
    "StepwiseReasoningTask",    # A4: 段階的推論
    "SemanticReasoningTask",    # A5: 意味推論
    "MultiDocumentTask",        # A6: 複数文書統合
    "PatternAnalysisTask",      # A7: パターン分析
    "SoDDetectionTask",         # A8: 競合検出
]
