# setup-azure-ad-auth.ps1
# Azure AD認証のセットアップスクリプト
#
# 前提条件:
#   - Azure CLI (az) がインストール済み
#   - Azure サブスクリプションへのアクセス権限
#   - Function App が既にデプロイ済み
#
# 使用方法:
#   .\setup-azure-ad-auth.ps1 -FunctionAppName "func-ic-test-evaluation" -ResourceGroup "rg-ic-test"

param(
    [Parameter(Mandatory=$true)]
    [string]$FunctionAppName,

    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,

    [Parameter(Mandatory=$false)]
    [string]$GroupName = "IC-Test-Users",

    [Parameter(Mandatory=$false)]
    [string]$GroupDescription = "内部統制テストツールの利用者グループ"
)

Write-Host "============================================================"
Write-Host "Azure AD認証セットアップスクリプト"
Write-Host "============================================================"
Write-Host ""

# 1. Azure CLIでログイン確認
Write-Host "[Step 1] Azureログイン確認..."
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "Azureにログインしてください..."
    az login
    $account = az account show | ConvertFrom-Json
}
Write-Host "  ログイン済み: $($account.user.name)"
Write-Host "  サブスクリプション: $($account.name)"
Write-Host "  テナントID: $($account.tenantId)"
$TenantId = $account.tenantId
Write-Host ""

# 2. Function App の存在確認
Write-Host "[Step 2] Function App確認..."
$functionApp = az functionapp show --name $FunctionAppName --resource-group $ResourceGroup 2>$null | ConvertFrom-Json
if (-not $functionApp) {
    Write-Host "エラー: Function App '$FunctionAppName' が見つかりません" -ForegroundColor Red
    Write-Host "リソースグループ '$ResourceGroup' 内のFunction Appを確認してください"
    exit 1
}
Write-Host "  Function App: $($functionApp.name)"
Write-Host "  URL: https://$($functionApp.defaultHostName)"
Write-Host ""

# 3. App Registration作成（または既存を取得）
Write-Host "[Step 3] App Registration作成..."
$appName = "$FunctionAppName-auth"
$existingApp = az ad app list --display-name $appName 2>$null | ConvertFrom-Json

if ($existingApp -and $existingApp.Count -gt 0) {
    Write-Host "  既存のApp Registrationを使用: $appName"
    $appRegistration = $existingApp[0]
    $ClientId = $appRegistration.appId
} else {
    Write-Host "  新規App Registrationを作成: $appName"

    # App Registrationを作成
    $appRegistration = az ad app create `
        --display-name $appName `
        --sign-in-audience "AzureADMyOrg" `
        --enable-id-token-issuance true `
        --enable-access-token-issuance true `
        2>$null | ConvertFrom-Json

    if (-not $appRegistration) {
        Write-Host "エラー: App Registrationの作成に失敗しました" -ForegroundColor Red
        exit 1
    }

    $ClientId = $appRegistration.appId

    # API識別子URIを設定
    $identifierUri = "api://$ClientId"
    az ad app update --id $ClientId --identifier-uris $identifierUri 2>$null

    Write-Host "  App Registration作成完了"
}

Write-Host "  クライアントID: $ClientId"
Write-Host ""

# 3.5. Public Client Flow有効化とAPI Scope設定
Write-Host "[Step 3.5] Public Client FlowとAPIスコープ設定..."

# Public Client Flow (Device Code Flow用) を有効化
Write-Host "  Public Client Flowを有効化..."
az ad app update --id $ClientId --is-fallback-public-client true 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Public Client Flow有効化完了"
} else {
    Write-Host "警告: Public Client Flowの有効化に失敗しました" -ForegroundColor Yellow
}

# API Scope (user_impersonation) を追加
Write-Host "  APIスコープを設定..."
$scopeGuid = [guid]::NewGuid().ToString()
$oauth2PermissionScopes = @(
    @{
        adminConsentDescription = "内部統制テスト評価APIへのアクセスを許可します"
        adminConsentDisplayName = "IC Test Evaluation API へのアクセス"
        id = $scopeGuid
        isEnabled = $true
        type = "User"
        userConsentDescription = "内部統制テスト評価APIへのアクセスを許可します"
        userConsentDisplayName = "IC Test Evaluation API へのアクセス"
        value = "user_impersonation"
    }
) | ConvertTo-Json -Depth 5 -AsArray

$tempScopeFile = [System.IO.Path]::GetTempFileName()
$oauth2PermissionScopes | Out-File -FilePath $tempScopeFile -Encoding UTF8

# 既存のスコープを確認
$currentApp = az ad app show --id $ClientId 2>$null | ConvertFrom-Json
$hasScope = $false
if ($currentApp.api.oauth2PermissionScopes) {
    foreach ($scope in $currentApp.api.oauth2PermissionScopes) {
        if ($scope.value -eq "user_impersonation") {
            $hasScope = $true
            break
        }
    }
}

if (-not $hasScope) {
    az rest --method PATCH `
        --uri "https://graph.microsoft.com/v1.0/applications/$($currentApp.id)" `
        --headers "Content-Type=application/json" `
        --body "{`"api`":{`"oauth2PermissionScopes`":$oauth2PermissionScopes}}" `
        2>$null | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  APIスコープ(user_impersonation)追加完了"
    } else {
        Write-Host "警告: APIスコープの追加に失敗しました" -ForegroundColor Yellow
        Write-Host "  Azure Portalで手動設定してください:" -ForegroundColor Yellow
        Write-Host "    App Registration → APIの公開 → スコープの追加" -ForegroundColor Yellow
    }
} else {
    Write-Host "  APIスコープ(user_impersonation)は既に存在します"
}

