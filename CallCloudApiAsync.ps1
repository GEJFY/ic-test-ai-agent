# CallCloudApiAsync.ps1
# 非同期版クラウドAPI呼び出しスクリプト
# 504 Gateway Timeout対策として、ジョブ送信→ポーリング→結果取得の3段階で処理
#
# 使用方法:
#   .\CallCloudApiAsync.ps1 -JsonFilePath "input.json" -Endpoint "https://xxx.azurewebsites.net/api/evaluate" `
#       -ApiKey "xxx" -OutputFilePath "output.json" -Provider "AZURE"
#
# 処理フロー:
#   1. POST /api/evaluate/submit でジョブ送信（即座にジョブIDを返却）
#   2. GET /api/evaluate/status/{job_id} でポーリング（完了まで待機）
#   3. GET /api/evaluate/results/{job_id} で結果取得
#
param(
    [Parameter(Mandatory=$true)]
    [string]$JsonFilePath,

    [Parameter(Mandatory=$true)]
    [string]$Endpoint,

    [Parameter(Mandatory=$false)]
    [string]$ApiKey = "",

    [Parameter(Mandatory=$true)]
    [string]$OutputFilePath,

    [Parameter(Mandatory=$true)]
    [string]$Provider,

    [Parameter(Mandatory=$false)]
    [string]$AuthHeader = "",

    [Parameter(Mandatory=$false)]
    [int]$TimeoutSec = 1800,  # 30分（非同期なので長めに設定）

    [Parameter(Mandatory=$false)]
    [int]$PollingIntervalSec = 5,  # ポーリング間隔

    # Azure AD Authentication Parameters
    [Parameter(Mandatory=$false)]
    [string]$AuthType = "functionsKey",

    [Parameter(Mandatory=$false)]
    [string]$TenantId = "",

    [Parameter(Mandatory=$false)]
    [string]$ClientId = "",

    [Parameter(Mandatory=$false)]
    [string]$Scope = ""
)

# ==============================================================================
# ユーティリティ関数
# ==============================================================================

# Azure AD参加状態を確認
function Test-AzureAdJoinStatus {
    $result = @{
        IsJoined = $false
        UserPrincipalName = $null
    }

    try {
        # dsregcmd /status を使用してAzure AD参加状態を確認
        $dsregOutput = dsregcmd /status 2>$null
        if ($dsregOutput -match "AzureAdJoined\s*:\s*YES") {
            $result.IsJoined = $true
        }
        if ($dsregOutput -match "WorkplaceJoined\s*:\s*YES") {
            $result.IsJoined = $true
        }

        # UPNを取得
        $upnMatch = $dsregOutput | Select-String -Pattern "UserEmail\s*:\s*(\S+)"
        if ($upnMatch) {
            $result.UserPrincipalName = $upnMatch.Matches[0].Groups[1].Value
        }
    }
    catch {
        # エラーの場合は無視（Azure AD未参加として扱う）
    }

    return $result
}

# トークンキャッシュファイルのパス
$script:TokenCachePath = Join-Path $env:TEMP "ic-test-azure-ad-token.json"

# デバッグログ出力（環境変数でオフにできる）
$script:DebugTokenCache = $true

function Write-TokenDebug {
    param([string]$Message)
    if ($script:DebugTokenCache) {
        Write-Host "[TokenCache] $Message" -ForegroundColor DarkGray
    }
}

