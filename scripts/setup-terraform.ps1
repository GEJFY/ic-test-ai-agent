<#
.SYNOPSIS
    Terraformのインストールとクライアント設定の初期化を行います。

.DESCRIPTION
    このスクリプトは以下を実行します:
    1. Terraformがインストールされているか確認
    2. 未インストールの場合、wingetまたはchocolateyでインストール
    3. 指定されたクライアントディレクトリでterraform initを実行

.PARAMETER ClientName
    クライアント名（terraform/clients/<ClientName>）

.PARAMETER SkipInstall
    Terraformのインストールをスキップ

.EXAMPLE
    .\setup-terraform.ps1 -ClientName "sample-client"

.EXAMPLE
    .\setup-terraform.ps1 -ClientName "company-a" -SkipInstall
#>

param(
    [Parameter(Mandatory=$false)]
    [string]$ClientName = "sample-client",

    [switch]$SkipInstall
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

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

function Test-TerraformInstalled {
    try {
        $version = terraform version 2>&1
        if ($LASTEXITCODE -eq 0) {
            return $true
        }
    }
    catch {
        return $false
    }
    return $false
}

function Install-Terraform {
    Write-Step "Terraformのインストール"

    # wingetを試す
    try {
        $wingetVersion = winget --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "wingetでTerraformをインストールしています..."
            winget install HashiCorp.Terraform
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Terraformのインストールが完了しました"
                # PATHを更新
                $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
                return $true
            }
        }
    }
    catch {
        Write-Warning "wingetが利用できません"
    }

    # chocolateyを試す
    try {
        $chocoVersion = choco --version 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "ChocolateyでTerraformをインストールしています..."
            choco install terraform -y
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Terraformのインストールが完了しました"
                return $true
            }
        }
    }
    catch {
        Write-Warning "Chocolateyが利用できません"
    }

    # 手動インストールの案内
    Write-Error "自動インストールに失敗しました"
    Write-Host ""
    Write-Host "以下のいずれかの方法でインストールしてください:" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "1. winget (推奨):" -ForegroundColor White
    Write-Host "   winget install HashiCorp.Terraform"
    Write-Host ""
    Write-Host "2. Chocolatey:" -ForegroundColor White
    Write-Host "   choco install terraform"
    Write-Host ""
    Write-Host "3. 手動ダウンロード:" -ForegroundColor White
    Write-Host "   https://developer.hashicorp.com/terraform/downloads"
    Write-Host ""

    return $false
}

# =============================================================================
# メイン処理
# =============================================================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host " Terraform セットアップスクリプト" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan

# プロジェクトルートを取得
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent $ScriptDir
$TerraformDir = Join-Path $ProjectRoot "terraform"
$ClientDir = Join-Path $TerraformDir "clients" $ClientName

# Terraformのインストール確認
Write-Step "Terraformの確認"

if (Test-TerraformInstalled) {
    $version = terraform version -json 2>$null | ConvertFrom-Json
    Write-Success "Terraform v$($version.terraform_version) がインストールされています"
}
elseif (-not $SkipInstall) {
    if (-not (Install-Terraform)) {
        exit 1
    }

    # インストール後の確認
    if (-not (Test-TerraformInstalled)) {
        Write-Error "Terraformのインストールに失敗しました。新しいターミナルで再実行してください。"
        exit 1
    }
}
else {
    Write-Error "Terraformがインストールされていません"
    exit 1
}

# クライアントディレクトリの確認
Write-Step "クライアント設定の確認"

if (-not (Test-Path $ClientDir)) {
    Write-Error "クライアントディレクトリが見つかりません: $ClientDir"
    Write-Host ""
    Write-Host "利用可能なクライアント:" -ForegroundColor Yellow

    $clients = Get-ChildItem -Path (Join-Path $TerraformDir "clients") -Directory | Where-Object { $_.Name -ne "_template" }
    foreach ($client in $clients) {
        Write-Host "  - $($client.Name)"
    }

    Write-Host ""
    Write-Host "新規クライアントを作成するには:" -ForegroundColor Yellow
    Write-Host "  Copy-Item -Path terraform/clients/_template -Destination terraform/clients/<client-name> -Recurse"
    exit 1
}

$TfVarsFile = Join-Path $ClientDir "terraform.tfvars"
if (-not (Test-Path $TfVarsFile)) {
    Write-Warning "terraform.tfvars が見つかりません"
    Write-Host ""

    $ExampleFile = Join-Path $ClientDir "terraform.tfvars.example"
    if (Test-Path $ExampleFile) {
        Write-Host "terraform.tfvars.example からコピーしますか? (Y/n)" -ForegroundColor Yellow
        $response = Read-Host
        if ($response -eq "" -or $response -eq "Y" -or $response -eq "y") {
            Copy-Item $ExampleFile $TfVarsFile
            Write-Success "terraform.tfvars を作成しました"
            Write-Warning "terraform.tfvars を編集して、適切な値を設定してください"
            Write-Host "  notepad $TfVarsFile"
            exit 0
        }
    }

    Write-Error "terraform.tfvars を作成してください"
    exit 1
}

Write-Success "クライアント設定が見つかりました: $ClientName"

# Terraform初期化
Write-Step "Terraform初期化"

Push-Location $ClientDir
try {
    Write-Host "terraform init を実行しています..."
    terraform init

    if ($LASTEXITCODE -ne 0) {
        Write-Error "terraform init に失敗しました"
        exit 1
    }

    Write-Success "Terraformの初期化が完了しました"

    # Terraform Plan
    Write-Step "Terraform Plan"
    Write-Host "terraform plan を実行しています..."
    terraform plan

    if ($LASTEXITCODE -ne 0) {
        Write-Warning "terraform plan に警告またはエラーがあります"
    }
    else {
        Write-Success "Terraform Planが完了しました"
    }

    # 適用確認
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host " セットアップ完了" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "次のステップ:" -ForegroundColor Yellow
    Write-Host "  1. terraform.tfvars の設定値を確認"
    Write-Host "  2. terraform plan で変更内容を確認"
    Write-Host "  3. terraform apply でインフラを構築"
    Write-Host ""
    Write-Host "コマンド:" -ForegroundColor Cyan
    Write-Host "  cd $ClientDir"
    Write-Host "  terraform apply"
    Write-Host ""
}
finally {
    Pop-Location
}
