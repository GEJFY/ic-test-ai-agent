"""
================================================================================
core - 内部統制テスト評価AIコアモジュール
================================================================================

【概要】
内部統制テスト評価AIシステムの中核となるモジュール群です。
監査評価のオーケストレーション、ドキュメント処理、各種タスクを提供します。

【モジュール構成】
- auditor_agent: 監査評価オーケストレーター（複数タスクの統合実行）
- document_processor: ドキュメント処理（PDF/Excel/画像のテキスト抽出）
- tasks/: 各種監査評価タスク（A1-A8）

【使用例】
```python
from core.auditor_agent import AuditOrchestrator
from core.document_processor import DocumentProcessor
from core.tasks.base_task import AuditContext

# オーケストレーターを作成
orchestrator = AuditOrchestrator(llm=llm, vision_llm=vision_llm)

# コンテキストを作成
context = AuditContext.from_request(request_data)

# 評価を実行
result = await orchestrator.evaluate(context)
```

================================================================================
"""
# Core module for Audit AI Agent
