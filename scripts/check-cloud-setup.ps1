# check-cloud-setup.ps1
# クラウド環境のセットアップ状況を確認するスクリプト
# コンテナベースデプロイ（Container Apps / App Runner / Cloud Run）対応

Write-Host "============================================================"
Write-Host "クラウド環境セットアップ確認（コンテナデプロイ対応）"
Write-Host "============================================================"
Write-Host ""

# Docker確認（全プラットフォーム共通で必須）
Write-Host "[Docker]" -ForegroundColor Cyan
$dockerInstalled = $false
try {
    $dockerVersion = docker version --format '{{.Client.Version}}' 2>&1
    if ($LASTEXITCODE -eq 0) {
        $dockerInstalled = $true
        Write-Host "  状態: インストール済み" -ForegroundColor Green
        Write-Host "  バージョン: $dockerVersion"

        # Docker Daemon起動確認
        $dockerInfo = docker info 2>&1
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  デーモン: 起動中" -ForegroundColor Green
        }
        else {
            Write-Host "  デーモン: 停止中" -ForegroundColor Yellow
            Write-Host "  → Docker Desktopを起動してください"
        }
    }
}
catch {
    # コマンドが見つからない
}

if (-not $dockerInstalled) {
    Write-Host "  状態: 未インストール" -ForegroundColor Red
    Write-Host "  → 実行: winget install Docker.DockerDesktop"
}
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

            # Container Apps拡張機能確認
            $caExt = az extension show --name containerapp 2>&1
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  containerapp拡張: インストール済み" -ForegroundColor Green
            }
            else {
                Write-Host "  containerapp拡張: 未インストール" -ForegroundColor Yellow
                Write-Host "  → 実行: az extension add --name containerapp --upgrade"
            }
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

            # Cloud Run APIの有効化確認
            $runApi = gcloud services list --enabled --filter="name:run.googleapis.com" --format="value(name)" 2>&1
            if ($runApi -match "run.googleapis.com") {
                Write-Host "  Cloud Run API: 有効" -ForegroundColor Green
            }
            else {
                Write-Host "  Cloud Run API: 未有効化" -ForegroundColor Yellow
                Write-Host "  → 実行: gcloud services enable run.googleapis.com"
            }

            # Artifact Registry APIの有効化確認
            $arApi = gcloud services list --enabled --filter="name:artifactregistry.googleapis.com" --format="value(name)" 2>&1
            if ($arApi -match "artifactregistry.googleapis.com") {
                Write-Host "  Artifact Registry API: 有効" -ForegroundColor Green
            }
            else {
                Write-Host "  Artifact Registry API: 未有効化" -ForegroundColor Yellow
                Write-Host "  → 実行: gcloud services enable artifactregistry.googleapis.com"
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

            # ECRリポジトリ確認
            $ecrRepos = aws ecr describe-repositories --query "repositories[?contains(repositoryName, 'ic-test')].repositoryName" --output text 2>&1
            if ($LASTEXITCODE -eq 0 -and $ecrRepos) {
                Write-Host "  ECRリポジトリ: $ecrRepos" -ForegroundColor Green
            }
            else {
                Write-Host "  ECRリポジトリ: 未作成またはic-test関連なし" -ForegroundColor Yellow
                Write-Host "  → 実行: aws ecr create-repository --repository-name ic-test-agent"
            }

            # App Runnerサービス確認
            $appRunnerServices = aws apprunner list-services --query "ServiceSummaryList[?contains(ServiceName, 'ic-test')].ServiceName" --output text 2>&1
            if ($LASTEXITCODE -eq 0 -and $appRunnerServices) {
                Write-Host "  App Runnerサービス: $appRunnerServices" -ForegroundColor Green
            }
            else {
                Write-Host "  App Runnerサービス: 未作成またはic-test関連なし" -ForegroundColor Yellow
            }
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
Write-Host "winget install Docker.DockerDesktop"
Write-Host "winget install Microsoft.AzureCLI"
Write-Host "winget install Google.CloudSDK"
Write-Host "winget install Amazon.AWSCLI"
Write-Host ""
Write-Host "# Azure Container Apps拡張機能:"
Write-Host "az extension add --name containerapp --upgrade"
Write-Host ""
Write-Host "# GCP API有効化:"
Write-Host "gcloud services enable run.googleapis.com artifactregistry.googleapis.com"
Write-Host ""