# キャッシュからトークンを読み込む
function Get-CachedToken {
    param([string]$ClientId)

    Write-TokenDebug "キャッシュファイル確認: $($script:TokenCachePath)"

    if (-not (Test-Path $script:TokenCachePath)) {
        Write-TokenDebug "キャッシュファイルが存在しません"
        return $null
    }

    try {
        $cacheContent = Get-Content $script:TokenCachePath -Raw -ErrorAction Stop
        Write-TokenDebug "キャッシュファイル読み込み成功（サイズ: $($cacheContent.Length) bytes）"

        $cache = $cacheContent | ConvertFrom-Json -ErrorAction Stop

        # クライアントIDが一致するか確認
        if ($cache.client_id -ne $ClientId) {
            Write-TokenDebug "クライアントID不一致: キャッシュ=$($cache.client_id), 要求=$ClientId"
            return $null
        }
        Write-TokenDebug "クライアントID一致: $ClientId"

        # 有効期限をチェック（5分の余裕を持つ）
        # ISO 8601形式（"o"）で保存されているため、DateTimeOffsetでパース
        $expiresAt = $null
        try {
            # まずDateTimeOffsetでパースを試みる（タイムゾーン情報を保持）
            $expiresAt = [DateTimeOffset]::Parse($cache.expires_at).LocalDateTime
            Write-TokenDebug "有効期限パース成功（DateTimeOffset）: $($expiresAt.ToString('yyyy-MM-dd HH:mm:ss'))"
        }
        catch {
            try {
                # フォールバック: 直接DateTimeでパース
                $expiresAt = [DateTime]::Parse($cache.expires_at)
                Write-TokenDebug "有効期限パース成功（DateTime）: $($expiresAt.ToString('yyyy-MM-dd HH:mm:ss'))"
            }
            catch {
                Write-TokenDebug "有効期限パース失敗: $($cache.expires_at) - $($_.Exception.Message)"
                # パース失敗時はキャッシュ無効として扱う
                return $null
            }
        }

        $now = Get-Date
        $threshold = $now.AddMinutes(5)
        Write-TokenDebug "現在時刻: $($now.ToString('yyyy-MM-dd HH:mm:ss')), 閾値: $($threshold.ToString('yyyy-MM-dd HH:mm:ss'))"

        if ($expiresAt -gt $threshold) {
            $remainingMinutes = [math]::Round(($expiresAt - $now).TotalMinutes, 1)
            Write-Host "[CallCloudApiAsync] キャッシュされたトークンを使用します（残り: ${remainingMinutes}分）" -ForegroundColor Green
            return $cache
        }

        Write-TokenDebug "トークン有効期限切れまたは間近"

        # 有効期限切れだがリフレッシュトークンがある場合
        if ($cache.refresh_token) {
            Write-Host "[CallCloudApiAsync] トークンの有効期限が切れています。リフレッシュを試みます..."
            return $cache
        }

        Write-TokenDebug "リフレッシュトークンなし"
    }
    catch {
        Write-Host "[CallCloudApiAsync] キャッシュの読み込みに失敗: $($_.Exception.Message)" -ForegroundColor Yellow
        Write-TokenDebug "例外詳細: $($_.ToString())"
    }

    return $null
}

# トークンをキャッシュに保存
function Save-TokenCache {
    param(
        [string]$ClientId,
        [string]$AccessToken,
        [string]$RefreshToken,
        [int]$ExpiresIn
    )

    $expiresAt = (Get-Date).AddSeconds($ExpiresIn)

    $cache = @{
        client_id     = $ClientId
        access_token  = $AccessToken
        refresh_token = $RefreshToken
        expires_at    = $expiresAt.ToUniversalTime().ToString("o")  # UTCで保存
        created_at    = (Get-Date).ToUniversalTime().ToString("o")  # 作成日時も記録
    }

    try {
        $cache | ConvertTo-Json | Out-File -FilePath $script:TokenCachePath -Encoding UTF8 -Force
        Write-Host "[CallCloudApiAsync] トークンをキャッシュに保存しました（有効期限: $($expiresAt.ToString('HH:mm:ss'))）" -ForegroundColor Green
        Write-TokenDebug "キャッシュ保存先: $($script:TokenCachePath)"
    }
    catch {
        Write-Host "[CallCloudApiAsync] キャッシュの保存に失敗: $($_.Exception.Message)" -ForegroundColor Yellow
    }
}

