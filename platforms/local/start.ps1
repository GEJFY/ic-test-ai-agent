# start.ps1
# ローカルサーバー起動スクリプト

param(
    [Parameter(Mandatory=$false)]
    [int]$Port = 8000,

    [Parameter(Mandatory=$false)]
    [string]$Host = "0.0.0.0",

    [Parameter(Mandatory=$false)]
    [switch]$Production = $false
)

$ErrorActionPreference = "Stop"

# Configuration
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)

Write-Host "=============================================="
Write-Host "内部統制テスト評価AI - ローカルサーバー"
Write-Host "=============================================="
Write-Host "Project Root: $ProjectRoot"
Write-Host "Port: $Port"
Write-Host "Host: $Host"
Write-Host ""

# 1. Check Python
Write-Host "[1/4] Checking Python..."
$pythonCheck = python --version 2>&1
if (-not $pythonCheck) {
    Write-Error "Python is not installed."
    exit 1
}
Write-Host "      Python: $pythonCheck"

# 2. Check Ollama
Write-Host "[2/4] Checking Ollama..."
$ollamaUrl = $env:OLLAMA_BASE_URL
if (-not $ollamaUrl) {
    $ollamaUrl = "http://localhost:11434"
}

try {
    $response = Invoke-WebRequest -Uri "$ollamaUrl/api/tags" -TimeoutSec 5 -ErrorAction Stop
    $models = ($response.Content | ConvertFrom-Json).models
    Write-Host "      Ollama: Connected ($ollamaUrl)"
    Write-Host "      Models: $($models.Count) available"
    if ($models.Count -gt 0) {
        Write-Host "      - $($models[0].name)"
    }
} catch {
    Write-Host "      Ollama: Not running" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "WARNING: Ollamaが起動していません。" -ForegroundColor Yellow
    Write-Host "  1. Ollamaをインストール: https://ollama.ai" -ForegroundColor Yellow
    Write-Host "  2. モデルをダウンロード: ollama pull llama3.1:8b" -ForegroundColor Yellow
    Write-Host "  3. Ollamaを起動してから再実行してください" -ForegroundColor Yellow
    Write-Host ""
}

# 3. Check dependencies
Write-Host "[3/4] Checking dependencies..."
$requirementsPath = Join-Path $ScriptDir "requirements.txt"
if (Test-Path $requirementsPath) {
    pip install -r $requirementsPath --quiet 2>&1 | Out-Null
    Write-Host "      Dependencies: OK"
} else {
    Write-Host "      Requirements file not found, skipping..."
}

# 4. Start server
Write-Host "[4/4] Starting server..."
Write-Host ""
Write-Host "=============================================="
Write-Host "Server starting at: http://${Host}:${Port}"
Write-Host "API Documentation: http://${Host}:${Port}/docs"
Write-Host "Health Check: http://${Host}:${Port}/health"
Write-Host "=============================================="
Write-Host ""

# Set environment variables
$env:PYTHONPATH = $ProjectRoot + "\src"

Push-Location $ScriptDir

if ($Production) {
    # Production mode with Gunicorn
    Write-Host "Mode: Production (Gunicorn + Uvicorn Workers)"
    gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind "${Host}:${Port}"
} else {
    # Development mode with Uvicorn
    Write-Host "Mode: Development (Uvicorn with reload)"
    uvicorn main:app --host $Host --port $Port --reload
}

Pop-Location
