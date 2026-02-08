# setup-aws-cognito-auth.ps1
# AWS Cognito 認証のセットアップスクリプト
#
# 前提条件:
#   - AWS CLI がインストール済み
#   - AWS認証設定済み (aws configure)
#   - Lambda関数が既にデプロイ済み
#
# 使用方法:
#   .\setup-aws-cognito-auth.ps1 -FunctionName "ic-test-evaluate" -Region "ap-northeast-1"
#
# 注意:
#   - このスクリプトは認証を有効化する場合にのみ実行
#   - 認証なしの場合は API Gateway の認証設定をスキップ

param(
    [Parameter(Mandatory=$true)]
    [string]$FunctionName,

    [Parameter(Mandatory=$false)]
    [string]$Region = "ap-northeast-1",

    [Parameter(Mandatory=$false)]
    [string]$UserPoolName = "ic-test-users",

    [Parameter(Mandatory=$false)]
    [string]$AppClientName = "ic-test-client",

    [Parameter(Mandatory=$false)]
    [string]$ApiName = "ic-test-api"
)

$ErrorActionPreference = "Stop"

Write-Host "============================================================"
Write-Host "AWS Cognito 認証セットアップスクリプト"
Write-Host "============================================================"
Write-Host ""

# 1. AWS CLI確認
Write-Host "[Step 1] AWS CLI確認..."
try {
    $identity = aws sts get-caller-identity | ConvertFrom-Json
    Write-Host "  アカウント: $($identity.Account)"
    Write-Host "  ユーザー: $($identity.Arn)"
    $AccountId = $identity.Account
}
catch {
    Write-Error "AWS CLIが設定されていません。'aws configure' を実行してください。"
    exit 1
}
Write-Host ""

# 2. Cognito User Pool作成
Write-Host "[Step 2] Cognito User Pool作成..."

# 既存のUser Poolを確認
$existingPools = aws cognito-idp list-user-pools --max-results 60 --region $Region | ConvertFrom-Json
$userPool = $existingPools.UserPools | Where-Object { $_.Name -eq $UserPoolName }

if ($userPool) {
    Write-Host "  既存のUser Poolを使用: $UserPoolName"
    $UserPoolId = $userPool.Id
} else {
    Write-Host "  新規User Poolを作成: $UserPoolName"

    $poolResult = aws cognito-idp create-user-pool `
        --pool-name $UserPoolName `
        --policies "PasswordPolicy={MinimumLength=8,RequireUppercase=true,RequireLowercase=true,RequireNumbers=true,RequireSymbols=false}" `
        --auto-verified-attributes "email" `
        --username-attributes "email" `
        --mfa-configuration "OFF" `
        --region $Region | ConvertFrom-Json

    $UserPoolId = $poolResult.UserPool.Id
    Write-Host "  User Pool作成完了: $UserPoolId"
}
Write-Host "  User Pool ID: $UserPoolId"
Write-Host ""

# 3. App Client作成
Write-Host "[Step 3] App Client作成..."

$existingClients = aws cognito-idp list-user-pool-clients `
    --user-pool-id $UserPoolId `
    --max-results 60 `
    --region $Region | ConvertFrom-Json

$appClient = $existingClients.UserPoolClients | Where-Object { $_.ClientName -eq $AppClientName }

if ($appClient) {
    Write-Host "  既存のApp Clientを使用: $AppClientName"
    $ClientId = $appClient.ClientId
} else {
    Write-Host "  新規App Clientを作成: $AppClientName"

    $clientResult = aws cognito-idp create-user-pool-client `
        --user-pool-id $UserPoolId `
        --client-name $AppClientName `
        --explicit-auth-flows "ALLOW_USER_PASSWORD_AUTH" "ALLOW_REFRESH_TOKEN_AUTH" "ALLOW_USER_SRP_AUTH" `
        --generate-secret `
        --region $Region | ConvertFrom-Json

    $ClientId = $clientResult.UserPoolClient.ClientId
    $ClientSecret = $clientResult.UserPoolClient.ClientSecret
    Write-Host "  App Client作成完了"
}