# リフレッシュトークンで新しいアクセストークンを取得
function Refresh-AccessToken {
    param(
        [string]$TenantId,
        [string]$ClientId,
        [string]$RefreshToken,
        [string]$Scope
    )

    try {
        $tokenUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
        $tokenBody = @{
            grant_type    = "refresh_token"
            client_id     = $ClientId
            refresh_token = $RefreshToken
            scope         = $Scope
        }

        $response = Invoke-RestMethod -Uri $tokenUrl -Method Post -Body $tokenBody -ErrorAction Stop

        if ($response.access_token) {
            # 新しいトークンをキャッシュに保存
            Save-TokenCache -ClientId $ClientId `
                           -AccessToken $response.access_token `
                           -RefreshToken $response.refresh_token `
                           -ExpiresIn $response.expires_in

            Write-Host "[CallCloudApiAsync] トークンのリフレッシュに成功しました" -ForegroundColor Green
            return $response.access_token
        }
    }
    catch {
        Write-Host "[CallCloudApiAsync] トークンのリフレッシュに失敗: $($_.Exception.Message)" -ForegroundColor Yellow
    }

    return $null
}

# PKCE用のコード生成
function New-PkceCodeVerifier {
    $bytes = New-Object byte[] 32
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rng.Dispose()
    return [Convert]::ToBase64String($bytes) -replace '\+', '-' -replace '/', '_' -replace '=', ''
}

function New-PkceCodeChallenge {
    param([string]$CodeVerifier)
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($CodeVerifier)
    $hash = $sha256.ComputeHash($bytes)
    $sha256.Dispose()
    return [Convert]::ToBase64String($hash) -replace '\+', '-' -replace '/', '_' -replace '=', ''
}

# ブラウザベース認証（Authorization Code Flow with PKCE）
function Get-TokenWithBrowser {
    param(
        [string]$TenantId,
        [string]$ClientId,
        [string]$Scope
    )

    Write-Host "[CallCloudApiAsync] ブラウザ認証を試行中..." -ForegroundColor Cyan

    $codeVerifier = New-PkceCodeVerifier
    $codeChallenge = New-PkceCodeChallenge -CodeVerifier $codeVerifier

    $port = Get-Random -Minimum 8400 -Maximum 8500
    $redirectUri = "http://localhost:$port/"

    # サイレント認証を試行
    $authUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/authorize?" +
               "client_id=$ClientId" +
               "&response_type=code" +
               "&redirect_uri=$([Uri]::EscapeDataString($redirectUri))" +
               "&scope=$([Uri]::EscapeDataString($Scope))" +
               "&code_challenge=$codeChallenge" +
               "&code_challenge_method=S256" +
               "&prompt=none"

    try {
        $listener = New-Object System.Net.HttpListener
        $listener.Prefixes.Add($redirectUri)
        $listener.Start()

        Start-Process $authUrl

        $asyncResult = $listener.BeginGetContext($null, $null)
        $completed = $asyncResult.AsyncWaitHandle.WaitOne(10000)

        if (-not $completed) {
            $listener.Stop()

            # インタラクティブ認証にフォールバック
            $authUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/authorize?" +
                       "client_id=$ClientId" +
                       "&response_type=code" +
                       "&redirect_uri=$([Uri]::EscapeDataString($redirectUri))" +
                       "&scope=$([Uri]::EscapeDataString($Scope))" +
                       "&code_challenge=$codeChallenge" +
                       "&code_challenge_method=S256"

            $listener = New-Object System.Net.HttpListener
            $listener.Prefixes.Add($redirectUri)
            $listener.Start()

            Write-Host "[CallCloudApiAsync] ブラウザでAzure ADにログインしてください..." -ForegroundColor Yellow
            Start-Process $authUrl

            $asyncResult = $listener.BeginGetContext($null, $null)
            $completed = $asyncResult.AsyncWaitHandle.WaitOne(60000)

            if (-not $completed) {
                $listener.Stop()
                return $null
            }
        }

        $context = $listener.EndGetContext($asyncResult)
        $queryString = $context.Request.Url.Query

        # 成功ページを返す
        $responseHtml = "<html><body><h1>認証完了</h1><p>このウィンドウを閉じてください。</p><script>setTimeout(function(){window.close();},2000);</script></body></html>"
        $buffer = [System.Text.Encoding]::UTF8.GetBytes($responseHtml)
        $context.Response.ContentLength64 = $buffer.Length
        $context.Response.OutputStream.Write($buffer, 0, $buffer.Length)
        $context.Response.OutputStream.Close()
        $listener.Stop()

        if ($queryString -match "code=([^&]+)") {
            $authCode = [Uri]::UnescapeDataString($matches[1])

            $tokenUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
            $tokenBody = @{
                client_id     = $ClientId
                grant_type    = "authorization_code"
                code          = $authCode
                redirect_uri  = $redirectUri
                code_verifier = $codeVerifier
                scope         = $Scope
            }

            $tokenResponse = Invoke-RestMethod -Uri $tokenUrl -Method Post -Body $tokenBody -ErrorAction Stop

            if ($tokenResponse.access_token) {
                Write-Host "[CallCloudApiAsync] ブラウザ認証成功！" -ForegroundColor Green

                Save-TokenCache -ClientId $ClientId `
                               -AccessToken $tokenResponse.access_token `
                               -RefreshToken $tokenResponse.refresh_token `
                               -ExpiresIn $tokenResponse.expires_in

                return $tokenResponse.access_token
            }
        }
    }
    catch {
        Write-TokenDebug "ブラウザ認証エラー: $($_.Exception.Message)"
        if ($listener -and $listener.IsListening) { $listener.Stop() }
    }

    return $null
}

