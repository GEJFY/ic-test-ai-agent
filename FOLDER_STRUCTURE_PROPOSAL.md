# フォルダ構成改善提案

## 現状の問題点

1. **テスト構成**: ユニットテスト、統合テスト、E2Eテストがフラットに配置（23ファイル）
2. **監視機能**: Phase 3で必要な `monitoring/` ディレクトリが未作成
3. **IaC配置**: Bicep (Azure) と Terraform (AWS/GCP) の配置が不明確
4. **ドキュメント**: Phase 4で大量追加予定だがサブディレクトリ構造が未整備

---

## 提案する構成

```
ic-test-ai-agent/
├── .github/
│   ├── workflows/               # CI/CD (既存)
│   └── dependabot.yml           # 依存関係管理 (既存)
│
├── docs/                        # ドキュメント（Phase 4で拡充）
│   ├── architecture/            # アーキテクチャ設計書 (NEW)
│   │   ├── SYSTEM_ARCHITECTURE.md
│   │   ├── API_GATEWAY_DESIGN.md
│   │   └── CORRELATION_ID_DESIGN.md
│   ├── monitoring/              # 監視・ログ設計 (NEW)
│   │   ├── CORRELATION_ID.md
│   │   ├── ERROR_HANDLING.md
│   │   └── QUERY_SAMPLES.md
│   ├── operations/              # 運用ガイド (NEW)
│   │   ├── DEPLOYMENT_GUIDE.md
│   │   ├── MONITORING_RUNBOOK.md
│   │   ├── TROUBLESHOOTING.md
│   │   └── INCIDENT_RESPONSE.md
│   ├── setup/                   # セットアップガイド (NEW)
│   │   ├── AZURE_SETUP.md
│   │   ├── AWS_SETUP.md
│   │   ├── GCP_SETUP.md
│   │   └── CLIENT_SETUP.md
│   ├── security/                # セキュリティガイド (NEW)
│   │   └── SECRET_MANAGEMENT.md
│   ├── CLOUD_COST_ESTIMATION.md # コスト見積もり (既存)
│   └── README.md                # ドキュメント索引 (既存)
│
├── infrastructure/              # IaC (Infrastructure as Code) - RENAMED from terraform/
│   ├── azure/                   # Azure IaC (NEW)
│   │   ├── bicep/
│   │   │   ├── main.bicep
│   │   │   ├── apim.bicep
│   │   │   ├── function-app.bicep
│   │   │   ├── key-vault.bicep
│   │   │   ├── app-insights.bicep
│   │   │   └── parameters.json
│   │   ├── apim-policies.xml    # APIM ポリシー定義
│   │   └── README.md            # Azure Bicep使用ガイド
│   │
│   ├── aws/                     # AWS IaC (既存terraform/modules/aws → 移動)
│   │   ├── terraform/
│   │   │   ├── main.tf
│   │   │   ├── api-gateway.tf
│   │   │   ├── lambda.tf
│   │   │   ├── lambda-xray.tf
│   │   │   ├── secrets-manager.tf
│   │   │   ├── cloudwatch.tf
│   │   │   ├── variables.tf
│   │   │   ├── outputs.tf
│   │   │   └── backend.tf
│   │   └── README.md            # AWS Terraform使用ガイド
│   │
│   ├── gcp/                     # GCP IaC (既存terraform/modules/gcp → 移動)
│   │   ├── terraform/
│   │   │   ├── main.tf
│   │   │   ├── apigee.tf
│   │   │   ├── cloud-functions.tf
│   │   │   ├── secret-manager.tf
│   │   │   ├── cloud-logging.tf
│   │   │   ├── variables.tf
│   │   │   └── outputs.tf
│   │   └── README.md            # GCP Terraform使用ガイド
│   │
│   └── clients/                 # クライアント環境管理 (既存terraform/clients → 移動)
│       ├── _template/
│       └── sample-client/
│
├── platforms/                   # プラットフォーム固有コード (既存)
│   ├── azure/
│   │   └── function_app.py      # 相関ID統合済み
│   ├── aws/
│   │   └── lambda_handler.py    # 相関ID統合済み
│   ├── gcp/
│   │   └── main.py              # 相関ID統合済み
│   └── local/
│       └── main.py
│
├── scripts/                     # 運用スクリプト (Phase 5で追加)
│   ├── validate_deployment.py   # デプロイメント検証 (NEW)
│   ├── check_cost_estimates.py  # コスト見積もり整合性チェック (NEW)
│   ├── verify_documentation.py  # ドキュメント整合性検証 (NEW)
│   └── audit_security.py        # セキュリティ監査 (NEW)
│
├── src/                         # 共通ソースコード
│   ├── core/                    # ビジネスロジック
│   │   ├── __init__.py
│   │   ├── handlers.py          # 相関ID統合済み
│   │   ├── async_handlers.py
│   │   ├── correlation.py       # 相関ID管理 (Phase 1)
│   │   ├── error_handler.py     # エラーハンドリング (Phase 1)
│   │   ├── graph_orchestrator.py
│   │   ├── auditor_agent.py
│   │   ├── document_processor.py
│   │   ├── prompts.py
│   │   └── tasks/               # タスク実装
│   │       ├── base_task.py
│   │       ├── a1_semantic_search.py
│   │       └── ... (8タスク)
│   │
│   └── infrastructure/          # インフラ抽象化層
│       ├── __init__.py
│       ├── logging_config.py    # 相関ID統合済み
│       ├── llm_factory.py
│       ├── ocr_factory.py
│       │
│       ├── secrets/             # シークレット管理 (Phase 1)
│       │   ├── __init__.py
│       │   ├── secrets_provider.py
│       │   ├── azure_keyvault.py
│       │   ├── aws_secrets.py
│       │   └── gcp_secrets.py
│       │
│       ├── monitoring/          # 監視・トレーシング (Phase 3で実装) (NEW)
│       │   ├── __init__.py
│       │   ├── azure_monitor.py    # Application Insights統合
│       │   ├── aws_xray.py         # X-Ray統合
│       │   ├── gcp_monitoring.py   # Cloud Logging/Trace統合
│       │   └── metrics.py          # カスタムメトリクス
│       │
│       └── job_storage/         # ジョブストレージ
│           ├── __init__.py
│           ├── memory.py
│           ├── azure_table.py
│           ├── azure_queue.py
│           ├── azure_blob.py
│           ├── aws_dynamodb.py
│           ├── aws_sqs.py
│           ├── gcp_firestore.py
│           └── gcp_tasks.py
│
├── tests/                       # テストコード (階層化) (RESTRUCTURED)
│   ├── __init__.py
│   ├── conftest.py              # Pytest設定
│   │
│   ├── unit/                    # ユニットテスト (NEW)
│   │   ├── __init__.py
│   │   ├── test_correlation.py         # Phase 1
│   │   ├── test_error_handler.py       # Phase 1
│   │   ├── test_secrets_provider.py    # Phase 1
│   │   ├── test_handlers.py            # 既存 → 移動
│   │   ├── test_async_handlers.py      # 既存 → 移動
│   │   ├── test_prompts.py             # 既存 → 移動
│   │   ├── test_llm_factory.py         # 既存 → 移動
│   │   ├── test_ocr_factory.py         # 既存 → 移動
│   │   ├── test_document_processor.py  # 既存 → 移動
│   │   ├── test_graph_orchestrator.py  # 既存 → 移動
│   │   ├── test_base_task.py           # 既存 → 移動
│   │   └── test_tasks.py               # 既存 → 移動
│   │
│   ├── integration/             # 統合テスト (NEW)
│   │   ├── __init__.py
│   │   ├── test_secret_providers.py        # Phase 1
│   │   ├── test_monitoring_platforms.py    # Phase 3
│   │   ├── test_api_gateway_backends.py    # Phase 2
│   │   ├── test_job_storage.py             # 既存 → 移動
│   │   ├── test_job_storage_aws_gcp.py     # 既存 → 移動
│   │   ├── test_integration_local.py       # 既存 → 移動
│   │   ├── test_integration_models.py      # 既存 → 移動
│   │   └── test_integration_cloud.py       # 既存 → 移動
│   │
│   ├── e2e/                     # E2Eテスト (Phase 5で実装) (NEW)
│   │   ├── __init__.py
│   │   ├── test_azure_e2e.py           # Azure全体フロー
│   │   ├── test_aws_e2e.py             # AWS全体フロー
│   │   ├── test_gcp_e2e.py             # GCP全体フロー
│   │   ├── test_correlation_e2e.py     # 相関ID伝播
│   │   ├── test_error_scenarios.py     # エラーシナリオ
│   │   └── test_e2e.py                 # 既存 → 移動
│   │
│   ├── load/                    # 負荷テスト (Phase 5で実装) (NEW)
│   │   ├── __init__.py
│   │   ├── locustfile.py        # Locust負荷テストシナリオ
│   │   └── README.md            # 負荷テスト実行ガイド
│   │
│   └── platform/                # プラットフォーム固有テスト (NEW)
│       ├── __init__.py
│       ├── test_platform_azure.py      # 既存 → 移動
│       ├── test_platform_aws.py        # 既存 → 移動
│       ├── test_platform_gcp.py        # 既存 → 移動
│       └── test_local_platform.py      # 既存 → 移動
│
├── web/                         # Webインターフェース (既存)
│   └── ... (既存のまま)
│
├── SampleData/                  # テストデータ (既存)
│   └── ... (既存のまま)
│
├── logs/                        # ログ出力先 (既存)
│
├── .env                         # 環境変数 (ローカル開発用)
├── .env.example                 # 環境変数テンプレート
├── .gitignore
├── .pre-commit-config.yaml      # Pre-commitフック設定
├── .secrets.baseline            # Detect Secrets設定
├── pyproject.toml               # Pythonプロジェクト設定
├── requirements.txt             # 本番依存関係
├── requirements-dev.txt         # 開発依存関係
├── SYSTEM_SPECIFICATION.md      # システム仕様書
├── LICENSE                      # ライセンス
└── README.md                    # プロジェクト概要
```