Remove-Item $tempScopeFile -ErrorAction SilentlyContinue
Write-Host ""

# 3.6. リダイレクトURI設定（ブラウザ認証用）
Write-Host "[Step 3.6] リダイレクトURI設定（ブラウザ認証用）..."

# localhost:8400-8409のリダイレクトURIを設定
$redirectUris = @()
for ($port = 8400; $port -le 8409; $port++) {
    $redirectUris += "http://localhost:$port/callback"
}

# 現在のリダイレクトURIを取得
$currentApp = az ad app show --id $ClientId 2>$null | ConvertFrom-Json
$existingUris = @()
if ($currentApp.publicClient -and $currentApp.publicClient.redirectUris) {
    $existingUris = $currentApp.publicClient.redirectUris
}

# 必要なURIが存在するか確認
$missingUris = @()
foreach ($uri in $redirectUris) {
    if ($existingUris -notcontains $uri) {
        $missingUris += $uri
    }
}

if ($missingUris.Count -gt 0) {
    # 既存のURIと新しいURIをマージ
    $allUris = $existingUris + $missingUris | Sort-Object -Unique

    # JSON形式で更新
    $publicClientConfig = @{
        publicClient = @{
            redirectUris = $allUris
        }
    } | ConvertTo-Json -Depth 5 -Compress

    $tempRedirectFile = [System.IO.Path]::GetTempFileName()
    $publicClientConfig | Out-File -FilePath $tempRedirectFile -Encoding UTF8

    az rest --method PATCH `
        --uri "https://graph.microsoft.com/v1.0/applications/$($currentApp.id)" `
        --headers "Content-Type=application/json" `
        --body "@$tempRedirectFile" `
        2>$null | Out-Null

    Remove-Item $tempRedirectFile -ErrorAction SilentlyContinue

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  リダイレクトURI設定完了（localhost:8400-8409）"
    } else {
        Write-Host "警告: リダイレクトURIの設定に失敗しました" -ForegroundColor Yellow
        Write-Host "  Azure Portalで手動設定してください:" -ForegroundColor Yellow
        Write-Host "    App Registration → 認証 → プラットフォームを追加" -ForegroundColor Yellow
        Write-Host "    → モバイル アプリケーションとデスクトップ アプリケーション" -ForegroundColor Yellow
        Write-Host "    → カスタム リダイレクトURI: http://localhost:8400/callback 〜 8409" -ForegroundColor Yellow
    }
} else {
    Write-Host "  リダイレクトURIは既に設定済みです"
}
Write-Host ""

