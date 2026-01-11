$headers = @{
    "Content-Type" = "application/json; charset=utf-8"
    "x-functions-key" = "l0YgJTc0nAIGmqsY6-sgtivx6Kt__MfbL6pVVud64O9vAzFum7WRTA=="
}
$body = '[{"ID":"CLC-01","ControlDescription":"Test","TestProcedure":"Test","EvidenceLink":"","EvidenceFiles":[]}]'
$response = Invoke-RestMethod -Uri "https://func-ic-test-evaluation.azurewebsites.net/api/evaluate" -Method Post -Headers $headers -Body $body -ContentType "application/json; charset=utf-8"
Write-Host "Response:"
$response | ConvertTo-Json -Depth 5
