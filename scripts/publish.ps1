# Publish xbar5090 to GitHub.
#
# Requirements:
#   - Run from the project root.
#   - Either `gh` CLI is installed and authenticated (`gh auth login`),
#     or set $env:GH_TOKEN to a GitHub personal access token with
#     Contents: read/write and Metadata: read.
#
# This script does NOT accept passwords. Use gh auth or a token.

$ErrorActionPreference = 'Stop'
$repo = 'SHANAjam/rtx5090-xbar-control'

# Read version from pyproject.toml (e.g. version = "0.2.1")
$versionLine = Select-String -Path 'pyproject.toml' -Pattern '^version\s*=\s*"([^"]+)"' | Select-Object -First 1
if (-not $versionLine) { throw 'Could not read version from pyproject.toml' }
$version = $versionLine.Matches[0].Groups[1].Value
$tag = "v$version"

# 1. Sanity checks
if (-not (Get-Command gh -ErrorAction SilentlyContinue) -and -not $env:GH_TOKEN) {
    throw 'Neither gh CLI nor GH_TOKEN is available. Run "gh auth login" or set GH_TOKEN.'
}

# 2. Stage everything and commit
git add .
if ($LASTEXITCODE -ne 0) { throw 'git add failed' }
git commit -m "$tag release" 2>$null
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) { throw 'git commit failed' }

# 3. Ensure main branch and remote
git branch -M main
if (-not (git remote | Select-String '^origin$')) {
    git remote add origin "https://github.com/$repo.git"
}

# 4. Tag and push
git tag -f $tag
git push origin main --force --tags

# 5. Create GitHub release
$notes = Join-Path $env:TEMP "xbar5090_${version}_notes.md"
Set-Content -Path $notes -Encoding UTF8 -Value @"
# xbar5090 $tag

See https://github.com/SHANAjam/rtx5090-xbar-control/releases for details.
"@
if (Get-Command gh -ErrorAction SilentlyContinue) {
    gh release create $tag "dist\xbar5090.exe" "dist\xbar5090-windows-single.zip" "dist\xbar5090-windows-folder.zip" `
        --title "xbar5090 $tag" `
        --notes-file $notes
} else {
    Write-Host "gh not installed; release creation skipped. Push succeeded."
    Write-Host "Create the release manually at: https://github.com/$repo/releases/new?tag=$tag"
}
