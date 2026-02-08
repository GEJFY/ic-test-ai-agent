# deploy.ps1
# Azure Functions デプロイスクリプト
#
# 使用方法:
#   .\deploy.ps1 -FunctionAppName "func-ic-test-evaluation" -ResourceGroup "rg-ic-test"
#
# 事前準備:
#   1. Azure CLI をインストール: https://docs.microsoft.com/ja-jp/cli/azure/install-azure-cli
#   2. ログイン: az login
#   3. サブスクリプション設定: az account set --subscription "Your Subscription"
#
param(
    [Parameter(Mandatory=$true)]
    [string]$FunctionAppName,

    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory=$false)]
    [string]$StorageAccountName = "",  # 空の場合は既存の設定を使用

    [Parameter(Mandatory=$false)]
    [switch]$SkipEnvSetup = $false  # 環境変数設定をスキップ
)

$ErrorActionPreference = "Stop"

# ==============================================================================
# 設定
# ==============================================================================
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$AzurePlatformDir = $ScriptDir
$SrcDir = Join-Path $ProjectRoot "src"
$DeployDir = Join-Path $ScriptDir ".deploy"
$ZipPath = Join-Path $ScriptDir "deploy.zip"

Write-Host "=============================================="
Write-Host "Azure Functions デプロイスクリプト"
Write-Host "=============================================="
Write-Host "Function App: $FunctionAppName"
Write-Host "Resource Group: $ResourceGroup"
Write-Host "Project Root: $ProjectRoot"
Write-Host ""

# ==============================================================================
# 1. Azure CLI 確認
# ==============================================================================
Write-Host "[1/5] Azure CLI を確認中..."
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
# 2. デプロイパッケージ作成
# ==============================================================================
Write-Host "[2/5] デプロイパッケージを作成中..."

# 既存のデプロイディレクトリを削除
if (Test-Path $DeployDir) {
    Remove-Item -Path $DeployDir -Recurse -Force
}

# デプロイディレクトリを作成
New-Item -ItemType Directory -Path $DeployDir -Force | Out-Null

# Azure Functions プラットフォームファイルをコピー
$platformFiles = @(
    "function_app.py",
    "host.json",
    "requirements.txt",
    ".funcignore"
)

foreach ($file in $platformFiles) {
    $sourcePath = Join-Path $AzurePlatformDir $file
    if (Test-Path $sourcePath) {
        Copy-Item -Path $sourcePath -Destination $DeployDir
        Write-Host "      コピー: $file"
    }
}

# src/ ディレクトリをコピー
$destSrcDir = Join-Path $DeployDir "src"
Copy-Item -Path $SrcDir -Destination $destSrcDir -Recurse
Write-Host "      コピー: src/ ディレクトリ"

# 不要なファイルを削除（__pycache__, .pyc, etc.）
Get-ChildItem -Path $DeployDir -Recurse -Directory -Name "__pycache__" | ForEach-Object {
    Remove-Item -Path (Join-Path $DeployDir $_) -Recurse -Force
}
Get-ChildItem -Path $DeployDir -Recurse -File -Filter "*.pyc" | Remove-Item -Force

# ZIPファイルを作成（Linux互換のスラッシュパスで）
if (Test-Path $ZipPath) {
    Remove-Item -Path $ZipPath -Force
}

# Pythonスクリプトファイルを一時作成してLinux互換のZIPを作成
$tempPythonScript = Join-Path $env:TEMP "create_zip.py"
@"
# -*- coding: utf-8 -*-
import zipfile
import os
import sys

deploy_dir = sys.argv[1]
zip_path = sys.argv[2]

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(deploy_dir):
        for file in files:
            file_path = os.path.join(root, file)
            # Linux互換のパス（スラッシュ）でアーカイブに追加
            arcname = os.path.relpath(file_path, deploy_dir).replace('\\', '/')
            zipf.write(file_path, arcname)
            print(f'  Added: {arcname}')

