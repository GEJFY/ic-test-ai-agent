# ==============================================================================
# terraform.tfvars - パラメータ値
# ==============================================================================

project_name        = "ic-test-ai"
environment         = "prod"
location            = "japaneast"
resource_group_name = "rg-ic-test-evaluation"

# APIM設定
apim_publisher_email = "admin@example.com"
apim_publisher_name  = "Internal Control Test AI"
apim_sku_name        = "Consumption"
apim_sku_capacity    = 0

# Container Apps設定
container_app_cpu          = 0.5
container_app_memory       = "1Gi"
container_app_min_replicas = 1
container_app_max_replicas = 5
container_image_tag        = "latest"

# Azure AI Foundry設定
azure_foundry_capacity = 30  # 30K TPM（1だと429レート制限が頻発）

# タグ
tags = {
  Project     = "InternalControlTestAI"
  Environment = "Production"
  ManagedBy   = "Terraform"
}
