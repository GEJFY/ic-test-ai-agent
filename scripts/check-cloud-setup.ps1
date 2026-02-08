# check-cloud-setup.ps1
# クラウド環境のセットアップ状況を確認するスクリプト

Write-Host "============================================================"
Write-Host "クラウド環境セットアップ確認"
Write-Host "============================================================"
Write-Host ""

# Azure CLI確認
Write-Host "[Azure CLI]" -ForegroundColor Cyan
$azInstalled = $false
try {
    $azVersionOutput = az version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $azInstalled = $true
        Write-Host "  状態: インストール済み" -ForegroundColor Green

        $account = az account show 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ログイン: 済み" -ForegroundColor Green
        }
        else {
            Write-Host "  ログイン: 未実施" -ForegroundColor Yellow
            Write-Host "  → 実行: az login"
        }
    }
}
catch {
    # コマンドが見つからない
}

if (-not $azInstalled) {
    Write-Host "  状態: 未インストール" -ForegroundColor Red
    Write-Host "  → 実行: winget install Microsoft.AzureCLI"
}
Write-Host ""

# Azure Functions Core Tools確認
Write-Host "[Azure Functions Core Tools]" -ForegroundColor Cyan
$funcInstalled = $false
try {
    $funcVersion = func --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $funcInstalled = $true
        Write-Host "  状態: インストール済み" -ForegroundColor Green
        Write-Host "  バージョン: $funcVersion"
    }
}
catch {
    # コマンドが見つからない
}

if (-not $funcInstalled) {
    Write-Host "  状態: 未インストール" -ForegroundColor Red
    Write-Host "  → 実行: winget install Microsoft.Azure.FunctionsCoreTools"
}
Write-Host ""

# Google Cloud SDK確認
Write-Host "[Google Cloud SDK]" -ForegroundColor Cyan
$gcloudInstalled = $false
try {
    $gcloudOutput = gcloud version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $gcloudInstalled = $true
        Write-Host "  状態: インストール済み" -ForegroundColor Green

        $account = gcloud config get-value account 2>&1
        if ($account -and $account -ne "(unset)" -and $LASTEXITCODE -eq 0) {
            Write-Host "  ログイン: 済み ($account)" -ForegroundColor Green

            $project = gcloud config get-value project 2>&1
            if ($project -and $project -ne "(unset)") {
                Write-Host "  プロジェクト: $project"
            }
            else {
                Write-Host "  プロジェクト: 未設定" -ForegroundColor Yellow
            }
        }
        else {
            Write-Host "  ログイン: 未実施" -ForegroundColor Yellow
            Write-Host "  → 実行: gcloud auth login"
        }
    }
}
catch {
    # コマンドが見つからない
}

if (-not $gcloudInstalled) {
    Write-Host "  状態: 未インストール" -ForegroundColor Red
    Write-Host "  → 実行: winget install Google.CloudSDK"
}
Write-Host ""

# AWS CLI確認
Write-Host "[AWS CLI]" -ForegroundColor Cyan
$awsInstalled = $false
try {
    $awsVersion = aws --version 2>&1
    if ($LASTEXITCODE -eq 0) {
        $awsInstalled = $true
        Write-Host "  状態: インストール済み" -ForegroundColor Green
        Write-Host "  バージョン: $awsVersion"

        $identity = aws sts get-caller-identity 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  ログイン: 済み" -ForegroundColor Green
        }
        else {
            Write-Host "  ログイン: 未設定" -ForegroundColor Yellow
            Write-Host "  → 実行: aws configure"
        }
    }
}
catch {
    # コマンドが見つからない
}

if (-not $awsInstalled) {
    Write-Host "  状態: 未インストール" -ForegroundColor Red
    Write-Host "  → 実行: winget install Amazon.AWSCLI"
}
Write-Host ""

Write-Host "============================================================"
Write-Host "クイックインストールコマンド（管理者PowerShell）"
Write-Host "============================================================"
Write-Host ""
Write-Host "# 全てインストール:"
Write-Host "winget install Microsoft.AzureCLI"
Write-Host "winget install Microsoft.Azure.FunctionsCoreTools"
Write-Host "winget install Google.CloudSDK"
Write-Host "winget install Amazon.AWSCLI"
Write-Host ""
