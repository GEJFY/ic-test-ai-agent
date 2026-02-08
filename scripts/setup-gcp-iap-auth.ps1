# setup-gcp-iap-auth.ps1
# GCP Identity-Aware Proxy (IAP) 認証のセットアップスクリプト
#
# 前提条件:
#   - Google Cloud SDK (gcloud) がインストール済み
#   - GCPプロジェクトへのアクセス権限
#   - Cloud Functions が既にデプロイ済み
#
# 使用方法:
#   .\setup-gcp-iap-auth.ps1 -ProjectId "your-project-id" -Region "asia-northeast1"
#
# 注意:
#   - 認証なしでデプロイする場合は deploy.ps1 で -AllowUnauthenticated を指定
#   - このスクリプトは認証を有効化する場合にのみ実行

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,

    [Parameter(Mandatory=$false)]
    [string]$Region = "asia-northeast1",

    [Parameter(Mandatory=$false)]
    [string]$FunctionName = "evaluate",

    [Parameter(Mandatory=$false)]
    [string]$GroupEmail = ""  # 例: ic-test-users@your-domain.com
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================"
Write-Host "GCP 認証セットアップスクリプト"
Write-Host "============================================================"
Write-Host ""

# 1. gcloud CLI確認
Write-Host "[Step 1] gcloud CLI確認..."
try {
    $account = gcloud config get-value account 2>$null
    if (-not $account) {
        Write-Host "GCPにログインしてください..."
        gcloud auth login
        $account = gcloud config get-value account
    }
    Write-Host "  ログイン済み: $account"
}
catch {
    Write-Error "Google Cloud SDK がインストールされていません。"
    exit 1
}

# プロジェクト設定
gcloud config set project $ProjectId
Write-Host "  プロジェクト: $ProjectId"
Write-Host ""

# 2. 必要なAPIを有効化
Write-Host "[Step 2] 必要なAPIを有効化..."
$apis = @(
    "iap.googleapis.com",
    "cloudidentity.googleapis.com"
)

foreach ($api in $apis) {
    gcloud services enable $api --quiet 2>$null
    Write-Host "  有効化: $api"
}
Write-Host ""

# 3. Cloud Functionの認証を必須に変更
Write-Host "[Step 3] Cloud Functionの認証設定..."
Write-Host "  認証を必須に設定中..."

gcloud functions remove-iam-policy-binding $FunctionName `
    --region=$Region `
    --member="allUsers" `
    --role="roles/cloudfunctions.invoker" `
    2>$null

if ($LASTEXITCODE -eq 0) {
    Write-Host "  allUsers のアクセスを削除しました"
} else {
    Write-Host "  allUsers は既に削除されています"
}
Write-Host ""

# 4. サービスアカウントまたはグループにアクセス権を付与
Write-Host "[Step 4] アクセス権の設定..."

if ($GroupEmail) {
    # グループにアクセス権を付与
    Write-Host "  グループにアクセス権を付与: $GroupEmail"
    gcloud functions add-iam-policy-binding $FunctionName `
        --region=$Region `
        --member="group:$GroupEmail" `
        --role="roles/cloudfunctions.invoker"

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  グループへのアクセス権付与完了"
    } else {
        Write-Host "警告: グループへのアクセス権付与に失敗しました" -ForegroundColor Yellow
    }
} else {
    Write-Host "  グループが指定されていません。"
    Write-Host "  個別ユーザーまたはサービスアカウントに手動でアクセス権を付与してください。"
    Write-Host ""
    Write-Host "  例（ユーザー追加）:"
    Write-Host "    gcloud functions add-iam-policy-binding $FunctionName \"
    Write-Host "      --region=$Region \"
    Write-Host "      --member='user:example@your-domain.com' \"
    Write-Host "      --role='roles/cloudfunctions.invoker'"
    Write-Host ""
    Write-Host "  例（グループ追加）:"
    Write-Host "    gcloud functions add-iam-policy-binding $FunctionName \"
    Write-Host "      --region=$Region \"
    Write-Host "      --member='group:ic-test-users@your-domain.com' \"
    Write-Host "      --role='roles/cloudfunctions.invoker'"
}
Write-Host ""

# 5. OAuth同意画面の設定案内
Write-Host "[Step 5] OAuth同意画面設定..."
Write-Host "  ブラウザ認証を使用する場合は、GCP Consoleで設定が必要です："
Write-Host ""
Write-Host "  1. GCP Console → APIs & Services → OAuth consent screen"
Write-Host "  2. User Type: Internal（組織内のみ）"
Write-Host "  3. App name: IC Test Evaluation"
Write-Host "  4. Support email: $account"
Write-Host ""

# 6. クライアント認証情報の作成案内
Write-Host "[Step 6] OAuth クライアント作成..."
Write-Host "  PowerShellからの認証に OAuth クライアントが必要です："
Write-Host ""
Write-Host "  1. GCP Console → APIs & Services → Credentials"
Write-Host "  2. Create Credentials → OAuth client ID"
Write-Host "  3. Application type: Desktop app"
Write-Host "  4. Name: IC Test PowerShell Client"
Write-Host "  5. JSONをダウンロードして保存"
Write-Host ""

# 7. 設定情報の出力
Write-Host "============================================================"
Write-Host "セットアップ完了！" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ""

# Function URLを取得
$functionUrl = gcloud functions describe $FunctionName --region=$Region --format="value(serviceConfig.uri)" 2>$null
if (-not $functionUrl) {
    $functionUrl = "https://$Region-$ProjectId.cloudfunctions.net/$FunctionName"
}

Write-Host "以下の設定を setting.json に追加してください:"
Write-Host ""
Write-Host @"
{
    "api": {
        "provider": "GCP",
        "authType": "gcpIdentityToken",
        "endpoint": "$functionUrl"
    },
    "gcp": {
        "projectId": "$ProjectId",
        "region": "$Region"
    }
}
"@ -ForegroundColor Cyan

Write-Host ""
Write-Host "============================================================"
Write-Host "認証方法"
Write-Host "============================================================"
Write-Host ""
Write-Host "方法1: gcloud CLI（開発者向け）"
Write-Host '  $token = gcloud auth print-identity-token'
Write-Host '  Invoke-RestMethod -Uri $url -Headers @{Authorization="Bearer $token"}'
Write-Host ""
Write-Host "方法2: サービスアカウント（自動化向け）"
Write-Host '  $env:GOOGLE_APPLICATION_CREDENTIALS = "path/to/service-account.json"'
Write-Host ""
Write-Host "方法3: OAuth 2.0（エンドユーザー向け）"
Write-Host "  GCP ConsoleでOAuthクライアントを作成し、CallCloudApi.ps1で使用"
Write-Host ""