---

## 主な変更点

### 1. テストディレクトリの階層化 ✨

**現状**: 23ファイルがフラット配置

```
tests/
├── test_handlers.py
├── test_integration_cloud.py
├── test_e2e.py
└── ... (20ファイル)
```

**改善後**: 目的別に4階層化

```
tests/
├── unit/               # ユニットテスト (13ファイル)
├── integration/        # 統合テスト (9ファイル)
├── e2e/                # E2Eテスト (6ファイル)
├── load/               # 負荷テスト
└── platform/           # プラットフォーム固有テスト (4ファイル)
```

**利点**:
- テストの種類が明確
- 実行時にディレクトリ単位でフィルタリング可能 (`pytest tests/unit/`)
- CI/CDで段階的にテスト実行可能

### 2. 監視機能用ディレクトリ追加 (Phase 3対応) 🔍

**新規作成**: `src/infrastructure/monitoring/`

```
src/infrastructure/monitoring/
├── __init__.py
├── azure_monitor.py      # Application Insights統合
├── aws_xray.py           # X-Ray統合
├── gcp_monitoring.py     # Cloud Logging/Trace統合
└── metrics.py            # カスタムメトリクス
```

**理由**: Phase 3で実装予定の監視機能を一元管理

### 3. IaCディレクトリの整理 (Phase 2対応) 🏗️

