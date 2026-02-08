# deploy.ps1
# AWS Lambda deploy script

param(
    [Parameter(Mandatory=$true)]
    [string]$FunctionName,

    [Parameter(Mandatory=$false)]
    [string]$Region = "ap-northeast-1",

    [Parameter(Mandatory=$false)]
    [string]$RoleName = "lambda-ic-test-role",

    [Parameter(Mandatory=$false)]
    [int]$MemorySize = 1024,

    [Parameter(Mandatory=$false)]
    [int]$Timeout = 300,

    [Parameter(Mandatory=$false)]
    [switch]$CreateRole = $false,

    [Parameter(Mandatory=$false)]
    [switch]$SkipEnvSetup = $false
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$SrcDir = Join-Path $ProjectRoot "src"
$DeployDir = Join-Path $ScriptDir ".deploy"
$ZipPath = Join-Path $ScriptDir "deploy.zip"

Write-Host "=============================================="
Write-Host "AWS Lambda Deploy Script"
Write-Host "=============================================="
Write-Host "Function Name: $FunctionName"
Write-Host "Region: $Region"
Write-Host "Project Root: $ProjectRoot"
Write-Host ""

# 1. Check AWS CLI
Write-Host "[1/6] Checking AWS CLI..."
$awsVersion = aws --version 2>$null
if (-not $awsVersion) {
    Write-Error "AWS CLI is not installed."
    exit 1
}
Write-Host "      AWS CLI: $awsVersion"

$identityJson = aws sts get-caller-identity 2>$null
if (-not $identityJson) {
    Write-Error "Not authenticated. Run 'aws configure'"
    exit 1
}
$identity = $identityJson | ConvertFrom-Json
Write-Host "      Account: $($identity.Account)"
Write-Host "      User: $($identity.Arn)"
$AccountId = $identity.Account

# 2. Create IAM Role (optional)
if ($CreateRole) {
    Write-Host "[2/6] Creating IAM role..."

    $trustPolicyContent = '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"lambda.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
    $trustPolicyFile = Join-Path $env:TEMP "trust-policy.json"
    $trustPolicyContent | Out-File -FilePath $trustPolicyFile -Encoding ASCII

    $roleExists = $false
    try {
        $checkRole = aws iam get-role --role-name $RoleName 2>&1
        if ($LASTEXITCODE -eq 0) {
            $roleExists = $true
        }
    } catch {}

    if (-not $roleExists) {
        aws iam create-role --role-name $RoleName --assume-role-policy-document "file://$trustPolicyFile" --region $Region 2>&1 | Out-Null
        Write-Host "      Created role: $RoleName"

        aws iam attach-role-policy --role-name $RoleName --policy-arn "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole" 2>&1 | Out-Null
        aws iam attach-role-policy --role-name $RoleName --policy-arn "arn:aws:iam::aws:policy/AmazonBedrockFullAccess" 2>&1 | Out-Null
        aws iam attach-role-policy --role-name $RoleName --policy-arn "arn:aws:iam::aws:policy/AmazonTextractFullAccess" 2>&1 | Out-Null
        Write-Host "      Attached policies"
        Write-Host "      Waiting for role propagation..."
        Start-Sleep -Seconds 10
    } else {
        Write-Host "      Role already exists: $RoleName"
    }

    Remove-Item -Path $trustPolicyFile -Force -ErrorAction SilentlyContinue
}
else {
    Write-Host "[2/6] Skipping IAM role creation"
}

# 3. Create deploy package
Write-Host "[3/6] Creating deploy package..."

if (Test-Path $DeployDir) {
    Remove-Item -Path $DeployDir -Recurse -Force
}
New-Item -ItemType Directory -Path $DeployDir -Force | Out-Null

Copy-Item -Path (Join-Path $ScriptDir "lambda_handler.py") -Destination $DeployDir
Write-Host "      Copied: lambda_handler.py"

# Copy contents of src/ (not the src folder itself)
Get-ChildItem -Path $SrcDir | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $DeployDir -Recurse
}
Write-Host "      Copied: src/* (core/, infrastructure/)"

Write-Host "      Installing dependencies (for Linux/Lambda)..."
$ErrorActionPreference = "Continue"
# Install Linux x86_64 compatible packages for Lambda runtime
pip install -r (Join-Path $ScriptDir "requirements.txt") -t $DeployDir --platform manylinux2014_x86_64 --implementation cp --python-version 3.11 --only-binary=:all: --upgrade --quiet 2>&1 | Out-Null
$ErrorActionPreference = "Stop"
Write-Host "      Dependencies installed (Linux x86_64)"

# Clean up
Get-ChildItem -Path $DeployDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $DeployDir -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

# Create ZIP
if (Test-Path $ZipPath) {
    Remove-Item -Path $ZipPath -Force
}

Write-Host "      Creating ZIP file..."
Compress-Archive -Path "$DeployDir\*" -DestinationPath $ZipPath -Force
Write-Host "      Created: deploy.zip"

# 4. Deploy Lambda function
Write-Host "[4/6] Deploying Lambda function..."

$RoleArn = "arn:aws:iam::${AccountId}:role/${RoleName}"

$functionExists = $false
$ErrorActionPreference = "Continue"
$functionCheck = aws lambda get-function --function-name $FunctionName --region $Region 2>&1
if ($LASTEXITCODE -eq 0) {
    $functionExists = $true
}
$ErrorActionPreference = "Stop"

if ($functionExists) {
    Write-Host "      Updating existing function..."
    aws lambda update-function-code --function-name $FunctionName --zip-file "fileb://$ZipPath" --region $Region 2>$null

    Start-Sleep -Seconds 5
    aws lambda update-function-configuration --function-name $FunctionName --memory-size $MemorySize --timeout $Timeout --region $Region 2>$null
}
else {
    Write-Host "      Creating new function..."
    aws lambda create-function --function-name $FunctionName --runtime python3.11 --handler lambda_handler.handler --zip-file "fileb://$ZipPath" --role $RoleArn --memory-size $MemorySize --timeout $Timeout --region $Region 2>$null
}

Write-Host "      Deploy complete!"

# 5. Set environment variables
if (-not $SkipEnvSetup) {
    Write-Host "[5/6] Setting environment variables..."
    Start-Sleep -Seconds 5
    aws lambda update-function-configuration --function-name $FunctionName --environment "Variables={LLM_PROVIDER=AWS,OCR_PROVIDER=AWS,LOG_TO_FILE=false}" --region $Region 2>$null
    Write-Host "      Environment variables set"
}
else {
    Write-Host "[5/6] Skipping environment variables"
}

# 6. Cleanup
Write-Host "[6/6] Cleanup..."
if (Test-Path $DeployDir) {
    Remove-Item -Path $DeployDir -Recurse -Force
}
Write-Host "      Done"

# Complete
Write-Host ""
Write-Host "=============================================="
Write-Host "Deploy Complete!"
Write-Host "=============================================="
Write-Host ""
Write-Host "Lambda Function: $FunctionName"
Write-Host "Region: $Region"
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Create API Gateway for HTTP endpoint"
Write-Host "  2. Check environment variables in AWS Console"
Write-Host "  3. Enable Bedrock model access"
Write-Host ""
Write-Host "API Gateway creation command:"
Write-Host "  aws apigatewayv2 create-api --name ic-test-api --protocol-type HTTP --target arn:aws:lambda:${Region}:${AccountId}:function:${FunctionName}"
Write-Host ""
