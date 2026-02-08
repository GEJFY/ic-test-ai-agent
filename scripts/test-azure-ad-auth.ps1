# test-azure-ad-auth.ps1
# Azure AD認証のテストスクリプト
#
# 使用方法:
#   .\test-azure-ad-auth.ps1 -TenantId "xxx" -ClientId "yyy" -FunctionUrl "https://xxx.azurewebsites.net/api/health"

param(
    [Parameter(Mandatory=$true)]
    [string]$TenantId,

    [Parameter(Mandatory=$true)]
    [string]$ClientId,

    [Parameter(Mandatory=$true)]
    [string]$FunctionUrl,

    [Parameter(Mandatory=$false)]
    [string]$Scope = ""
)

# スコープが未指定の場合、デフォルト値を設定
if (-not $Scope) {
    $Scope = "api://$ClientId/user_impersonation openid offline_access"
}

Write-Host "============================================================"
Write-Host "Azure AD認証テスト"
Write-Host "============================================================"
Write-Host ""
Write-Host "設定値:"
Write-Host "  テナントID: $TenantId"
Write-Host "  クライアントID: $ClientId"
Write-Host "  スコープ: $Scope"
Write-Host "  エンドポイント: $FunctionUrl"
Write-Host ""

# Step 1: トークン取得
Write-Host "[Step 1] アクセストークン取得..."

# Az.Accounts モジュールを試す
$token = $null
try {
    $azModule = Get-Module -ListAvailable -Name Az.Accounts
    if ($azModule) {
        Import-Module Az.Accounts -ErrorAction SilentlyContinue

        $context = Get-AzContext -ErrorAction SilentlyContinue
        if (-not $context) {
            Write-Host "  Azureにログインします..."
            Connect-AzAccount -TenantId $TenantId -ErrorAction Stop | Out-Null
        } else {
            Write-Host "  既存のログインを使用: $($context.Account.Id)"
        }

        $resourceUrl = $Scope -replace '/\.default$', ''
        $tokenResult = Get-AzAccessToken -ResourceUrl $resourceUrl -ErrorAction Stop
        $token = $tokenResult.Token
        Write-Host "  トークン取得成功 (Az.Accounts)" -ForegroundColor Green
    }
}
catch {
    Write-Host "  Az.Accountsでの取得失敗: $($_.Exception.Message)" -ForegroundColor Yellow
}

# Az.Accountsで取得できない場合、Device Code Flowを使用
if (-not $token) {
    Write-Host "  Device Code Flowで認証します..."

    try {
        $deviceCodeUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/devicecode"
        $deviceCodeBody = @{
            client_id = $ClientId
            scope     = $Scope
        }

        $deviceCodeResponse = Invoke-RestMethod -Uri $deviceCodeUrl -Method Post -Body $deviceCodeBody -ErrorAction Stop

        Write-Host ""
        Write-Host "========================================" -ForegroundColor Yellow
        Write-Host "ブラウザで認証してください" -ForegroundColor Yellow
        Write-Host "========================================" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "URL: $($deviceCodeResponse.verification_uri)" -ForegroundColor Cyan
        Write-Host "コード: $($deviceCodeResponse.user_code)" -ForegroundColor White -BackgroundColor DarkBlue
        Write-Host ""
        Write-Host "認証を待機中..." -ForegroundColor Gray

        $tokenUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
        $tokenBody = @{
            grant_type  = "urn:ietf:params:oauth:grant-type:device_code"
            client_id   = $ClientId
            device_code = $deviceCodeResponse.device_code
        }

        $pollInterval = 5
        $maxAttempts = 60

        for ($attempt = 0; $attempt -lt $maxAttempts; $attempt++) {
            Start-Sleep -Seconds $pollInterval

            try {
                $tokenResponse = Invoke-RestMethod -Uri $tokenUrl -Method Post -Body $tokenBody -ErrorAction Stop
                if ($tokenResponse.access_token) {
                    $token = $tokenResponse.access_token
                    Write-Host ""
                    Write-Host "  トークン取得成功 (Device Code Flow)" -ForegroundColor Green
                    break
                }
            }
            catch {
                $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue
                if ($errorResponse.error -eq "authorization_pending") {
                    Write-Host "." -NoNewline
                    continue
                }
                elseif ($errorResponse.error -eq "expired_token") {
                    throw "認証タイムアウト"
                }
                else {
                    throw $errorResponse.error_description
                }
            }
        }
    }
    catch {
        Write-Host "  Device Code Flow失敗: $($_.Exception.Message)" -ForegroundColor Red
        exit 1
    }
}

