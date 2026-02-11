# ==============================================================================
# apigee.tf - GCP Apigee リソース定義
# ==============================================================================
#
# 【概要】
# 内部統制テスト評価AIのAPI Gateway層（Apigee）を構築します。
#
# 【注意】
# Apigeeは高コストです（月額$4.50～）。
# 評価版期間外は課金されるため、enable_apigee = false で無効化できます。
#
# 【代替案】
# Apigee不使用の場合、Cloud Functionsに直接アクセスします。
# その場合、相関ID管理・レート制限はCloud Functions内で実装します。
#
# 【機能】
# - API Key認証
# - レート制限
# - 相関ID管理（X-Correlation-IDヘッダー）
# - Cloud Logging統合
# - Cloud Functionsへのルーティング
#
# ==============================================================================

# ------------------------------------------------------------------------------
# Apigee組織（有効な場合のみ作成）
# ------------------------------------------------------------------------------

# Note: Apigee組織は手動で作成する必要があります。
# gcloud apigee organizations provision \
#   --project=<PROJECT_ID> \
#   --authorized-network=default \
#   --runtime-location=asia-northeast1

# データソース: 既存Apigee組織
data "google_apigee_organization" "org" {
  count = var.enable_apigee ? 1 : 0
  org_id = var.apigee_organization_name != "" ? var.apigee_organization_name : var.project_id
}

# ------------------------------------------------------------------------------
# Apigee環境
# ------------------------------------------------------------------------------

resource "google_apigee_environment" "prod" {
  count       = var.enable_apigee ? 1 : 0
  org_id      = data.google_apigee_organization.org[0].name
  name        = var.apigee_environment_name
  description = "Production environment for ${var.project_name}"
  display_name = "${var.project_name}-${var.environment}"
}

# ------------------------------------------------------------------------------
# Apigee環境グループ
# ------------------------------------------------------------------------------

resource "google_apigee_envgroup" "prod" {
  count     = var.enable_apigee ? 1 : 0
  org_id    = data.google_apigee_organization.org[0].name
  name      = "${var.project_name}-${var.environment}-group"
  hostnames = ["${var.project_name}-api.example.com"]  # 実際のドメインに変更
}

resource "google_apigee_envgroup_attachment" "prod" {
  count       = var.enable_apigee ? 1 : 0
  envgroup_id = google_apigee_envgroup.prod[0].id
  environment = google_apigee_environment.prod[0].name
}

# ------------------------------------------------------------------------------
# Apigee APIプロキシ（Cloud Functions統合）
# ------------------------------------------------------------------------------

# Note: Apigee APIプロキシはXML/YAMLで定義し、手動またはCI/CDでデプロイします。
# Terraform管理外とするか、google_apigee_sharedflow リソースで管理します。

# サンプルプロキシ構成:
# - ベースパス: /api
# - ターゲット: Cloud Functions URI
# - ポリシー:
#   1. VerifyAPIKey（API Key検証）
#   2. AssignMessage（相関ID設定）
#   3. Quota（レート制限）
#   4. MessageLogging（Cloud Logging）

# ------------------------------------------------------------------------------
# Apigee API製品
# ------------------------------------------------------------------------------

resource "google_apigee_product" "ic_test_ai" {
  count        = var.enable_apigee ? 1 : 0
  org_id       = data.google_apigee_organization.org[0].name
  name         = "${var.project_name}-${var.environment}-product"
  display_name = "IC Test AI Product"
  description  = "内部統制テスト評価AI API Product"

  approval_type = "auto"

  environments = [
    google_apigee_environment.prod[0].name
  ]

  # APIプロキシのベースパス
  api_resources = [
    "/**"
  ]

  # レート制限
  quota = "100"
  quota_interval = "1"
  quota_time_unit = "minute"

  # アクセススコープ
  scopes = [
    "read",
    "write"
  ]
}

# ------------------------------------------------------------------------------
# Apigee開発者アプリ（API Key発行）
# ------------------------------------------------------------------------------

resource "google_apigee_developer" "default" {
  count      = var.enable_apigee ? 1 : 0
  org_id     = data.google_apigee_organization.org[0].name
  email      = "developer@example.com"  # 実際のメールアドレスに変更
  first_name = "IC Test AI"
  last_name  = "Developer"
  user_name  = "ic-test-ai-developer"
}

resource "google_apigee_developer_app" "ic_test_ai" {
  count        = var.enable_apigee ? 1 : 0
  org_id       = data.google_apigee_organization.org[0].name
  developer_id = google_apigee_developer.default[0].email
  name         = "${var.project_name}-${var.environment}-app"
  api_products = [google_apigee_product.ic_test_ai[0].name]
}

# ------------------------------------------------------------------------------
# 代替: Cloud Load Balancingベースのエンドポイント（Apigee不使用時）
# ------------------------------------------------------------------------------

# Apigeeが無効な場合、Cloud Functionsに直接アクセス可能にする
# または、Cloud Armor + Cloud Load Balancerでレート制限を実装

# ------------------------------------------------------------------------------
# 出力
# ------------------------------------------------------------------------------

output "apigee_enabled" {
  description = "Apigeeが有効かどうか"
  value       = var.enable_apigee
}

output "apigee_environment_name" {
  description = "Apigee環境名"
  value       = var.enable_apigee ? google_apigee_environment.prod[0].name : "N/A (Apigee disabled)"
}

output "apigee_api_endpoint" {
  description = "ApigeeエンドポイントURL（カスタムドメイン設定後）"
  value       = var.enable_apigee ? "https://${google_apigee_envgroup.prod[0].hostnames[0]}/api/evaluate" : "N/A (Apigee disabled - use Cloud Functions URI directly)"
}

output "cloud_functions_direct_url" {
  description = "Cloud Functions直接URL（Apigee不使用時）"
  value       = "${google_cloudfunctions2_function.evaluate.service_config[0].uri}/evaluate"
}
