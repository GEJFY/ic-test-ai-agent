# Azure Functions ローカルテスト用スクリプト
# 使用方法: .\test.ps1

# テストデータ（日本語を含まないシンプルなJSON）
$testBody = '[{"ID":"IC-001","ControlDescription":"Access approval process","TestProcedure":"Check approval records","EvidenceLink":"","EvidenceFiles":[]}]'

# UTF-8バイト配列に変換
$bytes = [System.Text.Encoding]::UTF8.GetBytes($testBody)

Write-Host "=== Health Check ===" -ForegroundColor Cyan
try {
    $health = Invoke-RestMethod -Uri "http://localhost:7071/api/health" -Method GET
    Write-Host "Status: $($health.status)" -ForegroundColor Green
    Write-Host "Version: $($health.version)" -ForegroundColor Green
} catch {
    Write-Host "Health check failed: $($_.Exception.Message)" -ForegroundColor Red
}

Write-Host ""
Write-Host "=== Evaluate API Test ===" -ForegroundColor Cyan
try {
    $response = Invoke-RestMethod -Uri "http://localhost:7071/api/evaluate" -Method POST -Body $bytes -ContentType "application/json; charset=utf-8"

    Write-Host "Response:" -ForegroundColor Green
    $response | ConvertTo-Json -Depth 5
} catch {
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red

    # 詳細エラー情報
    if ($_.Exception.Response) {
        $reader = [System.IO.StreamReader]::new($_.Exception.Response.GetResponseStream())
        $errorBody = $reader.ReadToEnd()
        Write-Host "Error Details: $errorBody" -ForegroundColor Yellow
    }
}
