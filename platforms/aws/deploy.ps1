# deploy.ps1
# AWS App Runner deploy script (Docker)

param(
    [Parameter(Mandatory=$true)]
    [string]$EcrRepoUrl,

    [Parameter(Mandatory=$false)]
    [string]$Region = "ap-northeast-1",

    [Parameter(Mandatory=$false)]
    [string]$ServiceArn = "",

    [Parameter(Mandatory=$false)]
    [string]$ImageTag = "latest"
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$ImageName = "ic-test-ai-agent"
$FullImageName = "${EcrRepoUrl}:${ImageTag}"

Write-Host "=============================================="
Write-Host "AWS App Runner Deploy Script (Docker)"
Write-Host "=============================================="
Write-Host "ECR Repository: $EcrRepoUrl"
Write-Host "Image Tag: $ImageTag"
Write-Host "Region: $Region"
Write-Host "Project Root: $ProjectRoot"
Write-Host ""

# 1. Check AWS CLI
Write-Host "[1/4] Checking AWS CLI..."
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
$AccountId = $identity.Account

# 2. Build Docker image
Write-Host "[2/4] Building Docker image..."

Push-Location $ProjectRoot

docker build -t $FullImageName .
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Error "Docker build failed."
    exit 1
}

docker tag $FullImageName "${EcrRepoUrl}:latest"
Write-Host "      Build complete"

# 3. Push to ECR
Write-Host "[3/4] Pushing to ECR..."

# Login to ECR
$loginPassword = aws ecr get-login-password --region $Region
$loginPassword | docker login --username AWS --password-stdin "$($EcrRepoUrl.Split('/')[0])"

if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Error "ECR login failed."
    exit 1
}

docker push $FullImageName
docker push "${EcrRepoUrl}:latest"

if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Error "ECR push failed."
    exit 1
}

Pop-Location
Write-Host "      Push complete"

# 4. Deploy to App Runner
Write-Host "[4/4] Deploying to App Runner..."

if ($ServiceArn -ne "") {
    aws apprunner start-deployment --service-arn $ServiceArn --region $Region
    if ($LASTEXITCODE -ne 0) {
        Write-Error "App Runner deployment failed."
        exit 1
    }
    Write-Host "      Deployment triggered"
} else {
    Write-Host "      No ServiceArn provided. Get it from Terraform:"
    Write-Host "        cd infrastructure/aws/terraform"
    Write-Host "        terraform output -raw app_runner_service_arn"
    Write-Host ""
    Write-Host "      Then run:"
    Write-Host "        aws apprunner start-deployment --service-arn <ARN> --region $Region"
}

# Complete
Write-Host ""
Write-Host "=============================================="
Write-Host "Deploy Complete!"
Write-Host "=============================================="
Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Check App Runner service status in AWS Console"
Write-Host "  2. Verify health endpoint"
Write-Host "  3. Check environment variables in App Runner"
Write-Host ""
