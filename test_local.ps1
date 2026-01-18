# Test local API
$body = @'
[{"ID":"CLC-01","ControlDescription":"コンプライアンス研修実施","TestProcedure":"研修実施報告書を閲覧し、研修の実施状況を確認する","EvidenceFiles":[]}]
'@

$response = Invoke-RestMethod -Uri "http://localhost:7071/api/evaluate" -Method Post -Body ([System.Text.Encoding]::UTF8.GetBytes($body)) -ContentType "application/json; charset=utf-8"
Write-Host "Response:"
$response | ConvertTo-Json -Depth 10