# MSAL.PSモジュール - 使用しない（互換性のため残す）
function Get-TokenWithMSAL {
    param(
        [string]$TenantId,
        [string]$ClientId,
        [string]$Scope,
        [string]$UserPrincipalName
    )
    return $null

    # MSAL.PSモジュールの確認
    if (-not (Get-Module -ListAvailable -Name MSAL.PS)) {
        Write-TokenDebug "MSAL.PSモジュールがインストールされていません"
        return $null
    }

    try {
        Import-Module MSAL.PS -ErrorAction Stop
        Write-Host "[CallCloudApiAsync] MSAL.PSモジュールを使用してサイレント認証を試行中..." -ForegroundColor Cyan

        # まずサイレント認証を試行
        $token = $null
        try {
            $token = Get-MsalToken -ClientId $ClientId -TenantId $TenantId -Scopes $Scope -Silent -ErrorAction Stop
        }
        catch {
            Write-TokenDebug "サイレント認証失敗: $($_.Exception.Message)"
        }

        # IWA（統合Windows認証）を試行
        if (-not $token -and $UserPrincipalName) {
            try {
                Write-Host "[CallCloudApiAsync] 統合Windows認証（IWA）を試行中..." -ForegroundColor Cyan
                $token = Get-MsalToken -ClientId $ClientId -TenantId $TenantId -Scopes $Scope `
                                       -IntegratedWindowsAuth -LoginHint $UserPrincipalName -ErrorAction Stop
            }
            catch {
                Write-TokenDebug "IWA認証失敗: $($_.Exception.Message)"
            }
        }

        if ($token -and $token.AccessToken) {
            Write-Host "[CallCloudApiAsync] MSAL認証成功！" -ForegroundColor Green

            # キャッシュに保存
            $expiresIn = ($token.ExpiresOn - [DateTimeOffset]::Now).TotalSeconds
            Save-TokenCache -ClientId $ClientId `
                           -AccessToken $token.AccessToken `
                           -RefreshToken "" `
                           -ExpiresIn $expiresIn

            return $token.AccessToken
        }
    }
    catch {
        Write-TokenDebug "MSAL認証エラー: $($_.Exception.Message)"
    }

    return $null
}

# Get Azure AD access token using IWA, cached token, or device code flow
function Get-AzureAdToken {
    param(
        [string]$TenantId,
        [string]$ClientId,
        [string]$Scope
    )

    Write-Host "[CallCloudApiAsync] Azure AD認証を開始します..."

    # 0. デバイスのAzure AD参加状態を確認
    $joinStatus = Test-AzureAdJoinStatus
    if ($joinStatus.IsJoined) {
        Write-Host "[CallCloudApiAsync] Azure AD参加デバイス検出 (UPN: $($joinStatus.UserPrincipalName))" -ForegroundColor Cyan
    }

    # 1. キャッシュされたトークンを確認
    $cached = Get-CachedToken -ClientId $ClientId
    if ($cached) {
        # 有効期限内のトークンがある場合
        try {
            $expiresAt = [DateTimeOffset]::Parse($cached.expires_at).LocalDateTime
        }
        catch {
            $expiresAt = [DateTime]::Parse($cached.expires_at)
        }
        if ($expiresAt -gt (Get-Date).AddMinutes(5)) {
            return $cached.access_token
        }

        # リフレッシュトークンで更新を試みる
        if ($cached.refresh_token) {
            $newToken = Refresh-AccessToken -TenantId $TenantId -ClientId $ClientId `
                                            -RefreshToken $cached.refresh_token -Scope $Scope
            if ($newToken) {
                return $newToken
            }
        }
    }

    # 2. ブラウザベース認証を試行（ユーザーが既にログイン済みなら自動）
    $browserToken = Get-TokenWithBrowser -TenantId $TenantId -ClientId $ClientId -Scope $Scope
    if ($browserToken) {
        return $browserToken
    }

    Write-Host "[CallCloudApiAsync] ブラウザ認証が利用できないため、デバイスコードフローを使用します" -ForegroundColor Yellow

    # 3. Device Code Flow で認証（フォールバック）
    Write-Host "[CallCloudApiAsync] デバイスコードフローで認証します..."

    try {
        # Request device code
        $deviceCodeUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/devicecode"
        $deviceCodeBody = @{
            client_id = $ClientId
            scope     = $Scope
        }

        $deviceCodeResponse = Invoke-RestMethod -Uri $deviceCodeUrl -Method Post -Body $deviceCodeBody -ErrorAction Stop

        # Display instructions to user
        Write-Host ""
        Write-Host "========================================" -ForegroundColor Yellow
        Write-Host "Azure AD 認証が必要です" -ForegroundColor Yellow
        Write-Host "========================================" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "1. ブラウザで以下のURLを開いてください:" -ForegroundColor Cyan
        Write-Host "   $($deviceCodeResponse.verification_uri)" -ForegroundColor White
        Write-Host ""
        Write-Host "2. 以下のコードを入力してください:" -ForegroundColor Cyan
        Write-Host "   $($deviceCodeResponse.user_code)" -ForegroundColor White -BackgroundColor DarkBlue
        Write-Host ""
        Write-Host "3. アカウントでサインインしてください" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "認証を待機中..." -ForegroundColor Gray

        # Poll for token
        $tokenUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/token"
        $tokenBody = @{
            grant_type  = "urn:ietf:params:oauth:grant-type:device_code"
            client_id   = $ClientId
            device_code = $deviceCodeResponse.device_code
        }

        $pollInterval = $deviceCodeResponse.interval
        if (-not $pollInterval) { $pollInterval = 5 }

        $maxAttempts = 60  # 5 minutes max wait
        $attempt = 0

        while ($attempt -lt $maxAttempts) {
            Start-Sleep -Seconds $pollInterval
            $attempt++

            try {
                $tokenResponse = Invoke-RestMethod -Uri $tokenUrl -Method Post -Body $tokenBody -ErrorAction Stop

                if ($tokenResponse.access_token) {
                    Write-Host ""
                    Write-Host "認証成功！" -ForegroundColor Green
                    Write-Host ""

                    # トークンをキャッシュに保存
                    Save-TokenCache -ClientId $ClientId `
                                   -AccessToken $tokenResponse.access_token `
                                   -RefreshToken $tokenResponse.refresh_token `
                                   -ExpiresIn $tokenResponse.expires_in

                    return $tokenResponse.access_token
                }
            }
            catch {
                $errorResponse = $_.ErrorDetails.Message | ConvertFrom-Json -ErrorAction SilentlyContinue

                if ($errorResponse.error -eq "authorization_pending") {
                    Write-Host "." -NoNewline
                    continue
                }
                elseif ($errorResponse.error -eq "slow_down") {
                    $pollInterval += 5
                    continue
                }
                elseif ($errorResponse.error -eq "expired_token") {
                    throw "認証がタイムアウトしました。再度実行してください。"
                }
                else {
                    throw "認証エラー: $($errorResponse.error_description)"
                }
            }
        }

        throw "認証がタイムアウトしました（5分経過）"
    }
    catch {
        throw "Azure AD認証に失敗しました: $($_.Exception.Message)"
    }
}

