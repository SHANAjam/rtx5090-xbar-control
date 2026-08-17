# Publish xbar5090 v0.2.1 to GitHub.
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
$tag = 'v0.2.1'

# 1. Sanity checks
if (-not (Get-Command gh -ErrorAction SilentlyContinue) -and -not $env:GH_TOKEN) {
    throw 'Neither gh CLI nor GH_TOKEN is available. Run "gh auth login" or set GH_TOKEN.'
}

# 2. Stage everything and commit
git add .
if ($LASTEXITCODE -ne 0) { throw 'git add failed' }
git commit -m "v0.2.1: RTX 50-series family support + cross-version validation + docs" 2>$null
if ($LASTEXITCODE -ne 0 -and $LASTEXITCODE -ne 1) { throw 'git commit failed' }

# 3. Ensure main branch and remote
git branch -M main
if (-not (git remote | Select-String '^origin$')) {
    git remote add origin "https://github.com/$repo.git"
}

# 4. Tag and push
git tag $tag
git push origin main --tags

# 5. Create GitHub release
if (Get-Command gh -ErrorAction SilentlyContinue) {
    gh release create $tag "dist\xbar5090.exe" `
        --title "xbar5090 v0.2.1" `
        --notes-file "docs\RELEASE_NOTES_v0.2.1.md"
} else {
    Write-Host "gh not installed; release creation skipped. Push succeeded."
    Write-Host "Create the release manually at: https://github.com/$repo/releases/new?tag=$tag"
}
