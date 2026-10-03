<#
.SYNOPSIS
  Mirror the game-read parts of this repo into the Victoria 3 mod folder.

.DESCRIPTION
  The repo lives outside Documents/Paradox Interactive/Victoria 3/mod/ so that
  sources/, mapgen/, .git, planning/ etc. are never part of the Steam Workshop
  upload. The mod folder is a build output: this script copies ONLY the
  allowlisted shipping paths into it (robocopy /MIR per folder, so deletions
  propagate) and removes anything else from it.

  Run it after every change you want to test in-game, and before publishing.

.PARAMETER Dest
  Mod folder to deploy into. Default: <Documents>\Paradox Interactive\Victoria 3\mod\warhammer-fantasy

.PARAMETER WhatIf
  List what would change without copying or deleting.
#>
[CmdletBinding()]
param(
    [string]$Dest = (Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Paradox Interactive\Victoria 3\mod\warhammer-fantasy'),
    [switch]$WhatIf,
    # Copy files the game/editor wrote into the mod folder back into the repo (no deploy).
    [switch]$Pull,
    # Deploy even if the mod folder holds newer files; they are discarded.
    [switch]$Force
)

$ErrorActionPreference = 'Stop'
$repo = $PSScriptRoot

# Folders and files the game (or the launcher) reads. Everything else stays in the repo.
$shipDirs  = @('.metadata', 'common', 'events', 'gfx', 'gui', 'interface', 'localization', 'map_data')
$shipFiles = @('thumbnail.png')

$repoFull = [IO.Path]::GetFullPath($repo).TrimEnd('\')
$destFull = [IO.Path]::GetFullPath($Dest).TrimEnd('\')
if ($repoFull -ieq $destFull) {
    throw "Dest is the repo itself ($destFull). Move the repo out of the mod folder first."
}
if (Test-Path (Join-Path $destFull '.git')) {
    throw "Dest contains a .git folder - it looks like an old repo checkout, not a deploy target. Move or delete it deliberately first."
}

New-Item -ItemType Directory -Force $destFull | Out-Null

# 0. Drift guard. The game and the in-game map editor write INTO the deployed folder
#    (packed heightmap, nodes.dat, generated locators...). Anything there that is
#    newer than, or missing from, the repo would be destroyed by the mirror below.
$drift = @()
foreach ($d in $shipDirs) {
    $src = Join-Path $repoFull $d
    $dst = Join-Path $destFull $d
    if (-not (Test-Path $dst)) { continue }
    if (-not (Test-Path $src)) { $src = Join-Path $env:TEMP 'deploy-empty-src' ; New-Item -ItemType Directory -Force $src | Out-Null }
    # Lists files in Dest that are newer than, or absent from, the repo copy.
    $out = robocopy $dst $src /L /E /XO /XF .gitkeep /NJH /NJS /NDL /NP /FP /NC /R:0 /W:0
    $drift += $out | Where-Object { $_ -match '\S' } | ForEach-Object { $_.Trim() -replace '^\d+\s+', '' }
}
$drift = $drift | Where-Object { $_ } | Sort-Object -Unique
if ($Pull) {
    foreach ($f in $drift) {
        $rel = $f.Substring($destFull.Length).TrimStart('\')
        $to = Join-Path $repoFull $rel
        if ($WhatIf) { "would pull $rel" } else { New-Item -ItemType Directory -Force (Split-Path $to) | Out-Null; Copy-Item $f $to -Force; "pulled $rel" }
    }
    "Pulled $($drift.Count) file(s) into the repo. Review with git status/diff (restore anything you do not want committed), then deploy."
    $global:LASTEXITCODE = 0
    return
}
if ($drift.Count -gt 0 -and -not $Force) {
    $drift | Select-Object -First 25 | ForEach-Object { "  changed in mod folder: $_" }
    throw "$($drift.Count) file(s) in the mod folder are newer than / missing from the repo (editor or game output?). Run '.\deploy.ps1 -Pull' to copy them into the repo first, or '.\deploy.ps1 -Force' to discard them."
}

# 1. Mirror shipping folders.
foreach ($d in $shipDirs) {
    $src = Join-Path $repoFull $d
    $dst = Join-Path $destFull $d
    if (-not (Test-Path $src)) {
        if (Test-Path $dst) { if ($WhatIf) { "would remove $dst" } else { Remove-Item $dst -Recurse -Force } }
        continue
    }
    $args = @($src, $dst, '/MIR', '/XF', '.gitkeep', '/NFL', '/NDL', '/NJH', '/NJS', '/NP', '/R:2', '/W:1')
    if ($WhatIf) { $args += '/L' }
    robocopy @args | Out-Host
    if ($LASTEXITCODE -ge 8) { throw "robocopy failed for $d (exit $LASTEXITCODE)" }
}

# 2. Copy shipping files.
foreach ($f in $shipFiles) {
    $src = Join-Path $repoFull $f
    if (Test-Path $src) {
        if ($WhatIf) { "would copy $f" } else { Copy-Item $src (Join-Path $destFull $f) -Force }
    }
}

# 3. Remove anything in Dest that is not on the allowlist (stale repo leftovers).
$keep = $shipDirs + $shipFiles
Get-ChildItem $destFull -Force | Where-Object { $keep -notcontains $_.Name } | ForEach-Object {
    if ($WhatIf) { "would remove $($_.FullName)" } else { Remove-Item $_.FullName -Recurse -Force }
}

$bytes = (Get-ChildItem $destFull -Recurse -Force -File | Measure-Object Length -Sum).Sum
"Deployed to $destFull ({0:N1} MB)" -f ($bytes / 1MB)
$global:LASTEXITCODE = 0   # robocopy's 1-7 are success codes