# ファイルをBase64に変換
function ConvertTo-Base64File {
    param([string]$FilePath)

    if (Test-Path $FilePath -PathType Leaf) {
        $bytes = [System.IO.File]::ReadAllBytes($FilePath)
        return [System.Convert]::ToBase64String($bytes)
    }
    return $null
}

# 拡張子からMIMEタイプを取得
function Get-MimeType {
    param([string]$Extension)

    $mimeTypes = @{
        ".pdf"  = "application/pdf"
        ".jpg"  = "image/jpeg"
        ".jpeg" = "image/jpeg"
        ".png"  = "image/png"
        ".gif"  = "image/gif"
        ".bmp"  = "image/bmp"
        ".tiff" = "image/tiff"
        ".tif"  = "image/tiff"
        ".webp" = "image/webp"
        ".doc"  = "application/msword"
        ".docx" = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ".xls"  = "application/vnd.ms-excel"
        ".xlsx" = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ".xlsm" = "application/vnd.ms-excel.sheet.macroEnabled.12"
        ".ppt"  = "application/vnd.ms-powerpoint"
        ".pptx" = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ".msg"  = "application/vnd.ms-outlook"
        ".eml"  = "message/rfc822"
        ".txt"  = "text/plain"
        ".log"  = "text/plain"
        ".csv"  = "text/csv"
        ".json" = "application/json"
        ".xml"  = "application/xml"
        ".zip"  = "application/zip"
        ".html" = "text/html"
        ".htm"  = "text/html"
    }

    $ext = $Extension.ToLower()
    if ($mimeTypes.ContainsKey($ext)) {
        return $mimeTypes[$ext]
    }
    return "application/octet-stream"
}

