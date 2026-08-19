# Upload xbar5090 files to GitHub using the REST Contents API.
#
# This script is intentionally NOT run automatically. It is the prepared
# "upload with API" path for after the user confirms and provides the 3DMark
# screenshot.
#
# Requirements:
#   - gh CLI authenticated with repo scope (gh auth status)
#   - Run from the project root:
#       powershell -ExecutionPolicy Bypass -File scripts/upload_github_api.ps1
#
# Optional:
#   -ScreenshotPath C:\path\to\3dmark.png
#     Uploads the screenshot to docs/images/hall-of-fame.png and inserts it
#     into README.md / README.zh-CN.md under a prominent Hall of Fame section.

param(
    [string]$SourceDir = (Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) 'xbar5090-upload'),
    [string]$Repo = 'SHANAjam/rtx5090-xbar-control',
    [string]$Branch = 'main',
    [string]$ScreenshotPath = '',
    [switch]$WhatIf
)

$ErrorActionPreference = 'Stop'

if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'gh CLI is required. Install GitHub CLI and run "gh auth login".'
}

gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'gh is not authenticated. Run "gh auth login" first.'
}

if (-not (Test-Path $SourceDir)) {
    throw "Source directory not found: $SourceDir"
}

function Get-ContentSha([string]$path) {
    $oldEAP = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $out = & gh api "repos/$Repo/contents/$path" --jq '.sha' 2>&1
        if ($LASTEXITCODE -eq 0 -and $out) {
            return ($out | Out-String).Trim()
        }
        return $null
    } finally {
        $ErrorActionPreference = $oldEAP
    }
}

function Put-File([string]$path, [string]$localFile, [string]$commitMessage) {
    $bytes = [System.IO.File]::ReadAllBytes((Resolve-Path $localFile))
    $b64 = [Convert]::ToBase64String($bytes)
    $sha = Get-ContentSha $path
    $args = @(
        'api', '--method', 'PUT', "repos/$Repo/contents/$path",
        '-f', "message=$commitMessage",
        '-f', "content=$b64",
        '-f', "branch=$Branch"
    )
    if ($sha) {
        $args += @('-f', "sha=$sha")
    }
    if ($WhatIf) {
        Write-Host "[WhatIf] PUT $path (sha=$sha)"
        return
    }
    gh @args *> $null
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upload $path"
    }
    Write-Host "Uploaded $path"
}

# 1. Upload the full staging tree.
$root = (Resolve-Path $SourceDir).Path
Get-ChildItem -Path $root -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($root.Length + 1).Replace('\', '/')
    # Never upload local build artifacts/backups from the staging folder.
    if ($rel -match '^(build|dist|backups|__pycache__|\.pytest_cache)/') {
        return
    }
    Put-File $rel $_.FullName "xbar5090 0.2.2 update: $rel"
}

# 2. Optional screenshot + README Hall of Fame section.
if ($ScreenshotPath) {
    if (-not (Test-Path $ScreenshotPath)) {
        throw "Screenshot not found: $ScreenshotPath"
    }
    $imgPath = 'docs/images/hall-of-fame.png'
    Put-File $imgPath $ScreenshotPath "Add 3DMark Hall of Fame screenshot"

    $imgMarkdown = "![3DMark Time Spy Extreme Graphics Hall of Fame](./$imgPath)"
    foreach ($readme in @('README.md', 'README.zh-CN.md')) {
        $local = Join-Path $root $readme
        if (-not (Test-Path $local)) {
            continue
        }
        $content = Get-Content $local -Raw -Encoding UTF8
        $section = "## Hall of Fame`n`n$imgMarkdown`n"
        if ($content -notmatch '## Hall of Fame') {
            $content = $section + "`n" + $content
        } else {
            $content = $content -replace '(?ms)## Hall of Fame.*?(?=## |\z)', $section
        }
        $tmp = [System.IO.Path]::GetTempFileName()
        [System.IO.File]::WriteAllText($tmp, $content, [System.Text.UTF8Encoding]::new($false))
        Put-File $readme $tmp "Add 3DMark Hall of Fame screenshot to $readme"
        Remove-Item $tmp -Force
    }
}

Write-Host 'Upload script completed. (Run without -WhatIf after user confirmation.)'
