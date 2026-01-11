# Debug script to check JSON transformation
$jsonContent = Get-Content -Path 'C:/Users/goyos/AppData/Local/Temp/excel_to_api_input.json' -Raw -Encoding UTF8
$jsonObject = $jsonContent | ConvertFrom-Json

foreach ($item in $jsonObject) {
    $evidenceLink = $item.EvidenceLink

    if ($evidenceLink -and (Test-Path $evidenceLink -PathType Container)) {
        $item | Add-Member -NotePropertyName "EvidenceFiles" -NotePropertyValue @() -Force
    } else {
        $item | Add-Member -NotePropertyName "EvidenceFiles" -NotePropertyValue @() -Force
    }
}

$updatedJsonContent = $jsonObject | ConvertTo-Json -Depth 10 -Compress:$false
$updatedJsonContent | Out-File -FilePath 'C:/temp/debug_output.json' -Encoding UTF8
Write-Host "Output written to C:/temp/debug_output.json"
