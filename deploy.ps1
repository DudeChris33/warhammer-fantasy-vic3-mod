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
    [switch]$WhatIf
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
