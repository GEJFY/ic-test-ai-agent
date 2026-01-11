# CallCloudApi.ps1
# Send JSON to cloud API and return results
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
    [string]$AuthHeader = ""
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

try {
    # Read JSON file
    $jsonContent = Get-Content -Path $JsonFilePath -Raw -Encoding UTF8
    $jsonObject = $jsonContent | ConvertFrom-Json

    # Ensure jsonObject is always an array
    if ($jsonObject -isnot [System.Array]) {
        $jsonObject = @($jsonObject)
    }

    # Process EvidenceLink folders
    foreach ($item in $jsonObject) {
        $evidenceLink = $item.EvidenceLink

        if ($evidenceLink -and (Test-Path $evidenceLink -PathType Container)) {
            $evidenceFiles = Get-FolderFilesAsBase64 -FolderPath $evidenceLink
            $item | Add-Member -NotePropertyName "EvidenceFiles" -NotePropertyValue $evidenceFiles -Force
        } else {
            $item | Add-Member -NotePropertyName "EvidenceFiles" -NotePropertyValue @() -Force
        }
    }

    # Convert to JSON - use @() to ensure array output even for single item
    $updatedJsonContent = @($jsonObject) | ConvertTo-Json -Depth 10 -Compress:$false

    # Handle single item case - ConvertTo-Json doesn't wrap single object in array
    if ($jsonObject.Count -eq 1) {
        $updatedJsonContent = "[$updatedJsonContent]"
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

    # Call API using Invoke-WebRequest to preserve raw JSON encoding
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($updatedJsonContent)
    $webResponse = Invoke-WebRequest -Uri $Endpoint -Method Post -Headers $headers -Body $bodyBytes -ContentType "application/json; charset=utf-8" -UseBasicParsing

    # Get response content as UTF-8 string and write to file
    $responseContent = $webResponse.Content
    [System.IO.File]::WriteAllText($OutputFilePath, $responseContent, [System.Text.Encoding]::UTF8)

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
