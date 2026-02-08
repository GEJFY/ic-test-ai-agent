# deploy.ps1
# GCP Cloud Functions deploy script

param(
    [Parameter(Mandatory=$true)]
    [string]$ProjectId,

    [Parameter(Mandatory=$false)]
    [string]$Region = "asia-northeast1",

    [Parameter(Mandatory=$false)]
    [string]$FunctionName = "evaluate",

    [Parameter(Mandatory=$false)]
    [int]$MemoryMB = 1024,

    [Parameter(Mandatory=$false)]
    [int]$TimeoutSeconds = 540,

    [Parameter(Mandatory=$false)]
    [switch]$AllowUnauthenticated = $false,

    [Parameter(Mandatory=$false)]
    [switch]$SkipEnvSetup = $false,

    [Parameter(Mandatory=$false)]
    [switch]$DeployAll = $false
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)
$SrcDir = Join-Path $ProjectRoot "src"
$DeployDir = Join-Path $ScriptDir ".deploy"

Write-Host "=============================================="
Write-Host "GCP Cloud Functions Deploy Script"
Write-Host "=============================================="
Write-Host "Project ID: $ProjectId"
Write-Host "Region: $Region"
Write-Host "Function Name: $FunctionName"
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
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "aiplatform.googleapis.com"
)

foreach ($api in $apis) {
    gcloud services enable $api --quiet 2>$null
    Write-Host "      Enabled: $api"
}

# 3. Create deploy package
Write-Host "[3/5] Creating deploy package..."

if (Test-Path $DeployDir) {
    Remove-Item -Path $DeployDir -Recurse -Force
}

New-Item -ItemType Directory -Path $DeployDir -Force | Out-Null

$platformFiles = @("main.py", "requirements.txt", ".gcloudignore")

foreach ($file in $platformFiles) {
    $sourcePath = Join-Path $ScriptDir $file
    if (Test-Path $sourcePath) {
        Copy-Item -Path $sourcePath -Destination $DeployDir
        Write-Host "      Copied: $file"
    }
}

# Copy contents of src/ (not the src folder itself) so core/ and infrastructure/ are at root level
Get-ChildItem -Path $SrcDir | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination $DeployDir -Recurse
}
Write-Host "      Copied: src/* (core/, infrastructure/)"

Get-ChildItem -Path $DeployDir -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $DeployDir -Recurse -File -Filter "*.pyc" -ErrorAction SilentlyContinue | Remove-Item -Force -ErrorAction SilentlyContinue

Write-Host "      Package ready"

# 4. Deploy to Cloud Functions
Write-Host "[4/5] Deploying to Cloud Functions..."

$authFlag = if ($AllowUnauthenticated) { "--allow-unauthenticated" } else { "--no-allow-unauthenticated" }
$envVars = "LLM_PROVIDER=GCP,GCP_PROJECT_ID=$ProjectId,OCR_PROVIDER=NONE"

$functions = @(
    @{Name="evaluate"; EntryPoint="evaluate"; Methods="POST"},
    @{Name="health"; EntryPoint="health"; Methods="GET"},
    @{Name="config"; EntryPoint="config_status"; Methods="GET"}
)

if (-not $DeployAll) {
    $functions = @(@{Name=$FunctionName; EntryPoint=$FunctionName; Methods="POST,GET"})
}

foreach ($func in $functions) {
    Write-Host "      Deploying: $($func.Name)..."

    Push-Location $DeployDir

    $deployArgs = @(
        "functions", "deploy", $func.Name,
        "--gen2",
        "--runtime", "python311",
        "--trigger-http",
        $authFlag,
        "--entry-point", $func.EntryPoint,
        "--region", $Region,
        "--timeout", "${TimeoutSeconds}s",
        "--memory", "${MemoryMB}MB",
        "--set-env-vars", $envVars,
        "--source", ".",
        "--quiet"
    )

    & gcloud @deployArgs

    if ($LASTEXITCODE -ne 0) {
        Pop-Location
        Write-Error "Deploy failed: $($func.Name)"
        exit 1
    }

    Write-Host "      Done: $($func.Name)"
    Pop-Location
}

Write-Host "      Deploy complete!"

# 5. Cleanup
Write-Host "[5/5] Cleanup..."
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

Write-Host "Endpoints:"
foreach ($func in $functions) {
    $url = gcloud functions describe $func.Name --region $Region --format="value(serviceConfig.uri)" 2>$null
    if ($url) {
        Write-Host "  $($func.Name): $url"
    } else {
        Write-Host "  $($func.Name): https://$Region-$ProjectId.cloudfunctions.net/$($func.Name)"
    }
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Verify Vertex AI model access"
Write-Host "  2. Check environment variables in GCP Console"
Write-Host "  3. Verify IAM permissions (Vertex AI User role)"
Write-Host ""
