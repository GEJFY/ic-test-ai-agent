# deploy.ps1
# GCP Cloud Run deploy script (Docker)

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,

    [Parameter(Mandatory=$false)]
    [string]$Region = "asia-northeast1",

    [Parameter(Mandatory=$false)]
    [string]$ServiceName = "ic-test-ai-prod-api",

    [Parameter(Mandatory=$false)]
    [string]$ImageTag = "latest",

    [Parameter(Mandatory=$false)]
    [switch]$AllowUnauthenticated = $false
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$RepoName = "ic-test-ai-prod"
$ImageName = "ic-test-ai-agent"
$FullImageName = "${Region}-docker.pkg.dev/${ProjectId}/${RepoName}/${ImageName}:${ImageTag}"

Write-Host "=============================================="
Write-Host "GCP Cloud Run Deploy Script (Docker)"
Write-Host "=============================================="
Write-Host "Project ID: $ProjectId"
Write-Host "Region: $Region"
Write-Host "Service Name: $ServiceName"
Write-Host "Image: $FullImageName"
Write-Host "Project Root: $ProjectRoot"
Write-Host ""

# 1. Check gcloud CLI
Write-Host "[1/5] Checking gcloud CLI..."
$gcloudCheck = gcloud --version 2>$null
if (-not $gcloudCheck) {
    Write-Error "Google Cloud SDK is not installed."
    exit 1
}
Write-Host "      Google Cloud SDK: OK"

$account = gcloud config get-value account 2>$null
if (-not $account) {
    Write-Error "Not authenticated. Run 'gcloud auth login'"
    exit 1
}
Write-Host "      Account: $account"

gcloud config set project $ProjectId 2>$null

# 2. Enable APIs
Write-Host "[2/5] Enabling APIs..."

$apis = @(
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com"
)

foreach ($api in $apis) {
    gcloud services enable $api --quiet 2>$null
    Write-Host "      Enabled: $api"
}

# 3. Build Docker image
Write-Host "[3/5] Building Docker image..."

Push-Location $ProjectRoot

# Auth Docker to Artifact Registry
gcloud auth configure-docker "${Region}-docker.pkg.dev" --quiet

docker build -t $FullImageName .
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Error "Docker build failed."
    exit 1
}

docker tag $FullImageName "${Region}-docker.pkg.dev/${ProjectId}/${RepoName}/${ImageName}:latest"
Write-Host "      Build complete"

# 4. Push to Artifact Registry
Write-Host "[4/5] Pushing to Artifact Registry..."

docker push $FullImageName
docker push "${Region}-docker.pkg.dev/${ProjectId}/${RepoName}/${ImageName}:latest"

if ($LASTEXITCODE -ne 0) {
    Pop-Location
    Write-Error "Artifact Registry push failed."
    exit 1
}

Pop-Location
Write-Host "      Push complete"

# 5. Deploy to Cloud Run
Write-Host "[5/5] Deploying to Cloud Run..."

$authFlag = if ($AllowUnauthenticated) { "--allow-unauthenticated" } else { "--no-allow-unauthenticated" }

gcloud run deploy $ServiceName `
    --image $FullImageName `
    --region $Region `
    --platform managed `
    $authFlag `
    --quiet

if ($LASTEXITCODE -ne 0) {
    Write-Error "Cloud Run deployment failed."
    exit 1
}

Write-Host "      Deploy complete!"

# Complete
Write-Host ""
Write-Host "=============================================="
Write-Host "Deploy Complete!"
Write-Host "=============================================="
Write-Host ""

$url = gcloud run services describe $ServiceName --region $Region --format="value(status.url)" 2>$null
if ($url) {
    Write-Host "Endpoints:"
    Write-Host "  Health:   $url/health"
    Write-Host "  Evaluate: $url/evaluate"
    Write-Host ""
}

Write-Host "Next steps:"
Write-Host "  1. Verify Vertex AI model access"
Write-Host "  2. Check environment variables in Cloud Run Console"
Write-Host "  3. Verify IAM permissions (Vertex AI User role)"
Write-Host ""