print(f'Created: {zip_path}')
"@ | Out-File -FilePath $tempPythonScript -Encoding UTF8

python $tempPythonScript $DeployDir $ZipPath

# 一時ファイルを削除
Remove-Item -Path $tempPythonScript -Force -ErrorAction SilentlyContinue

Write-Host "      ZIP作成: deploy.zip (Linux互換パス)"

# ==============================================================================
# 3. Azure Functions にデプロイ
# ==============================================================================
Write-Host "[3/5] Azure Functions にデプロイ中..."
Write-Host "      (数分かかる場合があります)"

az functionapp deployment source config-zip `
    --resource-group $ResourceGroup `
    --name $FunctionAppName `
    --src $ZipPath `
    --build-remote true

if ($LASTEXITCODE -ne 0) {
    Write-Error "デプロイに失敗しました。"
    exit 1
}

Write-Host "      デプロイ完了!"

# ==============================================================================
# 4. 環境変数設定（非同期ジョブ処理用）
# ==============================================================================
if (-not $SkipEnvSetup) {
    Write-Host "[4/5] 環境変数を設定中..."

    # Storage Account の接続文字列を取得
    if ($StorageAccountName -ne "") {
        Write-Host "      Storage Account: $StorageAccountName"
        $storageConnStr = az storage account show-connection-string `
            --resource-group $ResourceGroup `
            --name $StorageAccountName `
            --query connectionString -o tsv

        if ($LASTEXITCODE -ne 0 -or $storageConnStr -eq "") {
            Write-Warning "Storage Account の接続文字列を取得できませんでした。手動で設定してください。"
        }
        else {
            # 環境変数を設定
            az functionapp config appsettings set `
                --resource-group $ResourceGroup `
                --name $FunctionAppName `
                --settings `
                "JOB_STORAGE_PROVIDER=AZURE" `
                "JOB_QUEUE_PROVIDER=AZURE" `
                "AZURE_STORAGE_CONNECTION_STRING=$storageConnStr" `
                "AzureWebJobsStorage=$storageConnStr"

            Write-Host "      環境変数設定完了"
        }
    }
    else {
        Write-Host "      Storage Account が指定されていないため、環境変数設定をスキップ"
        Write-Host "      手動で以下の環境変数を設定してください:"
        Write-Host "        - JOB_STORAGE_PROVIDER=AZURE"
        Write-Host "        - JOB_QUEUE_PROVIDER=AZURE"
        Write-Host "        - AZURE_STORAGE_CONNECTION_STRING=..."
        Write-Host "        - AzureWebJobsStorage=..."
    }
}
else {
    Write-Host "[4/5] 環境変数設定をスキップ"
}

# ==============================================================================
# 5. クリーンアップ
# ==============================================================================
Write-Host "[5/5] クリーンアップ中..."
if (Test-Path $DeployDir) {
    Remove-Item -Path $DeployDir -Recurse -Force
}
Write-Host "      完了"

# ==============================================================================
# 完了メッセージ
# ==============================================================================
Write-Host ""
Write-Host "=============================================="
Write-Host "デプロイ完了!"
Write-Host "=============================================="
Write-Host ""
Write-Host "エンドポイント:"
Write-Host "  同期API:  https://$FunctionAppName.azurewebsites.net/api/evaluate"
Write-Host "  非同期API:"
Write-Host "    Submit:  https://$FunctionAppName.azurewebsites.net/api/evaluate/submit"
Write-Host "    Status:  https://$FunctionAppName.azurewebsites.net/api/evaluate/status/{job_id}"
Write-Host "    Results: https://$FunctionAppName.azurewebsites.net/api/evaluate/results/{job_id}"
Write-Host ""
Write-Host "次のステップ:"
Write-Host "  1. Azure Portal で環境変数を確認"
Write-Host "  2. setting.json の asyncMode を true に設定"
Write-Host "  3. Excel から動作確認"
Write-Host ""
