# CallCloudApi.ps1
# Send JSON to cloud API and return results
# Supports parallel API calls for each item to maximize throughput
# Supported providers: AZURE, GCP, AWS
# Supports Azure AD authentication for enhanced security
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
    [int]$TimeoutSec = 600,

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

# Convert file to Base64
function ConvertTo-Base64File {
    param(
        [string]$FilePath
    )

    if (Test-Path $FilePath -PathType Leaf) {
        $bytes = [System.IO.File]::ReadAllBytes($FilePath)
        return [System.Convert]::ToBase64String($bytes)
    }
    return $null
}

# Get MIME type from extension
function Get-MimeType {
    param(
        [string]$Extension
    )

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
            Write-Host "[CallCloudApi] キャッシュされたトークンを使用します（残り: ${remainingMinutes}分）" -ForegroundColor Green
            return $cache
        }

        Write-TokenDebug "トークン有効期限切れまたは間近"

        # 有効期限切れだがリフレッシュトークンがある場合
        if ($cache.refresh_token) {
            Write-Host "[CallCloudApi] トークンの有効期限が切れています。リフレッシュを試みます..."
            return $cache
        }

        Write-TokenDebug "リフレッシュトークンなし"
    }
    catch {
        Write-Host "[CallCloudApi] キャッシュの読み込みに失敗: $($_.Exception.Message)" -ForegroundColor Yellow
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
        Write-Host "[CallCloudApi] トークンをキャッシュに保存しました（有効期限: $($expiresAt.ToString('HH:mm:ss'))）" -ForegroundColor Green
        Write-TokenDebug "キャッシュ保存先: $($script:TokenCachePath)"
    }
    catch {
        Write-Host "[CallCloudApi] キャッシュの保存に失敗: $($_.Exception.Message)" -ForegroundColor Yellow
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

            Write-Host "[CallCloudApi] トークンのリフレッシュに成功しました" -ForegroundColor Green
            return $response.access_token
        }
    }
    catch {
        Write-Host "[CallCloudApi] トークンのリフレッシュに失敗: $($_.Exception.Message)" -ForegroundColor Yellow
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
# ユーザーが既にブラウザでログイン済みの場合、ほぼ自動で認証完了
function Get-TokenWithBrowser {
    param(
        [string]$TenantId,
        [string]$ClientId,
        [string]$Scope
    )

    Write-Host "[CallCloudApi] ブラウザ認証を試行中..." -ForegroundColor Cyan

    # PKCE用のコード生成
    $codeVerifier = New-PkceCodeVerifier
    $codeChallenge = New-PkceCodeChallenge -CodeVerifier $codeVerifier

    # ランダムなポートを選択（8400-8499の範囲）
    $port = Get-Random -Minimum 8400 -Maximum 8500
    $redirectUri = "http://localhost:$port/"

    # 認証URLの構築
    $authUrl = "https://login.microsoftonline.com/$TenantId/oauth2/v2.0/authorize?" +
               "client_id=$ClientId" +
               "&response_type=code" +
               "&redirect_uri=$([Uri]::EscapeDataString($redirectUri))" +
               "&scope=$([Uri]::EscapeDataString($Scope))" +
               "&code_challenge=$codeChallenge" +
               "&code_challenge_method=S256" +
               "&prompt=none"  # サイレント認証を試行

    try {
        # HTTPリスナーを起動
        $listener = New-Object System.Net.HttpListener
        $listener.Prefixes.Add($redirectUri)
        $listener.Start()

        Write-TokenDebug "HTTPリスナー起動: $redirectUri"

        # ブラウザを開く（サイレントモード）
        Start-Process $authUrl

        # タイムアウト設定（10秒でサイレント認証の結果を待つ）
        $asyncResult = $listener.BeginGetContext($null, $null)
        $completed = $asyncResult.AsyncWaitHandle.WaitOne(10000)

        if (-not $completed) {
            $listener.Stop()
            Write-TokenDebug "サイレント認証タイムアウト - インタラクティブ認証にフォールバック"

            # サイレント認証失敗時は prompt=select_account で再試行
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

            Write-Host "[CallCloudApi] ブラウザでAzure ADにログインしてください..." -ForegroundColor Yellow
            Start-Process $authUrl

            # インタラクティブ認証は60秒待機
            $asyncResult = $listener.BeginGetContext($null, $null)
            $completed = $asyncResult.AsyncWaitHandle.WaitOne(60000)

            if (-not $completed) {
                $listener.Stop()
                Write-TokenDebug "インタラクティブ認証タイムアウト"
                return $null
            }
        }

        # コールバックを受信
        $context = $listener.EndGetContext($asyncResult)
        $request = $context.Request
        $response = $context.Response

        # クエリパラメータからコードを取得
        $queryString = $request.Url.Query
        Write-TokenDebug "コールバック受信: $queryString"

        # 成功ページを返す
        $responseHtml = @"
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>認証完了</title></head>
<body style="font-family: sans-serif; text-align: center; padding: 50px;">
<h1 style="color: green;">&#x2713; 認証が完了しました</h1>
<p>このウィンドウを閉じてExcelに戻ってください。</p>
<script>setTimeout(function(){ window.close(); }, 2000);</script>
</body>
</html>
"@
        $buffer = [System.Text.Encoding]::UTF8.GetBytes($responseHtml)
        $response.ContentLength64 = $buffer.Length
        $response.ContentType = "text/html; charset=utf-8"
        $response.OutputStream.Write($buffer, 0, $buffer.Length)
        $response.OutputStream.Close()
        $listener.Stop()

        # 認証コードを抽出
        if ($queryString -match "code=([^&]+)") {
            $authCode = [Uri]::UnescapeDataString($matches[1])
            Write-TokenDebug "認証コード取得成功"

            # トークンエンドポイントでアクセストークンを取得
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
                Write-Host "[CallCloudApi] ブラウザ認証成功！" -ForegroundColor Green

                # キャッシュに保存
                Save-TokenCache -ClientId $ClientId `
                               -AccessToken $tokenResponse.access_token `
                               -RefreshToken $tokenResponse.refresh_token `
                               -ExpiresIn $tokenResponse.expires_in

                return $tokenResponse.access_token
            }
        }
        elseif ($queryString -match "error=([^&]+)") {
            $authError = [Uri]::UnescapeDataString($matches[1])
            $errorDesc = if ($queryString -match "error_description=([^&]+)") { [Uri]::UnescapeDataString($matches[1]) } else { "" }
            Write-TokenDebug "認証エラー: $authError - $errorDesc"
        }
    }
    catch {
        Write-TokenDebug "ブラウザ認証エラー: $($_.Exception.Message)"
        if ($listener -and $listener.IsListening) {
            $listener.Stop()
        }
    }

    return $null
}

# MSAL.PSモジュールを使用したIWA認証（モジュールがある場合） - 削除予定、互換性のため残す
function Get-TokenWithMSAL {
    param(
        [string]$TenantId,
        [string]$ClientId,
        [string]$Scope,
        [string]$UserPrincipalName
    )

    # MSAL.PSは使用しない（外部依存を避ける）
    return $null

    # MSAL.PSモジュールの確認
    if (-not (Get-Module -ListAvailable -Name MSAL.PS)) {
        Write-TokenDebug "MSAL.PSモジュールがインストールされていません"
        return $null
    }

    try {
        Import-Module MSAL.PS -ErrorAction Stop
        Write-Host "[CallCloudApi] MSAL.PSモジュールを使用してサイレント認証を試行中..." -ForegroundColor Cyan

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
                Write-Host "[CallCloudApi] 統合Windows認証（IWA）を試行中..." -ForegroundColor Cyan
                $token = Get-MsalToken -ClientId $ClientId -TenantId $TenantId -Scopes $Scope `
                                       -IntegratedWindowsAuth -LoginHint $UserPrincipalName -ErrorAction Stop
            }
            catch {
                Write-TokenDebug "IWA認証失敗: $($_.Exception.Message)"
            }
        }

        if ($token -and $token.AccessToken) {
            Write-Host "[CallCloudApi] MSAL認証成功！" -ForegroundColor Green

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

    Write-Host "[CallCloudApi] Azure AD認証を開始します..."

    # 0. デバイスのAzure AD参加状態を確認
    $joinStatus = Test-AzureAdJoinStatus
    if ($joinStatus.IsJoined) {
        Write-Host "[CallCloudApi] Azure AD参加デバイス検出 (UPN: $($joinStatus.UserPrincipalName))" -ForegroundColor Cyan
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

    Write-Host "[CallCloudApi] ブラウザ認証が利用できないため、デバイスコードフローを使用します" -ForegroundColor Yellow

    # 3. Device Code Flow で認証（フォールバック）
    Write-Host "[CallCloudApi] デバイスコードフローで認証します..."

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

# Get files from folder as Base64 array
function Get-FolderFilesAsBase64 {
    param(
        [string]$FolderPath
    )

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

# Function to call API for a single item (used by parallel jobs)
function Invoke-SingleItemApi {
    param(
        [string]$ItemJson,
        [string]$Endpoint,
        [hashtable]$Headers,
        [int]$TimeoutSec
    )

    try {
        # Wrap single item in array (API expects array)
        $bodyContent = "[$ItemJson]"
        $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyContent)

        $webResponse = Invoke-WebRequest -Uri $Endpoint -Method Post -Headers $Headers -Body $bodyBytes -ContentType "application/json; charset=utf-8" -UseBasicParsing -TimeoutSec $TimeoutSec

        # Parse response and extract first item
        $responseContent = $webResponse.Content
        $responseArray = $responseContent | ConvertFrom-Json

        if ($responseArray -is [System.Array] -and $responseArray.Count -gt 0) {
            return $responseArray[0]
        }
        return $responseArray
    }
    catch {
        # Return error object
        return @{
            "ID" = "ERROR"
            "evaluationResult" = $false
            "judgmentBasis" = "API Error: $($_.Exception.Message)"
            "documentReference" = ""
            "fileName" = ""
            "evidenceFiles" = @()
            "_error" = $true
        }
    }
}

try {
    # Read JSON file
    $jsonContent = Get-Content -Path $JsonFilePath -Raw -Encoding UTF8
    $jsonObject = $jsonContent | ConvertFrom-Json

    # Ensure jsonObject is always an array
    if ($jsonObject -isnot [System.Array]) {
        $jsonObject = @($jsonObject)
    }

    # Process EvidenceLink folders and prepare items
    $preparedItems = @()
    foreach ($item in $jsonObject) {
        $evidenceLink = $item.EvidenceLink

        if ($evidenceLink -and (Test-Path $evidenceLink -PathType Container)) {
            $evidenceFiles = Get-FolderFilesAsBase64 -FolderPath $evidenceLink
            $item | Add-Member -NotePropertyName "EvidenceFiles" -NotePropertyValue $evidenceFiles -Force
        } else {
            $item | Add-Member -NotePropertyName "EvidenceFiles" -NotePropertyValue @() -Force
        }

        $preparedItems += $item
    }

    # Set headers by provider and auth type
    $headers = @{
        "Content-Type" = "application/json; charset=utf-8"
    }

    # Handle Azure AD authentication
    if ($AuthType.ToLower() -eq "azuread") {
        Write-Host "[CallCloudApi] 認証方式: Azure AD"

        if (-not $TenantId -or -not $ClientId -or -not $Scope) {
            throw "Azure AD認証にはTenantId, ClientId, Scopeが必要です"
        }

        # Get Azure AD token
        $accessToken = Get-AzureAdToken -TenantId $TenantId -ClientId $ClientId -Scope $Scope
        $headers["Authorization"] = "Bearer $accessToken"

        Write-Host "[CallCloudApi] Azure ADトークンをヘッダーに設定しました"
    }
    else {
        # Traditional API Key authentication
        Write-Host "[CallCloudApi] 認証方式: Functions Key"

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

    # Parallel API calls using Start-Job (Windows PowerShell 5.1 compatible)
    $jobs = @()
    $results = @()

    Write-Host "[CallCloudApi] Starting parallel API calls for $($preparedItems.Count) items..."

    foreach ($item in $preparedItems) {
        $itemJson = $item | ConvertTo-Json -Depth 10 -Compress

        # Start background job for each item
        $job = Start-Job -ScriptBlock {
            param($ItemJson, $Endpoint, $Headers, $TimeoutSec)

            try {
                # Wrap single item in array (API expects array)
                $bodyContent = "[$ItemJson]"
                $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyContent)

                $webResponse = Invoke-WebRequest -Uri $Endpoint -Method Post -Headers $Headers -Body $bodyBytes -ContentType "application/json; charset=utf-8" -UseBasicParsing -TimeoutSec $TimeoutSec

                # Parse response and extract first item
                $responseContent = $webResponse.Content
                $responseArray = $responseContent | ConvertFrom-Json

                if ($responseArray -is [System.Array] -and $responseArray.Count -gt 0) {
                    return $responseArray[0]
                }
                return $responseArray
            }
            catch {
                # Return error object with item ID if available
                $errorItem = $ItemJson | ConvertFrom-Json
                $itemId = if ($errorItem.ID) { $errorItem.ID } else { "UNKNOWN" }

                return @{
                    "ID" = $itemId
                    "evaluationResult" = $false
                    "executionPlanSummary" = ""
                    "judgmentBasis" = "API Error: $($_.Exception.Message)"
                    "documentReference" = ""
                    "fileName" = ""
                    "evidenceFiles" = @()
                    "_error" = $true
                }
            }
        } -ArgumentList $itemJson, $Endpoint, $headers, $TimeoutSec

        $jobs += $job
        Write-Host "[CallCloudApi] Started job for item: $($item.ID)"
    }

    # Wait for all jobs to complete
    Write-Host "[CallCloudApi] Waiting for all jobs to complete..."
    $jobs | Wait-Job -Timeout ($TimeoutSec + 60) | Out-Null

    # Collect results
    foreach ($job in $jobs) {
        if ($job.State -eq 'Completed') {
            $result = Receive-Job -Job $job
            $results += $result
            Write-Host "[CallCloudApi] Job completed: $($result.ID)"
        }
        elseif ($job.State -eq 'Running') {
            # Job timed out
            Stop-Job -Job $job
            $results += @{
                "ID" = "TIMEOUT"
                "evaluationResult" = $false
                "executionPlanSummary" = ""
                "judgmentBasis" = "Timeout: Processing time exceeded the limit"
                "documentReference" = ""
                "fileName" = ""
                "evidenceFiles" = @()
                "_error" = $true
            }
            Write-Host "[CallCloudApi] Job timed out"
        }
        else {
            # Job failed
            $errorInfo = Receive-Job -Job $job -ErrorAction SilentlyContinue
            $results += @{
                "ID" = "ERROR"
                "evaluationResult" = $false
                "executionPlanSummary" = ""
                "judgmentBasis" = "Job Error: $($job.State)"
                "documentReference" = ""
                "fileName" = ""
                "evidenceFiles" = @()
                "_error" = $true
            }
            Write-Host "[CallCloudApi] Job failed: $($job.State)"
        }

        # Clean up job
        Remove-Job -Job $job -Force
    }

    # Sort results by ID to maintain order
    $sortedResults = $results | Sort-Object { $_.ID }

    # Convert results to JSON and save
    $outputJson = $sortedResults | ConvertTo-Json -Depth 10 -Compress:$false

    # Ensure array format for single item
    if ($sortedResults.Count -eq 1) {
        $outputJson = "[$outputJson]"
    }

    [System.IO.File]::WriteAllText($OutputFilePath, $outputJson, [System.Text.Encoding]::UTF8)

    Write-Host "[CallCloudApi] All jobs completed. Results saved to: $OutputFilePath"
    exit 0
}
catch {
    # Try to extract response body from WebException
    $responseBody = ""
    if ($_.Exception.Response) {
        try {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $responseBody = $reader.ReadToEnd()
            $reader.Close()
            $stream.Close()
        } catch {
            $responseBody = "Failed to read response body"
        }
    }

    # Write error to output file with response body
    $errorInfo = @{
        "error" = $true
        "message" = $_.Exception.Message
        "details" = $_.ToString()
        "responseBody" = $responseBody
    }
    # Use UTF8 without BOM for proper encoding
    $utf8NoBom = New-Object System.Text.UTF8Encoding $false
    [System.IO.File]::WriteAllText($OutputFilePath, ($errorInfo | ConvertTo-Json -Depth 5), $utf8NoBom)

    exit 1
}
