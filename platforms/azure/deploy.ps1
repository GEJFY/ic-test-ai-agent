# deploy.ps1
# Azure Container Apps デプロイスクリプト
#
# 使用方法:
#   .\deploy.ps1 -ContainerAppName "ic-test-ai-prod-app" -ResourceGroup "rg-ic-test" -AcrName "ictestai"
#
# 事前準備:
#   1. Azure CLI をインストール: https://docs.microsoft.com/ja-jp/cli/azure/install-azure-cli
#   2. ログイン: az login
#   3. サブスクリプション設定: az account set --subscription "Your Subscription"
#   4. Docker Desktop が起動していること
#
param(
    [Parameter(Mandatory=$true)]
    [string]$ContainerAppName,

    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory=$true)]
    [string]$AcrName,

    [Parameter(Mandatory=$false)]
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

# ==============================================================================
# 設定
# ==============================================================================
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$ImageName = "ic-test-ai-agent"
$FullImageName = "${AcrName}.azurecr.io/${ImageName}:${ImageTag}"

Write-Host "=============================================="
Write-Host "Azure Container Apps デプロイスクリプト"
Write-Host "=============================================="
Write-Host "Container App: $ContainerAppName"
Write-Host "Resource Group: $ResourceGroup"
Write-Host "ACR: $AcrName"
Write-Host "Image: $FullImageName"
Write-Host "Project Root: $ProjectRoot"
Write-Host ""

# ==============================================================================
# 1. Azure CLI 確認
# ==============================================================================
Write-Host "[1/4] Azure CLI を確認中..."
try {
    $azVersion = az version | ConvertFrom-Json
    Write-Host "      Azure CLI: $($azVersion.'azure-cli')"
}
catch {
    Write-Error "Azure CLI がインストールされていません。https://docs.microsoft.com/ja-jp/cli/azure/install-azure-cli"
    exit 1
}

# ログイン状態確認
try {
    $account = az account show | ConvertFrom-Json
    Write-Host "      サブスクリプション: $($account.name)"
}
catch {
    Write-Error "Azure にログインしていません。'az login' を実行してください。"
    exit 1
}

# ==============================================================================
# 2. Dockerイメージのビルドとプッシュ
# ==============================================================================
Write-Host "[2/4] Dockerイメージをビルド中..."

Push-Location $ProjectRoot

# ACRにログイン
az acr login --name $AcrName
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Error "ACRへのログインに失敗しました。"
    exit 1
}

# Dockerイメージをビルド
docker build -t $FullImageName .
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Error "Dockerイメージのビルドに失敗しました。"
    exit 1
}

# latestタグも付与
docker tag $FullImageName "${AcrName}.azurecr.io/${ImageName}:latest"

Write-Host "      ビルド完了"

# ==============================================================================
# 3. ACRにプッシュ
# ==============================================================================
Write-Host "[3/4] ACRにプッシュ中..."

docker push $FullImageName
docker push "${AcrName}.azurecr.io/${ImageName}:latest"

if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Error "ACRへのプッシュに失敗しました。"
    exit 1
}

Pop-Location
Write-Host "      プッシュ完了"

# ==============================================================================
# 4. Container Appsにデプロイ
# ==============================================================================
Write-Host "[4/4] Container Apps にデプロイ中..."

az containerapp update `
    --name $ContainerAppName `
    --resource-group $ResourceGroup `
    --image $FullImageName

if ($LASTEXITCODE -ne 0) {
    Write-Error "Container Apps へのデプロイに失敗しました。"
    exit 1
}

Write-Host "      デプロイ完了!"

# ==============================================================================
# 完了メッセージ
# ==============================================================================
Write-Host ""
Write-Host "=============================================="
Write-Host "デプロイ完了!"
Write-Host "=============================================="
Write-Host ""

# Container AppのFQDN取得
$fqdn = az containerapp show --name $ContainerAppName --resource-group $ResourceGroup --query "properties.configuration.ingress.fqdn" -o tsv 2>$null
if ($fqdn) {
    Write-Host "エンドポイント:"
    Write-Host "  Health:   https://$fqdn/health"
    Write-Host "  Evaluate: https://$fqdn/evaluate"
    Write-Host ""
}

Write-Host "次のステップ:"
Write-Host "  1. Azure Portal で Container App のログを確認"
Write-Host "  2. ヘルスチェックで動作確認"
Write-Host "  3. Excel から動作確認"
Write-Host ""