**現状**: `terraform/` ディレクトリのみ

**改善後**: `infrastructure/` に統一（Bicep + Terraform）

```
infrastructure/
├── azure/bicep/          # Azure (Bicep) - Phase 2で追加
├── aws/terraform/        # AWS (Terraform) - 既存を移動
└── gcp/terraform/        # GCP (Terraform) - 既存を移動
```

**理由**:
- Bicep (Azure) と Terraform (AWS/GCP) を統一ディレクトリに配置
- コードの `src/infrastructure/` との混同を避けるため、プロジェクトルートに配置

### 4. ドキュメント構造の整備 (Phase 4対応) 📚

**現状**: `docs/` に3ファイルのみ

**改善後**: 5カテゴリに分類

```
docs/
├── architecture/         # アーキテクチャ設計書
├── monitoring/          # 監視・ログ設計
├── operations/          # 運用ガイド
├── setup/               # セットアップガイド
└── security/            # セキュリティガイド
```

**理由**: Phase 4で追加予定の15+ドキュメントを整理

### 5. 運用スクリプト追加 (Phase 5対応) 🔧

**新規作成**: `scripts/` ディレクトリ

```
scripts/
├── validate_deployment.py     # デプロイメント検証
├── check_cost_estimates.py    # コスト見積もり整合性チェック
├── verify_documentation.py    # ドキュメント整合性検証
└── audit_security.py          # セキュリティ監査
```

**理由**: Phase 5の整合性検証タスクをスクリプト化

---

## 移行手順

### ステップ1: 新しいディレクトリ作成

```bash
# 監視機能ディレクトリ (Phase 3対応)
mkdir -p src/infrastructure/monitoring

# テストディレクトリ階層化
mkdir -p tests/unit tests/integration tests/e2e tests/load tests/platform

# ドキュメント構造整備 (Phase 4対応)
mkdir -p docs/architecture docs/monitoring docs/operations docs/setup docs/security

# IaCディレクトリ整理 (Phase 2対応)
mkdir -p infrastructure/azure/bicep

# 運用スクリプト (Phase 5対応)
mkdir -p scripts
```

### ステップ2: 既存テストファイルの移動