# フォルダ内のファイルをBase64配列として取得
function Get-FolderFilesAsBase64 {
    param([string]$FolderPath)

    $files = @()

    if (Test-Path $FolderPath -PathType Container) {
        Get-ChildItem -Path $FolderPath -File | ForEach-Object {
            $base64 = ConvertTo-Base64File -FilePath $_.FullName
            if ($base64) {
                $files += @{
                    "fileName"  = $_.Name
                    "extension" = $_.Extension.ToLower()
                    "mimeType"  = Get-MimeType -Extension $_.Extension
                    "base64"    = $base64
                }
            }
        }
    }

    return $files
}

# プロバイダーに応じたヘッダーを設定（Azure AD認証対応）
function Get-ApiHeaders {
    param(
        [string]$Provider,
        [string]$ApiKey,
        [string]$AuthHeader,
        [string]$AuthType = "functionsKey",
        [string]$TenantId = "",
        [string]$ClientId = "",
        [string]$Scope = ""
    )

    $headers = @{
        "Content-Type" = "application/json; charset=utf-8"
    }

    # Handle Azure AD authentication
    if ($AuthType.ToLower() -eq "azuread") {
        Write-Host "[CallCloudApiAsync] 認証方式: Azure AD"

        if (-not $TenantId -or -not $ClientId -or -not $Scope) {
            throw "Azure AD認証にはTenantId, ClientId, Scopeが必要です"
        }

        # Get Azure AD token
        $accessToken = Get-AzureAdToken -TenantId $TenantId -ClientId $ClientId -Scope $Scope
        $headers["Authorization"] = "Bearer $accessToken"

        Write-Host "[CallCloudApiAsync] Azure ADトークンをヘッダーに設定しました"
    }
    else {
        # Traditional API Key authentication
        Write-Host "[CallCloudApiAsync] 認証方式: Functions Key"

        switch ($Provider.ToUpper()) {
            "AZURE" {
                if ($AuthHeader -ne "") {
                    $headers[$AuthHeader] = $ApiKey
                } else {
                    $headers["x-functions-key"] = $ApiKey
                }
            }
            "GCP" {
                if ($AuthHeader -ne "") {
                    $headers[$AuthHeader] = $ApiKey
                } else {
                    $headers["Authorization"] = "Bearer $ApiKey"
                }
            }
            "AWS" {
                if ($AuthHeader -ne "") {
                    $headers[$AuthHeader] = $ApiKey
                } else {
                    $headers["x-api-key"] = $ApiKey
                }
            }
            default {
                if ($AuthHeader -ne "") {
                    $headers[$AuthHeader] = $ApiKey
                } else {
                    $headers["Authorization"] = $ApiKey
                }
            }
        }
    }

    return $headers
}

# ==============================================================================
# メイン処理
# ==============================================================================

