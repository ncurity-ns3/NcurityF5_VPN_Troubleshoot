# Publish to github.com/ncurity-ns3/NcurityF5_VPN_Troubleshoot
# Prerequisites: gh auth login  (org write access)
# Usage:  powershell -ExecutionPolicy Bypass -File scripts\publish_github.ps1

$ErrorActionPreference = "Stop"
$env:Path = "C:\Program Files\Git\cmd;C:\Program Files\GitHub CLI;" + $env:Path

$RepoName = "NcurityF5_VPN_Troubleshoot"
$Owner = "ncurity-ns3"
$Full = "$Owner/$RepoName"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root

Write-Host "Auth check..."
gh auth status

Write-Host "Creating repo $Full (public) if missing..."
$exists = $true
try { gh repo view $Full | Out-Null } catch { $exists = $false }
if (-not $exists) {
  gh repo create $Full --public --description "F5 SSL VPN Troubleshoot Tool (Ncurity) — Edge Client 증상 점검·복구" --source . --remote origin --push
} else {
  if (-not (git remote get-url origin 2>$null)) {
    git remote add origin "https://github.com/$Full.git"
  }
  git push -u origin main
  git push origin --tags
}

Write-Host "Creating GitHub Releases from docs/releases..."
$releases = @(
  @{ Tag = "v1.1.5"; File = "docs/releases/v1.1.5.md"; Title = "1.1.5 — GUI 트러블슈팅 도구 초판" },
  @{ Tag = "v1.2.0"; File = "docs/releases/v1.2.0.md"; Title = "1.2.0 — 헬스 · 환경 분석 · 재설치" },
  @{ Tag = "v1.2.1"; File = "docs/releases/v1.2.1.md"; Title = "1.2.1 — 최신 Edge Client 경로 헬스" },
  @{ Tag = "v1.2.2"; File = "docs/releases/v1.2.2.md"; Title = "1.2.2 — Sectigo 인증서" },
  @{ Tag = "v1.3.0"; File = "docs/releases/v1.3.0.md"; Title = "1.3.0 — 사용자 증상 점검 초안" },
  @{ Tag = "v1.3.1"; File = "docs/releases/v1.3.1.md"; Title = "1.3.1 — 기존 UI 유지 · 이슈별 조치 통합" },
  @{ Tag = "v1.4.0"; File = "docs/releases/v1.4.0.md"; Title = "1.4.0 — 진단 분류 · 수동 헬스 · 증상 점검" },
  @{ Tag = "v1.4.1"; File = "docs/releases/v1.4.1.md"; Title = "1.4.1 — 인증서 수정 · 해결 버튼 · 도메인 연동"; Latest = $true }
)

foreach ($r in $releases) {
  $notes = Get-Content -Raw -Encoding UTF8 $r.File
  $existing = gh release view $r.Tag -R $Full 2>$null
  if ($LASTEXITCODE -eq 0) {
    Write-Host "Skip existing $($r.Tag)"
    continue
  }
  $args = @("release", "create", $r.Tag, "-R", $Full, "--title", $r.Title, "--notes", $notes)
  if (-not $r.Latest) { $args += "--latest=false" }
  & gh @args
  Write-Host "Created $($r.Tag)"
}

Write-Host "Done: https://github.com/$Full"