```bash
# ユニットテストの移動
mv tests/test_handlers.py tests/unit/
mv tests/test_async_handlers.py tests/unit/
mv tests/test_prompts.py tests/unit/
mv tests/test_llm_factory.py tests/unit/
mv tests/test_ocr_factory.py tests/unit/
mv tests/test_document_processor.py tests/unit/
mv tests/test_graph_orchestrator.py tests/unit/
mv tests/test_base_task.py tests/unit/
mv tests/test_tasks.py tests/unit/
mv tests/test_tasks_execute.py tests/unit/

# Phase 1で追加したユニットテストも移動
mv tests/test_correlation.py tests/unit/
mv tests/test_error_handler.py tests/unit/
mv tests/test_secrets_provider.py tests/unit/

# 統合テストの移動
mv tests/test_job_storage.py tests/integration/
mv tests/test_job_storage_aws_gcp.py tests/integration/
mv tests/test_integration_local.py tests/integration/
mv tests/test_integration_models.py tests/integration/
mv tests/test_integration_cloud.py tests/integration/

# E2Eテストの移動
mv tests/test_e2e.py tests/e2e/

# プラットフォーム固有テストの移動
mv tests/test_platform_azure.py tests/platform/
mv tests/test_platform_aws.py tests/platform/
mv tests/test_platform_gcp.py tests/platform/
mv tests/test_local_platform.py tests/platform/
```

### ステップ3: IaCディレクトリの整理

```bash
# 既存terraformディレクトリの移動
mv terraform infrastructure/
mv infrastructure/terraform/modules/aws infrastructure/aws/terraform
mv infrastructure/terraform/modules/gcp infrastructure/gcp/terraform
mv infrastructure/terraform/modules infrastructure/_old_modules  # バックアップ
```

### ステップ4: __init__.py ファイルの追加

```bash
# テストディレクトリに __init__.py 追加
touch tests/unit/__init__.py
touch tests/integration/__init__.py
touch tests/e2e/__init__.py
touch tests/load/__init__.py
touch tests/platform/__init__.py

# 監視ディレクトリに __init__.py 追加
touch src/infrastructure/monitoring/__init__.py
```

---

## 移行後の利点

### 1. テスト実行の柔軟性

```bash
# ユニットテストのみ実行（高速）
pytest tests/unit/ -v

# 統合テストのみ実行
pytest tests/integration/ -v

# E2Eテストのみ実行（時間がかかる）
pytest tests/e2e/ -v

# 特定プラットフォームのみテスト
pytest tests/platform/test_platform_azure.py -v

# 負荷テスト実行
locust -f tests/load/locustfile.py
```

### 2. CI/CD パイプライン最適化

```yaml
# .github/workflows/ci.yml 例
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - name: Run Unit Tests
        run: pytest tests/unit/ --cov=src --cov-report=xml

  integration-tests:
    runs-on: ubuntu-latest
    needs: unit-tests
    steps:
      - name: Run Integration Tests
        run: pytest tests/integration/ -v

  e2e-tests:
    runs-on: ubuntu-latest
    needs: integration-tests
    steps:
      - name: Run E2E Tests
        run: pytest tests/e2e/ -v --maxfail=1
```

### 3. 開発者体験の向上

- **明確な責任分離**: 各ディレクトリの役割が明確
- **ドキュメント発見性**: カテゴリ別に整理されたドキュメント
- **IaC管理**: プラットフォーム別に分離されたインフラコード
- **スケーラビリティ**: 将来的な機能追加に対応しやすい構造

---

## Phase 2-5 での活用

### Phase 2: API Gateway層統合
- `infrastructure/azure/bicep/apim.bicep` に APIM 定義を追加
- `docs/architecture/API_GATEWAY_DESIGN.md` に設計書を追加

### Phase 3: 監視最適化
- `src/infrastructure/monitoring/` に監視機能を実装
- `tests/integration/test_monitoring_platforms.py` にテストを追加
- `docs/monitoring/` にクエリサンプルを追加

### Phase 4: ドキュメント整備
- `docs/operations/` に運用ガイドを追加
- `docs/setup/` にセットアップガイドを追加
- `infrastructure/*/README.md` に IaC 使用ガイドを追加

### Phase 5: テスト・検証
- `tests/e2e/` に包括的E2Eテストを追加
- `tests/load/` に負荷テストを追加
- `scripts/` に整合性検証スクリプトを追加

---

## 互換性の維持

### Pytest設定の更新

`pyproject.toml` または `pytest.ini` を更新:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]

# テストディレクトリのパス設定
pythonpath = [".", "src"]

# カバレッジ設定
addopts = "--cov=src --cov-report=html --cov-report=term-missing"
```

### インポートの調整

テストファイルのインポートパスは変更不要:

```python
# tests/unit/test_handlers.py
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))

from core.handlers import handle_evaluate
```

---

## まとめ

この改善により、Phase 2-5 の実装がスムーズになり、プロジェクトの保守性・スケーラビリティが大幅に向上します。

**即座に実施すべき項目**:
1. ✅ テストディレクトリの階層化（ステップ1-2）
2. ✅ 監視機能ディレクトリの作成（Phase 3準備）
3. ✅ ドキュメント構造の整備（Phase 4準備）

**Phase 2以降で実施**:
4. IaCディレクトリの整理（Phase 2で Bicep 追加時）
5. 運用スクリプトの追加（Phase 5で実装）
