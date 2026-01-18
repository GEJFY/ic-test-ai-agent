# CallCloudApi.ps1
# Send JSON to cloud API and return results
# Supports parallel API calls for each item to maximize throughput
# Supported providers: AZURE, GCP, AWS
param(
    [Parameter(Mandatory=$true)]
    [string]$JsonFilePath,

    [Parameter(Mandatory=$true)]
    [string]$Endpoint,

    [Parameter(Mandatory=$true)]
    [string]$ApiKey,

    [Parameter(Mandatory=$true)]
    [string]$OutputFilePath,

    [Parameter(Mandatory=$true)]
    [string]$Provider,

    [Parameter(Mandatory=$false)]
    [string]$AuthHeader = "",

    [Parameter(Mandatory=$false)]
    [int]$TimeoutSec = 600
)

# Convert file to Base64
function ConvertTo-Base64File {
    param(
        [string]$FilePath
    )

    if (Test-Path $FilePath -PathType Leaf) {
        $bytes = [System.IO.File]::ReadAllBytes($FilePath)
        return [System.Convert]::ToBase64String($bytes)
    }
    return $null
}

# Get MIME type from extension
function Get-MimeType {
    param(
        [string]$Extension
    )

    $mimeTypes = @{
        ".pdf"  = "application/pdf"
        ".jpg"  = "image/jpeg"
        ".jpeg" = "image/jpeg"
        ".png"  = "image/png"
        ".gif"  = "image/gif"
        ".bmp"  = "image/bmp"
        ".tiff" = "image/tiff"
        ".tif"  = "image/tiff"
        ".webp" = "image/webp"
        ".doc"  = "application/msword"
        ".docx" = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ".xls"  = "application/vnd.ms-excel"
        ".xlsx" = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ".xlsm" = "application/vnd.ms-excel.sheet.macroEnabled.12"
        ".ppt"  = "application/vnd.ms-powerpoint"
        ".pptx" = "application/vnd.openxmlformats-officedocument.presentationml.presentation"
        ".msg"  = "application/vnd.ms-outlook"
        ".eml"  = "message/rfc822"
        ".txt"  = "text/plain"
        ".log"  = "text/plain"
        ".csv"  = "text/csv"
        ".json" = "application/json"
        ".xml"  = "application/xml"
        ".zip"  = "application/zip"
        ".html" = "text/html"
        ".htm"  = "text/html"
    }

    $ext = $Extension.ToLower()
    if ($mimeTypes.ContainsKey($ext)) {
        return $mimeTypes[$ext]
    }
    return "application/octet-stream"
}

# Get files from folder as Base64 array
function Get-FolderFilesAsBase64 {
    param(
        [string]$FolderPath
    )

    $files = @()

    if (Test-Path $FolderPath -PathType Container) {
        Get-ChildItem -Path $FolderPath -File | ForEach-Object {
            $base64 = ConvertTo-Base64File -FilePath $_.FullName
            if ($base64) {
                $files += @{
                    "fileName"  = $_.Name
                    "extension" = $_.Extension.ToLower()
                    "mimeType"  = Get-MimeType -Extension $_.Extension
                    "base64"    = $base64
                }
            }
        }
    }

    return $files
}

# Function to call API for a single item (used by parallel jobs)
function Invoke-SingleItemApi {
    param(
        [string]$ItemJson,
        [string]$Endpoint,
        [hashtable]$Headers,
        [int]$TimeoutSec
    )

    try {
        # Wrap single item in array (API expects array)
        $bodyContent = "[$ItemJson]"
        $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyContent)

        $webResponse = Invoke-WebRequest -Uri $Endpoint -Method Post -Headers $Headers -Body $bodyBytes -ContentType "application/json; charset=utf-8" -UseBasicParsing -TimeoutSec $TimeoutSec

        # Parse response and extract first item
        $responseContent = $webResponse.Content
        $responseArray = $responseContent | ConvertFrom-Json

        if ($responseArray -is [System.Array] -and $responseArray.Count -gt 0) {
            return $responseArray[0]
        }
        return $responseArray
    }
    catch {
        # Return error object
        return @{
            "ID" = "ERROR"
            "evaluationResult" = $false
            "judgmentBasis" = "API呼び出しエラー: $($_.Exception.Message)"
            "documentReference" = ""
            "fileName" = ""
            "evidenceFiles" = @()
            "_error" = $true
        }
    }
}