# 4. Service Principal作成（Enterprise Application）
Write-Host "[Step 4] Service Principal (Enterprise Application)確認..."
$servicePrincipal = az ad sp list --filter "appId eq '$ClientId'" 2>$null | ConvertFrom-Json

if (-not $servicePrincipal -or $servicePrincipal.Count -eq 0) {
    Write-Host "  Service Principalを作成中..."
    $servicePrincipal = az ad sp create --id $ClientId 2>$null | ConvertFrom-Json
    Write-Host "  Service Principal作成完了"
} else {
    $servicePrincipal = $servicePrincipal[0]
    Write-Host "  既存のService Principalを使用"
}
$ServicePrincipalId = $servicePrincipal.id
Write-Host "  Service Principal ID: $ServicePrincipalId"
Write-Host ""

# 5. ユーザー割り当てを必須に設定
Write-Host "[Step 5] ユーザー割り当て設定..."
az ad sp update --id $ServicePrincipalId --set "appRoleAssignmentRequired=true" 2>$null
Write-Host "  ユーザー割り当てを必須に設定しました"
Write-Host ""

# 6. Azure ADグループ作成
Write-Host "[Step 6] Azure ADグループ作成..."
$existingGroup = az ad group list --filter "displayName eq '$GroupName'" 2>$null | ConvertFrom-Json

if ($existingGroup -and $existingGroup.Count -gt 0) {
    Write-Host "  既存のグループを使用: $GroupName"
    $group = $existingGroup[0]
} else {
    Write-Host "  新規グループを作成: $GroupName"
    $group = az ad group create `
        --display-name $GroupName `
        --mail-nickname $GroupName `
        --description $GroupDescription `
        2>$null | ConvertFrom-Json

    if (-not $group) {
        Write-Host "警告: グループの作成に失敗しました（権限不足の可能性）" -ForegroundColor Yellow
        Write-Host "Azure Portalで手動でグループを作成してください" -ForegroundColor Yellow
        $group = $null
    } else {
        Write-Host "  グループ作成完了"
    }
}

if ($group) {
    $GroupId = $group.id
    Write-Host "  グループID: $GroupId"
}
Write-Host ""

# 7. 現在のユーザーをグループに追加
Write-Host "[Step 7] 現在のユーザーをグループに追加..."
$currentUser = az ad signed-in-user show 2>$null | ConvertFrom-Json
if ($currentUser -and $group) {
    $userId = $currentUser.id
    Write-Host "  ユーザー: $($currentUser.userPrincipalName)"

    # 既にメンバーかチェック
    $isMember = az ad group member check --group $GroupId --member-id $userId 2>$null | ConvertFrom-Json
    if ($isMember.value -eq $true) {
        Write-Host "  既にグループのメンバーです"
    } else {
        az ad group member add --group $GroupId --member-id $userId 2>$null
        if ($LASTEXITCODE -eq 0) {
            Write-Host "  グループに追加しました"
        } else {
            Write-Host "警告: グループへの追加に失敗しました" -ForegroundColor Yellow
        }
    }
}
Write-Host ""

# 8. グループをEnterprise Applicationに割り当て
Write-Host "[Step 8] グループをアプリに割り当て..."
if ($group) {
    # デフォルトのApp Role ID (00000000-0000-0000-0000-000000000000 = Default Access)
    $defaultRoleId = "00000000-0000-0000-0000-000000000000"

    # 割り当て確認
    $assignments = az rest --method GET `
        --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$ServicePrincipalId/appRoleAssignedTo" `
        2>$null | ConvertFrom-Json

    $isAssigned = $false
    if ($assignments -and $assignments.value) {
        foreach ($assignment in $assignments.value) {
            if ($assignment.principalId -eq $GroupId) {
                $isAssigned = $true
                break
            }
        }
    }

    if ($isAssigned) {
        Write-Host "  グループは既に割り当て済みです"
    } else {
        # グループを割り当て
        $body = @{
            principalId = $GroupId
            resourceId = $ServicePrincipalId
            appRoleId = $defaultRoleId
        } | ConvertTo-Json -Compress

        $result = az rest --method POST `
            --uri "https://graph.microsoft.com/v1.0/servicePrincipals/$ServicePrincipalId/appRoleAssignedTo" `
            --headers "Content-Type=application/json" `
            --body $body `
            2>$null

        if ($LASTEXITCODE -eq 0) {
            Write-Host "  グループをアプリに割り当てました"
        } else {
            Write-Host "警告: グループの割り当てに失敗しました" -ForegroundColor Yellow
            Write-Host "Azure Portalで手動で割り当ててください" -ForegroundColor Yellow
        }
    }
}
Write-Host ""

