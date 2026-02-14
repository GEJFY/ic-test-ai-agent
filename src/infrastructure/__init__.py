"""
================================================================================
infrastructure - インフラストラクチャ層モジュール
================================================================================

【概要】
LLMプロバイダーやクラウドサービスとの連携を担当するモジュール群です。
環境変数に基づいて適切なプロバイダーを自動選択します。

【モジュール構成】
- llm_factory: LLMインスタンス生成ファクトリー
  - Azure AI Foundry（推奨）
  - Azure OpenAI Service（レガシー）
  - Google Cloud Vertex AI (Gemini)
  - Amazon Bedrock (Claude)

【使用例】
```python
from infrastructure import LLMFactory

# テキスト処理用LLMを作成
llm = LLMFactory.create_chat_model(temperature=0.0)

# 画像認識用LLMを作成
vision_llm = LLMFactory.create_vision_model()

# 設定状態を確認
status = LLMFactory.get_config_status()
```

================================================================================
"""
from .llm_factory import LLMFactory

__all__ = ["LLMFactory"]