if (-not $token) {
    Write-Host "エラー: トークンを取得できませんでした" -ForegroundColor Red
    exit 1
}

Write-Host ""

# Step 2: トークン情報の表示
Write-Host "[Step 2] トークン情報..."
try {
    # JWTをデコード（ペイロード部分のみ）
    $tokenParts = $token.Split('.')
    if ($tokenParts.Length -ge 2) {
        $payload = $tokenParts[1]
        # Base64 padding
        $padding = 4 - ($payload.Length % 4)
        if ($padding -ne 4) {
            $payload += '=' * $padding
        }
        $decodedPayload = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($payload))
        $claims = $decodedPayload | ConvertFrom-Json

        Write-Host "  ユーザー: $($claims.name) ($($claims.preferred_username))"
        Write-Host "  対象リソース: $($claims.aud)"

        $expTime = [System.DateTimeOffset]::FromUnixTimeSeconds($claims.exp).LocalDateTime
        Write-Host "  有効期限: $expTime"
    }
}
catch {
    Write-Host "  トークンのデコードに失敗（認証自体は成功）" -ForegroundColor Yellow
}
Write-Host ""

# Step 3: APIコール
Write-Host "[Step 3] API呼び出しテスト..."
Write-Host "  エンドポイント: $FunctionUrl"

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

try {
    $response = Invoke-RestMethod -Uri $FunctionUrl -Method Get -Headers $headers -ErrorAction Stop
    Write-Host ""
    Write-Host "============================================================"
    Write-Host "テスト成功！" -ForegroundColor Green
    Write-Host "============================================================"
    Write-Host ""
    Write-Host "レスポンス:"
    $response | ConvertTo-Json -Depth 5 | Write-Host
}
catch {
    $statusCode = $_.Exception.Response.StatusCode.value__
    Write-Host ""

    if ($statusCode -eq 401) {
        Write-Host "============================================================"
        Write-Host "認証エラー (401 Unauthorized)" -ForegroundColor Red
        Write-Host "============================================================"
        Write-Host ""
        Write-Host "考えられる原因:"
        Write-Host "  1. Function Appの認証設定が有効になっていない"
        Write-Host "  2. クライアントIDまたはスコープが間違っている"
        Write-Host "  3. トークンの対象リソース(aud)が一致していない"
        Write-Host ""
        Write-Host "Azure Portalで確認してください:"
        Write-Host "  Function App → 認証 → IDプロバイダー"
    }
    elseif ($statusCode -eq 403) {
        Write-Host "============================================================"
        Write-Host "アクセス拒否 (403 Forbidden)" -ForegroundColor Red
        Write-Host "============================================================"
        Write-Host ""
        Write-Host "認証は成功しましたが、アクセス権がありません。"
        Write-Host ""
        Write-Host "考えられる原因:"
        Write-Host "  1. ユーザーが許可されたグループに所属していない"
        Write-Host "  2. Enterprise Applicationでユーザー割り当てが必要だが未割り当て"
        Write-Host ""
        Write-Host "Azure Portalで確認してください:"
        Write-Host "  Microsoft Entra ID → エンタープライズアプリケーション"
        Write-Host "  → 該当アプリ → ユーザーとグループ"
    }
    else {
        Write-Host "============================================================"
        Write-Host "エラー: $statusCode" -ForegroundColor Red
        Write-Host "============================================================"
        Write-Host ""
        Write-Host "詳細: $($_.Exception.Message)"
    }

    exit 1
}