# クライアント詳細を取得
$clientDetails = aws cognito-idp describe-user-pool-client `
    --user-pool-id $UserPoolId `
    --client-id $ClientId `
    --region $Region | ConvertFrom-Json

$ClientSecret = $clientDetails.UserPoolClient.ClientSecret

Write-Host "  Client ID: $ClientId"
if ($ClientSecret) {
    Write-Host "  Client Secret: ****(setting.jsonに保存してください)"
}
Write-Host ""

# 4. API Gateway作成（HTTP API）
Write-Host "[Step 4] API Gateway作成..."

# 既存のAPIを確認
$existingApis = aws apigatewayv2 get-apis --region $Region | ConvertFrom-Json
$api = $existingApis.Items | Where-Object { $_.Name -eq $ApiName }

if ($api) {
    Write-Host "  既存のAPIを使用: $ApiName"
    $ApiId = $api.ApiId
    $ApiEndpoint = $api.ApiEndpoint
} else {
    Write-Host "  新規HTTP APIを作成: $ApiName"

    # Lambda ARN
    $LambdaArn = "arn:aws:lambda:${Region}:${AccountId}:function:${FunctionName}"

    $apiResult = aws apigatewayv2 create-api `
        --name $ApiName `
        --protocol-type "HTTP" `
        --target $LambdaArn `
        --region $Region | ConvertFrom-Json

    $ApiId = $apiResult.ApiId
    $ApiEndpoint = $apiResult.ApiEndpoint

    Write-Host "  API作成完了"

    # Lambdaにインボーク権限を付与
    Write-Host "  Lambda権限を設定中..."
    aws lambda add-permission `
        --function-name $FunctionName `
        --statement-id "apigateway-invoke-${ApiId}" `
        --action "lambda:InvokeFunction" `
        --principal "apigateway.amazonaws.com" `
        --source-arn "arn:aws:execute-api:${Region}:${AccountId}:${ApiId}/*" `
        --region $Region 2>$null
}

Write-Host "  API ID: $ApiId"
Write-Host "  API Endpoint: $ApiEndpoint"
Write-Host ""

# 5. Cognito Authorizer作成
Write-Host "[Step 5] JWT Authorizer作成..."

# 既存のAuthorizerを確認
$existingAuthorizers = aws apigatewayv2 get-authorizers `
    --api-id $ApiId `
    --region $Region | ConvertFrom-Json

$authorizer = $existingAuthorizers.Items | Where-Object { $_.Name -eq "cognito-authorizer" }

$IssuerUrl = "https://cognito-idp.$Region.amazonaws.com/$UserPoolId"

if ($authorizer) {
    Write-Host "  既存のAuthorizerを使用"
    $AuthorizerId = $authorizer.AuthorizerId
} else {
    Write-Host "  新規JWT Authorizerを作成..."

    $authResult = aws apigatewayv2 create-authorizer `
        --api-id $ApiId `
        --name "cognito-authorizer" `
        --authorizer-type "JWT" `
        --identity-source '$request.header.Authorization' `
        --jwt-configuration "Issuer=$IssuerUrl,Audience=$ClientId" `
        --region $Region | ConvertFrom-Json

    $AuthorizerId = $authResult.AuthorizerId
    Write-Host "  Authorizer作成完了"
}

Write-Host "  Authorizer ID: $AuthorizerId"
Write-Host ""

# 6. ルートにAuthorizerを適用
Write-Host "[Step 6] APIルートに認証を適用..."

$routes = aws apigatewayv2 get-routes --api-id $ApiId --region $Region | ConvertFrom-Json

foreach ($route in $routes.Items) {
    if ($route.AuthorizerId -ne $AuthorizerId) {
        Write-Host "  ルート更新: $($route.RouteKey)"
        aws apigatewayv2 update-route `
            --api-id $ApiId `
            --route-id $route.RouteId `
            --authorization-type "JWT" `
            --authorizer-id $AuthorizerId `
            --region $Region 2>$null | Out-Null
    }
}
Write-Host "  認証設定完了"
Write-Host ""

# 7. テストユーザー作成案内
Write-Host "[Step 7] ユーザー管理..."
Write-Host "  ユーザーを追加するには以下のコマンドを使用："
Write-Host ""
Write-Host "  # ユーザー作成"
Write-Host "  aws cognito-idp admin-create-user \"
Write-Host "    --user-pool-id $UserPoolId \"
Write-Host "    --username user@example.com \"
Write-Host "    --user-attributes Name=email,Value=user@example.com \"
Write-Host "    --region $Region"
Write-Host ""
Write-Host "  # パスワード設定"
Write-Host "  aws cognito-idp admin-set-user-password \"
Write-Host "    --user-pool-id $UserPoolId \"
Write-Host "    --username user@example.com \"
Write-Host "    --password 'YourPassword123' \"
Write-Host "    --permanent \"
Write-Host "    --region $Region"
Write-Host ""

# 8. 設定情報の出力
Write-Host "============================================================"
Write-Host "セットアップ完了！" -ForegroundColor Green
Write-Host "============================================================"
Write-Host ""
Write-Host "以下の設定を setting.json に追加してください:"
Write-Host ""

$settingJson = @"
{
    "api": {
        "provider": "AWS",
        "authType": "cognito",
        "endpoint": "$ApiEndpoint"
    },
    "cognito": {
        "userPoolId": "$UserPoolId",
        "clientId": "$ClientId",
        "clientSecret": "$ClientSecret",
        "region": "$Region"
    }
}
"@

Write-Host $settingJson -ForegroundColor Cyan

Write-Host ""
Write-Host "============================================================"
Write-Host "設定値サマリー"
Write-Host "============================================================"
Write-Host "  User Pool ID:   $UserPoolId"
Write-Host "  Client ID:      $ClientId"
if ($ClientSecret) {
    Write-Host "  Client Secret:  $ClientSecret"
}
Write-Host "  API Endpoint:   $ApiEndpoint"
Write-Host "  Issuer URL:     $IssuerUrl"
Write-Host "  Region:         $Region"
Write-Host ""
Write-Host "============================================================"
Write-Host "認証フロー"
Write-Host "============================================================"
Write-Host ""
Write-Host "1. ユーザー認証（トークン取得）:"
Write-Host '   $authResult = aws cognito-idp initiate-auth \'
Write-Host "     --auth-flow USER_PASSWORD_AUTH \"
Write-Host "     --client-id $ClientId \"
Write-Host '     --auth-parameters USERNAME=user@example.com,PASSWORD=YourPassword \'
Write-Host "     --region $Region"
Write-Host ""
Write-Host "2. API呼び出し:"
Write-Host '   $token = $authResult.AuthenticationResult.IdToken'
Write-Host '   Invoke-RestMethod -Uri "$ApiEndpoint/evaluate" -Headers @{Authorization="Bearer $token"}'
Write-Host ""