try {
    Write-Host "============================================================"
    Write-Host "[CallCloudApiAsync] 非同期API呼び出し開始"
    Write-Host "============================================================"

    # 1. JSONファイルを読み込み
    Write-Host "[CallCloudApiAsync] JSONファイル読み込み: $JsonFilePath"
    $jsonContent = Get-Content -Path $JsonFilePath -Raw -Encoding UTF8
    $jsonObject = $jsonContent | ConvertFrom-Json

    # 配列形式を保証
    if ($jsonObject -isnot [System.Array]) {
        $jsonObject = @($jsonObject)
    }

    Write-Host "[CallCloudApiAsync] 処理対象: $($jsonObject.Count) 件"

    # 2. 証跡ファイルをBase64に変換
    Write-Host "[CallCloudApiAsync] 証跡ファイルを準備中..."
    $preparedItems = @()
    foreach ($item in $jsonObject) {
        $evidenceLink = $item.EvidenceLink

        if ($evidenceLink -and (Test-Path $evidenceLink -PathType Container)) {
            $evidenceFiles = Get-FolderFilesAsBase64 -FolderPath $evidenceLink
            $item | Add-Member -NotePropertyName "EvidenceFiles" -NotePropertyValue $evidenceFiles -Force
            Write-Host "[CallCloudApiAsync]   - ID: $($item.ID), 証跡: $($evidenceFiles.Count) ファイル"
        } else {
            $item | Add-Member -NotePropertyName "EvidenceFiles" -NotePropertyValue @() -Force
        }

        $preparedItems += $item
    }

    # 3. ヘッダー設定（Azure AD認証対応）
    $headers = Get-ApiHeaders -Provider $Provider -ApiKey $ApiKey -AuthHeader $AuthHeader `
        -AuthType $AuthType -TenantId $TenantId -ClientId $ClientId -Scope $Scope

    # 4. ジョブ送信（POST /api/evaluate/submit）- リトライ機能付き
    Write-Host "[CallCloudApiAsync] ジョブ送信中..."
    $submitUrl = "$Endpoint/submit"
    $bodyJson = $preparedItems | ConvertTo-Json -Depth 10 -Compress

    # 単一要素の場合、ConvertTo-Jsonはオブジェクトとして出力するため配列形式を強制
    if ($bodyJson -notmatch '^\s*\[') {
        $bodyJson = "[$bodyJson]"
    }

    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyJson)

    # リトライ設定
    $maxRetries = 3
    $retryDelay = 5
    $submitSuccess = $false
    $jobId = $null
    $estimatedTime = 0

    for ($retry = 1; $retry -le $maxRetries; $retry++) {
        try {
            $submitResponse = Invoke-WebRequest -Uri $submitUrl -Method Post -Headers $headers `
                -Body $bodyBytes -ContentType "application/json; charset=utf-8" `
                -UseBasicParsing -TimeoutSec 60

            $submitResult = $submitResponse.Content | ConvertFrom-Json

            if ($submitResult.error) {
                throw "ジョブ送信エラー: $($submitResult.message)"
            }

            $jobId = $submitResult.job_id
            $estimatedTime = $submitResult.estimated_time
            $submitSuccess = $true

            Write-Host "[CallCloudApiAsync] ジョブ送信完了"
            Write-Host "[CallCloudApiAsync]   - ジョブID: $jobId"
            Write-Host "[CallCloudApiAsync]   - 推定処理時間: $estimatedTime 秒"
            break
        }
        catch {
            $errorMsg = $_.Exception.Message
            if ($retry -lt $maxRetries) {
                Write-Host "[CallCloudApiAsync] ジョブ送信エラー（リトライ $retry/$maxRetries）: $errorMsg"
                Start-Sleep -Seconds $retryDelay
            } else {
                throw "ジョブ送信失敗（$maxRetries 回リトライ後）: $errorMsg"
            }
        }
    }

    # 5. ポーリング（GET /api/evaluate/status/{job_id}）
    Write-Host "[CallCloudApiAsync] 処理完了を待機中..."
    $statusUrl = "$Endpoint/status/$jobId"
    $startTime = Get-Date
    $maxWaitTime = [TimeSpan]::FromSeconds($TimeoutSec)
    $lastProgress = -1

    do {
        Start-Sleep -Seconds $PollingIntervalSec

        try {
            $statusResponse = Invoke-WebRequest -Uri $statusUrl -Method Get -Headers $headers `
                -UseBasicParsing -TimeoutSec 30

            $statusResult = $statusResponse.Content | ConvertFrom-Json
            $status = $statusResult.status
            $progress = $statusResult.progress
            $message = $statusResult.message

            # 進捗が変わった場合のみ表示
            if ($progress -ne $lastProgress) {
                Write-Host "[CallCloudApiAsync]   進捗: $progress% - $message"
                $lastProgress = $progress
            }
        }
        catch {
            Write-Host "[CallCloudApiAsync]   ステータス確認エラー（リトライ）: $($_.Exception.Message)"
        }

        # タイムアウトチェック
        $elapsed = (Get-Date) - $startTime
        if ($elapsed -gt $maxWaitTime) {
            throw "タイムアウト: 処理が $TimeoutSec 秒以内に完了しませんでした"
        }

    } while ($status -eq "pending" -or $status -eq "running")

    # 6. 結果取得（GET /api/evaluate/results/{job_id}）
    if ($status -eq "completed") {
        Write-Host "[CallCloudApiAsync] 処理完了。結果を取得中..."
        $resultsUrl = "$Endpoint/results/$jobId"

        try {
            $resultsResponse = Invoke-WebRequest -Uri $resultsUrl -Method Get -Headers $headers `
                -UseBasicParsing -TimeoutSec 60

            $resultsData = $resultsResponse.Content | ConvertFrom-Json

            if ($resultsData.error) {
                throw "結果取得エラー: $($resultsData.message)"
            }

            # 結果をファイルに保存
            $results = $resultsData.results

            # 配列形式を保証
            if ($null -eq $results) {
                $results = @()
            } elseif ($results -isnot [System.Array]) {
                $results = @($results)
            }

            $outputJson = $results | ConvertTo-Json -Depth 10 -Compress:$false

            # ConvertTo-Jsonが単一オブジェクトを配列でなくオブジェクトとして出力する場合の対応
            if ($results.Count -eq 1 -and $outputJson -notmatch '^\s*\[') {
                $outputJson = "[$outputJson]"
            }

            # 空配列の場合
            if ($results.Count -eq 0) {
                $outputJson = "[]"
            }

            $utf8NoBom = New-Object System.Text.UTF8Encoding $false
            [System.IO.File]::WriteAllText($OutputFilePath, $outputJson, $utf8NoBom)

            $elapsedTotal = ((Get-Date) - $startTime).TotalSeconds

            # 成功時はエラーをクリアして正常終了
            $Error.Clear()
            $global:LASTEXITCODE = 0

            # ログ出力（エラーを無視）
            try {
                Write-Host "[CallCloudApiAsync] 結果保存完了: $OutputFilePath"
                Write-Host "[CallCloudApiAsync] 処理件数: $($results.Count) 件"
                Write-Host "[CallCloudApiAsync] 総処理時間: $([math]::Round($elapsedTotal, 1)) 秒"
                Write-Host "============================================================"
            } catch { }

            # 正常終了（exit 0 を使用）
            exit 0
        }
        catch {
            throw "結果取得失敗: $($_.Exception.Message)"
        }
    }
    elseif ($status -eq "failed") {
        $errorMessage = $statusResult.error_message
        throw "ジョブ処理失敗: $errorMessage"
    }
    else {
        throw "予期しないステータス: $status"
    }

    # ここに到達した場合も正常終了
    $Error.Clear()
    $global:LASTEXITCODE = 0
    exit 0
}
catch {
    # エラー処理
    Write-Host "[CallCloudApiAsync] エラー発生: $($_.Exception.Message)" -ForegroundColor Red

    # エラー情報をファイルに保存
    $errorInfo = @{
        "error" = $true
        "message" = $_.Exception.Message
        "details" = $_.ToString()
    }

    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($OutputFilePath, ($errorInfo | ConvertTo-Json -Depth 5), $utf8NoBom)

    Write-Host "============================================================"
    exit 1
}

# スクリプト末尾でも正常終了を保証
$Error.Clear()
$global:LASTEXITCODE = 0
exit 0
