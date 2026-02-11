# Azure環境セットアップガイド

## 前提条件

- Azureサブスクリプション
- Azure CLI インストール済み
- 権限: Contributor以上

## セットアップ手順

### 1. Azure CLIログイン

```bash
az login
az account set --subscription <SUBSCRIPTION_ID>
```

### 2. リソースグループ作成

```bash
az group create --name ic-test-rg --location japaneast
```

### 3. Azure AI Foundryデプロイ

```bash
# Azure OpenAI リソース作成
az cognitiveservices account create \
  --name ic-test-openai \
  --resource-group ic-test-rg \
  --kind OpenAI \
  --sku S0 \
  --location japaneast

# GPT-4oモデルデプロイ
az cognitiveservices account deployment create \
  --name ic-test-openai \
  --resource-group ic-test-rg \
  --deployment-name gpt-4o \
  --model-name gpt-4o \
  --model-version "2024-08-06" \
  --model-format OpenAI \
  --sku-capacity 10 \
  --sku-name "Standard"
```

### 4. Document Intelligence作成

```bash
az cognitiveservices account create \
  --name ic-test-doc-intel \
  --resource-group ic-test-rg \
  --kind FormRecognizer \
  --sku S0 \
  --location japaneast
```

### 5. Bicepデプロイ

```bash
cd infrastructure/azure/bicep
az deployment group create \
  --resource-group ic-test-rg \
  --template-file main.bicep \
  --parameters @parameters.json
```

### 6. Key Vaultシークレット設定

```bash
VAULT_NAME=$(az keyvault list --resource-group ic-test-rg --query "[0].name" -o tsv)

# Azure Foundry API Key
FOUNDRY_KEY=$(az cognitiveservices account keys list \
  --name ic-test-openai --resource-group ic-test-rg \
  --query "key1" -o tsv)

az keyvault secret set \
  --vault-name $VAULT_NAME \
  --name "azure-foundry-api-key" \
  --value "$FOUNDRY_KEY"

# Document Intelligence API Key
DOC_INTEL_KEY=$(az cognitiveservices account keys list \
  --name ic-test-doc-intel --resource-group ic-test-rg \
  --query "key1" -o tsv)

az keyvault secret set \
  --vault-name $VAULT_NAME \
  --name "document-intelligence-key" \
  --value "$DOC_INTEL_KEY"
```

### 7. APIM設定確認

```bash
# APIM Subscription Key取得
az apim subscription list \
  --resource-group ic-test-rg \
  --service-name <APIM_NAME>
```

### 8. デプロイ検証

```bash
python scripts/validate_deployment.py --platform azure
```

## 環境変数設定（クライアント用）

```bash
export AZURE_APIM_ENDPOINT="https://<APIM_NAME>.azure-api.net"
export AZURE_APIM_SUBSCRIPTION_KEY="<SUBSCRIPTION_KEY>"
export APPLICATIONINSIGHTS_CONNECTION_STRING="<CONNECTION_STRING>"
export KEY_VAULT_NAME="<VAULT_NAME>"
```

## 参考資料

- [Deployment Guide](../operations/DEPLOYMENT_GUIDE.md)
- [Azure Bicep Documentation](https://docs.microsoft.com/azure/azure-resource-manager/bicep/)