try {
    # Read JSON file
    $jsonContent = Get-Content -Path $JsonFilePath -Raw -Encoding UTF8
    $jsonObject = $jsonContent | ConvertFrom-Json

    # Ensure jsonObject is always an array
    if ($jsonObject -isnot [System.Array]) {
        $jsonObject = @($jsonObject)
    }

    # Process EvidenceLink folders and prepare items
    $preparedItems = @()
    foreach ($item in $jsonObject) {
        $evidenceLink = $item.EvidenceLink

        if ($evidenceLink -and (Test-Path $evidenceLink -PathType Container)) {
            $evidenceFiles = Get-FolderFilesAsBase64 -FolderPath $evidenceLink
            $item | Add-Member -NotePropertyName "EvidenceFiles" -NotePropertyValue $evidenceFiles -Force
        } else {
            $item | Add-Member -NotePropertyName "EvidenceFiles" -NotePropertyValue @() -Force
        }

        $preparedItems += $item
    }

    # Set headers by provider
    $headers = @{
        "Content-Type" = "application/json; charset=utf-8"
    }

    switch ($Provider.ToUpper()) {
        "AZURE" {
            if ($AuthHeader -ne "") {
                $headers[$AuthHeader] = $ApiKey
            } else {
                $headers["x-functions-key"] = $ApiKey
            }
        }
        "GCP" {
            if ($AuthHeader -ne "") {
                $headers[$AuthHeader] = $ApiKey
            } else {
                $headers["Authorization"] = "Bearer $ApiKey"
            }
        }
        "AWS" {
            if ($AuthHeader -ne "") {
                $headers[$AuthHeader] = $ApiKey
            } else {
                $headers["x-api-key"] = $ApiKey
            }
        }
        default {
            if ($AuthHeader -ne "") {
                $headers[$AuthHeader] = $ApiKey
            } else {
                $headers["Authorization"] = $ApiKey
            }
        }
    }

    # Parallel API calls using Start-Job (Windows PowerShell 5.1 compatible)
    $jobs = @()
    $results = @()

    Write-Host "[CallCloudApi] Starting parallel API calls for $($preparedItems.Count) items..."

    foreach ($item in $preparedItems) {
        $itemJson = $item | ConvertTo-Json -Depth 10 -Compress

        # Start background job for each item
        $job = Start-Job -ScriptBlock {
            param($ItemJson, $Endpoint, $Headers, $TimeoutSec)

            try {
                # Wrap single item in array (API expects array)
                $bodyContent = "[$ItemJson]"
                $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($bodyContent)

                $webResponse = Invoke-WebRequest -Uri $Endpoint -Method Post -Headers $Headers -Body $bodyBytes -ContentType "application/json; charset=utf-8" -UseBasicParsing -TimeoutSec $TimeoutSec

                # Parse response and extract first item
                $responseContent = $webResponse.Content
                $responseArray = $responseContent | ConvertFrom-Json

                if ($responseArray -is [System.Array] -and $responseArray.Count -gt 0) {
                    return $responseArray[0]
                }
                return $responseArray
            }
            catch {
                # Return error object with item ID if available
                $errorItem = $ItemJson | ConvertFrom-Json
                $itemId = if ($errorItem.ID) { $errorItem.ID } else { "UNKNOWN" }

                return @{
                    "ID" = $itemId
                    "evaluationResult" = $false
                    "executionPlanSummary" = ""
                    "judgmentBasis" = "API呼び出しエラー: $($_.Exception.Message)"
                    "documentReference" = ""
                    "fileName" = ""
                    "evidenceFiles" = @()
                    "_error" = $true
                }
            }
        } -ArgumentList $itemJson, $Endpoint, $headers, $TimeoutSec

        $jobs += $job
        Write-Host "[CallCloudApi] Started job for item: $($item.ID)"
    }

    # Wait for all jobs to complete
    Write-Host "[CallCloudApi] Waiting for all jobs to complete..."
    $jobs | Wait-Job -Timeout ($TimeoutSec + 60) | Out-Null

    # Collect results
    foreach ($job in $jobs) {
        if ($job.State -eq 'Completed') {
            $result = Receive-Job -Job $job
            $results += $result
            Write-Host "[CallCloudApi] Job completed: $($result.ID)"
        }
        elseif ($job.State -eq 'Running') {
            # Job timed out
            Stop-Job -Job $job
            $results += @{
                "ID" = "TIMEOUT"
                "evaluationResult" = $false
                "executionPlanSummary" = ""
                "judgmentBasis" = "タイムアウト: 処理時間が制限を超過しました"
                "documentReference" = ""
                "fileName" = ""
                "evidenceFiles" = @()
                "_error" = $true
            }
            Write-Host "[CallCloudApi] Job timed out"
        }
        else {
            # Job failed
            $errorInfo = Receive-Job -Job $job -ErrorAction SilentlyContinue
            $results += @{
                "ID" = "ERROR"
                "evaluationResult" = $false
                "executionPlanSummary" = ""
                "judgmentBasis" = "ジョブエラー: $($job.State)"
                "documentReference" = ""
                "fileName" = ""
                "evidenceFiles" = @()
                "_error" = $true
            }
            Write-Host "[CallCloudApi] Job failed: $($job.State)"
        }

        # Clean up job
        Remove-Job -Job $job -Force
    }

    # Sort results by ID to maintain order
    $sortedResults = $results | Sort-Object { $_.ID }

    # Convert results to JSON and save
    $outputJson = $sortedResults | ConvertTo-Json -Depth 10 -Compress:$false

    # Ensure array format for single item
    if ($sortedResults.Count -eq 1) {
        $outputJson = "[$outputJson]"
    }

    [System.IO.File]::WriteAllText($OutputFilePath, $outputJson, [System.Text.Encoding]::UTF8)

    Write-Host "[CallCloudApi] All jobs completed. Results saved to: $OutputFilePath"
    exit 0
}
catch {
    # Try to extract response body from WebException
    $responseBody = ""
    if ($_.Exception.Response) {
        try {
            $stream = $_.Exception.Response.GetResponseStream()
            $reader = New-Object System.IO.StreamReader($stream)
            $responseBody = $reader.ReadToEnd()
            $reader.Close()
            $stream.Close()
        } catch {
            $responseBody = "Failed to read response body"
        }
    }

    # Write error to output file with response body
    $errorInfo = @{
        "error" = $true
        "message" = $_.Exception.Message
        "details" = $_.ToString()
        "responseBody" = $responseBody
    }
    $errorInfo | ConvertTo-Json -Depth 5 | Out-File -FilePath $OutputFilePath -Encoding UTF8

    exit 1
}
