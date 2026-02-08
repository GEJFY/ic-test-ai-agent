<#
.SYNOPSIS
    クライアント環境へのデプロイを実行します。

.DESCRIPTION
    このスクリプトは以下を実行します:
    1. Dockerイメージのビルド
    2. Terraform によるインフラ構築（オプション）
    3. アプリケーションのデプロイ

.PARAMETER ClientName
    クライアント名（terraform/clients/<ClientName>）

.PARAMETER CloudProvider
    クラウドプロバイダー (azure, aws, gcp)

.PARAMETER SkipInfra
    インフラ構築をスキップ

.PARAMETER SkipApp
    アプリケーションデプロイをスキップ

.EXAMPLE
    .\deploy-client.ps1 -ClientName "sample-client" -CloudProvider "azure"

.EXAMPLE
    .\deploy-client.ps1 -ClientName "company-a" -CloudProvider "aws" -SkipInfra
#>

param(
    [Parameter(Mandatory=$true)]
    [string]$ClientName,

    [Parameter(Mandatory=$true)]
    [ValidateSet("azure", "aws", "gcp")]
    [string]$CloudProvider,

    [switch]$SkipInfra,
    [switch]$SkipApp
)

$ErrorActionPreference = "Stop"

# =============================================================================
# 関数定義
# =============================================================================

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host "=== $Message ===" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Message)
    Write-Host "[OK] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-ErrorMsg {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# =============================================================================
# メイン処理
# =============================================================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " クライアントデプロイスクリプト" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  クライアント: $ClientName"
Write-Host "  プロバイダー: $CloudProvider"
Write-Host "============================================" -ForegroundColor Cyan

# プロジェクトルートを取得
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$TerraformDir = Join-Path $ProjectRoot "terraform"
$ClientDir = Join-Path $TerraformDir "clients" $ClientName
$PlatformDir = Join-Path $ProjectRoot "platforms" $CloudProvider

# クライアントディレクトリの確認
if (-not (Test-Path $ClientDir)) {
    Write-ErrorMsg "クライアントディレクトリが見つかりません: $ClientDir"
    exit 1
}

# =============================================================================
# Step 1: Dockerイメージのビルド
# =============================================================================

Write-Step "Dockerイメージのビルド"

Push-Location $ProjectRoot
try {
    $ImageTag = "ic-test-ai-agent:$ClientName"
    Write-Host "イメージをビルドしています: $ImageTag"

    docker build -t $ImageTag .

    if ($LASTEXITCODE -ne 0) {
        Write-ErrorMsg "Dockerビルドに失敗しました"
        exit 1
    }

    Write-Success "Dockerイメージのビルドが完了しました"
}
finally {
    Pop-Location
}

# =============================================================================
# Step 2: インフラ構築（Terraform）
# =============================================================================

if (-not $SkipInfra) {
    Write-Step "インフラ構築 (Terraform)"

    # Terraformの確認
    try {
        terraform version | Out-Null
    }
    catch {
        Write-ErrorMsg "Terraformがインストールされていません"
        Write-Host "  .\scripts\setup-terraform.ps1 を実行してください"
        exit 1
    }

    Push-Location $ClientDir
    try {
        Write-Host "terraform init を実行しています..."
        terraform init

        Write-Host "terraform apply を実行しています..."
        terraform apply -auto-approve

        if ($LASTEXITCODE -ne 0) {
            Write-ErrorMsg "Terraformの適用に失敗しました"
            exit 1
        }

        Write-Success "インフラ構築が完了しました"

        # 出力を取得
        $outputs = terraform output -json | ConvertFrom-Json
        Write-Host "エンドポイント情報:"
        Write-Host ($outputs | ConvertTo-Json -Depth 5)
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Warning "インフラ構築をスキップしました"
}

# =============================================================================
# Step 3: アプリケーションデプロイ
# =============================================================================

if (-not $SkipApp) {
    Write-Step "アプリケーションデプロイ ($CloudProvider)"

    $DeployScript = Join-Path $PlatformDir "deploy.ps1"

    if (-not (Test-Path $DeployScript)) {
        Write-ErrorMsg "デプロイスクリプトが見つかりません: $DeployScript"
        exit 1
    }

    Push-Location $PlatformDir
    try {
        switch ($CloudProvider) {
            "azure" {
                Write-Host "Azure Functionsにデプロイしています..."
                # terraform出力からFunction App名を取得（または環境変数から）
                $FunctionAppName = $env:AZURE_FUNCTION_APP
                if (-not $FunctionAppName) {
                    Write-Warning "AZURE_FUNCTION_APP環境変数が設定されていません"
                    Write-Host "手動でデプロイしてください:"
                    Write-Host "  cd $PlatformDir"
                    Write-Host "  .\deploy.ps1 -FunctionAppName <name>"
                }
                else {
                    & $DeployScript -FunctionAppName $FunctionAppName
                }
            }
            "aws" {
                Write-Host "AWS Lambdaにデプロイしています..."
                $FunctionName = $env:AWS_LAMBDA_FUNCTION
                if (-not $FunctionName) {
                    Write-Warning "AWS_LAMBDA_FUNCTION環境変数が設定されていません"
                    Write-Host "手動でデプロイしてください:"
                    Write-Host "  cd $PlatformDir"
                    Write-Host "  .\deploy.ps1 -FunctionName <name>"
                }
                else {
                    & $DeployScript -FunctionName $FunctionName
                }
            }
            "gcp" {
                Write-Host "GCP Cloud Runにデプロイしています..."
                $ServiceName = $env:GCP_CLOUD_RUN_SERVICE
                if (-not $ServiceName) {
                    Write-Warning "GCP_CLOUD_RUN_SERVICE環境変数が設定されていません"
                    Write-Host "手動でデプロイしてください:"
                    Write-Host "  cd $PlatformDir"
                    Write-Host "  .\deploy.ps1 -ServiceName <name>"
                }
                else {
                    & $DeployScript -ServiceName $ServiceName
                }
            }
        }

        Write-Success "アプリケーションデプロイが完了しました"
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Warning "アプリケーションデプロイをスキップしました"
}

# =============================================================================
# 完了
# =============================================================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " デプロイ完了" -ForegroundColor Green
Write-Host "============================================" -ForegroundColor Green
Write-Host "  クライアント: $ClientName"
Write-Host "  プロバイダー: $CloudProvider"
Write-Host "============================================" -ForegroundColor Green
Write-Host ""
Write-Host "次のステップ:" -ForegroundColor Yellow
Write-Host "  1. エンドポイントのヘルスチェックを確認"
Write-Host "  2. テストリクエストを送信"
Write-Host ""
