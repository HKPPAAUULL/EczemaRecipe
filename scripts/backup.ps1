#Requires -Version 5.1
<#
.SYNOPSIS
  Backup the eczema_recipe Postgres DB (docker compose service `db`) to a
  custom-format .dump file outside the repo.

.EXAMPLE
  .\scripts\backup.ps1
  .\scripts\backup.ps1 -OutDir D:\backups -Keep 30
#>
[CmdletBinding()]
param(
    [string]$OutDir = "$env:USERPROFILE\EczemaRecipeBackups",
    [int]$Keep = 14
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Fail($msg) { Write-Error $msg; exit 1 }

# --- resolve OutDir: must exist outside the project ---
$resolvedRoot = (Resolve-Path $ProjectRoot).Path.TrimEnd('\','/')
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null
$resolvedOut = (Resolve-Path $OutDir).Path.TrimEnd('\','/')
if ($resolvedOut.StartsWith($resolvedRoot, [StringComparison]::OrdinalIgnoreCase)) {
    Fail "OutDir '$resolvedOut' is inside the project — backups must live outside the repo."
}

# --- .env: only POSTGRES_USER / POSTGRES_DB are read ---
$envFile = Join-Path $ProjectRoot '.env'
if (-not (Test-Path $envFile)) { Fail ".env not found at $envFile" }
$vars = @{}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^(POSTGRES_USER|POSTGRES_DB)\s*=\s*(.*)$') {
        $vars[$Matches[1]] = $Matches[2].Trim()
    }
}
if (-not $vars.POSTGRES_USER -or -not $vars.POSTGRES_DB) {
    Fail "POSTGRES_USER / POSTGRES_DB missing in .env"
}

# --- docker + container checks ---
Push-Location $ProjectRoot
try {
    docker compose version *> $null
    if ($LASTEXITCODE -ne 0) { Fail "docker compose not available — is Docker installed?" }
    $running = (docker compose ps -q db 2>$null)
    if (-not $running) { Fail "compose service 'db' is not running (docker compose up -d db)" }
} finally { Pop-Location }

$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$name = "eczema_$stamp.dump"
$containerPath = "/tmp/$name"
$outFile = Join-Path $resolvedOut $name

try {
    Write-Host "dumping database '$($vars.POSTGRES_DB)' ..."
    docker compose -f "$ProjectRoot\docker-compose.yml" exec -T db `
        pg_dump -U $vars.POSTGRES_USER -Fc -f $containerPath $vars.POSTGRES_DB
    if ($LASTEXITCODE -ne 0) { Fail "pg_dump failed (exit $LASTEXITCODE)" }

    docker compose -f "$ProjectRoot\docker-compose.yml" cp "db:$containerPath" $outFile
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path $outFile)) {
        Fail "docker cp failed — backup file not produced"
    }
    $size = (Get-Item $outFile).Length
    if ($size -le 0) { Remove-Item $outFile -Force; Fail "backup file is empty" }

    # verify the dump is readable by pg_restore --list inside the container
    docker compose -f "$ProjectRoot\docker-compose.yml" exec -T db `
        pg_restore --list $containerPath *> $null
    if ($LASTEXITCODE -ne 0) {
        Remove-Item $outFile -Force
        Fail "pg_restore --list could not read the dump — bad file removed"
    }
} finally {
    docker compose -f "$ProjectRoot\docker-compose.yml" exec -T db `
        rm -f $containerPath *> $null
}

# --- retention: only files matching OUR naming rule ---
if ($Keep -gt 0) {
    Get-ChildItem -Path $resolvedOut -Filter 'eczema_????????_??????.dump' -File |
        Sort-Object LastWriteTime -Descending |
        Select-Object -Skip $Keep |
        ForEach-Object { Write-Host "pruning old backup: $($_.Name)"; Remove-Item $_.FullName -Force }
}

# --- summary: main table counts via psql ---
$counts = docker compose -f "$ProjectRoot\docker-compose.yml" exec -T db `
    psql -U $vars.POSTGRES_USER -d $vars.POSTGRES_DB -tAc `
    "SELECT 'ingredient='||count(*) FROM ingredient;
     SELECT 'recipe='||count(*) FROM recipe;
     SELECT 'published_ingredient='||count(*) FROM published_ingredient;
     SELECT 'published_recipe='||count(*) FROM published_recipe;
     SELECT 'audit_log='||count(*) FROM audit_log;" 2>$null

Write-Host ""
Write-Host "backup OK: $outFile ($size bytes)"
if ($counts) { $counts | ForEach-Object { Write-Host "  $_" } }
exit 0