# 9. Function Appの認証設定
Write-Host "[Step 9] Function App認証設定..."
Write-Host "  認証プロバイダーを構成中..."

# 認証設定をAzure CLIで更新
$issuerUrl = "https://login.microsoftonline.com/$TenantId/v2.0"

# authsettingsV2を使用して認証を設定
$authConfig = @{
    properties = @{
        platform = @{
            enabled = $true
        }
        globalValidation = @{
            requireAuthentication = $true
            unauthenticatedClientAction = "Return401"
        }
        identityProviders = @{
            azureActiveDirectory = @{
                enabled = $true
                registration = @{
                    clientId = $ClientId
                    openIdIssuer = $issuerUrl
                }
                validation = @{
                    allowedAudiences = @(
                        "api://$ClientId",
                        $ClientId
                    )
                }
            }
        }
        login = @{
            tokenStore = @{
                enabled = $true
            }
        }
    }
}

$authConfigJson = $authConfig | ConvertTo-Json -Depth 10 -Compress
$tempFile = [System.IO.Path]::GetTempFileName()
$authConfigJson | Out-File -FilePath $tempFile -Encoding UTF8

az rest --method PUT `
    --uri "https://management.azure.com/subscriptions/$($account.id)/resourceGroups/$ResourceGroup/providers/Microsoft.Web/sites/$FunctionAppName/config/authsettingsV2?api-version=2021-02-01" `
    --headers "Content-Type=application/json" `
    --body "@$tempFile" `
    2>$null | Out-Null

Remove-Item $tempFile -ErrorAction SilentlyContinue

if ($LASTEXITCODE -eq 0) {
    Write-Host "  認証設定完了"
} else {
    Write-Host "警告: 認証設定の自動構成に失敗しました" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Azure Portalで手動設定してください:" -ForegroundColor Yellow
    Write-Host "  1. Function App → 認証 → IDプロバイダーの追加"
    Write-Host "  2. プロバイダー: Microsoft"
    Write-Host "  3. アプリの登録: 既存のアプリの登録を選択"
    Write-Host "  4. クライアントID: $ClientId"
}
Write-Host ""

# 10. 設定情報の出力
Write-Host "============================================================"
Write-Host "セットアップ完了！" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ""
Write-Host "以下の設定を setting.json に追加してください:"
Write-Host ""
Write-Host @"
{
    "api": {
        "provider": "AZURE",
        "authType": "azureAd",
        "endpoint": "https://$($functionApp.defaultHostName)/api/evaluate"
    },
    "azureAd": {
        "tenantId": "$TenantId",
        "clientId": "$ClientId",
        "scope": "api://$ClientId/user_impersonation openid offline_access"
    }
}
"@ -ForegroundColor Cyan

Write-Host ""
Write-Host "============================================================"
Write-Host "設定値サマリー"
Write-Host "============================================================"
Write-Host "  テナントID:     $TenantId"
Write-Host "  クライアントID: $ClientId"
Write-Host "  スコープ:       api://$ClientId/user_impersonation openid offline_access"
Write-Host "  グループ名:     $GroupName"
if ($GroupId) {
    Write-Host "  グループID:     $GroupId"
}
Write-Host "  Function App:   https://$($functionApp.defaultHostName)"
Write-Host ""
Write-Host "注意: グループに所属するユーザーのみAPIにアクセスできます"
Write-Host ""
