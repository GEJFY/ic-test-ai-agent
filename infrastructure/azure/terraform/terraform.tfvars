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

# Function App設定
function_app_sku_name = "Y1"
function_app_sku_tier = "Dynamic"
python_version        = "3.11"

# タグ
tags = {
  Project     = "InternalControlTestAI"
  Environment = "Production"
  ManagedBy   = "Terraform"
}
