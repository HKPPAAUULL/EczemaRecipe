#Requires -Version 5.1
<#
.SYNOPSIS
  Restore a .dump backup into a Postgres database (docker compose service `db`).

.EXAMPLE
  .\scripts\restore.ps1 -File C:\backups\eczema_20261030_030000.dump -TargetDb tmp_check
  .\scripts\restore.ps1 -File C:\backups\eczema_20261030_030000.dump   # restore main DB (asks for typed confirmation)
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$File,
    [string]$TargetDb,
    [switch]$Force,
    [switch]$SkipSafetyBackup,
    [string]$OutDir = "$env:USERPROFILE\EczemaRecipeBackups",
    [switch]$StopApp
)
$ErrorActionPreference = 'Stop'
$ProjectRoot = Split-Path -Parent $PSScriptRoot

function Fail($msg) { Write-Error $msg; exit 1 }

# --- file checks BEFORE touching anything ---
if (-not (Test-Path $File)) { Fail "backup file not found: $File" }
if ([IO.Path]::GetExtension($File) -ne '.dump') {
    Fail "expected a .dump file (custom pg_dump format): $File"
}
$resolvedFile = (Resolve-Path $File).Path
if ((Get-Item $resolvedFile).Length -le 0) { Fail "backup file is empty" }

# --- .env: POSTGRES_USER / POSTGRES_DB only ---
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
if (-not $TargetDb) { $TargetDb = $vars.POSTGRES_DB }
if ($TargetDb -notmatch '^[a-zA-Z_][a-zA-Z0-9_]*$') {
    Fail "invalid target database name: $TargetDb"
}

$compose = @('compose', '-f', "$ProjectRoot\docker-compose.yml")

# --- docker + container checks ---
docker compose version *> $null
if ($LASTEXITCODE -ne 0) { Fail "docker compose not available" }
Push-Location $ProjectRoot
try {
    if (-not (docker compose ps -q db 2>$null)) {
        Fail "compose service 'db' is not running"
    }
} finally { Pop-Location }

# --- verify dump readability INSIDE the container before any change ---
$containerFile = "/tmp/restore_$([guid]::NewGuid().ToString('N')).dump"
docker @compose cp $resolvedFile "db:$containerFile"
if ($LASTEXITCODE -ne 0) { Fail "docker cp into container failed" }
docker @compose exec -T db pg_restore --list $containerFile *> $null
if ($LASTEXITCODE -ne 0) {
    docker @compose exec -T db rm -f $containerFile *> $null
    Fail "pg_restore --list could not read the file — not a valid backup"
}

# --- does the target DB exist? ---
$dbExists = docker @compose exec -T db psql -U $vars.POSTGRES_USER -d postgres -tAc `
    "SELECT 1 FROM pg_database WHERE datname='$TargetDb'" 2>$null
$isNewDb = ($dbExists -ne '1')
$isMainDb = (-not $isNewDb) -and ($TargetDb -eq $vars.POSTGRES_DB)

if ($isMainDb) {
    Write-Host ""
    Write-Host "*** DESTRUCTIVE: this will overwrite the LIVE database '$TargetDb' ***" -ForegroundColor Yellow
    if (-not $SkipSafetyBackup) {
        Write-Host "taking a safety backup first ..."
        & "$PSScriptRoot\backup.ps1" -OutDir $OutDir
        if ($LASTEXITCODE -ne 0) { Fail "safety backup failed — aborting" }
    }
    if (-not $Force) {
        $answer = Read-Host "type the database name '$TargetDb' to confirm"
        if ($answer -ne $TargetDb) { Fail "confirmation mismatch — nothing was changed" }
    }
}

if (-not $isNewDb -and -not $StopApp) {
    Write-Host "tip: to stop writers first, run 'docker compose stop api web' or pass -StopApp"
}
if ($StopApp) {
    docker @compose stop api web | Out-Null
}

try {
    if ($isNewDb) {
        Write-Host "creating database '$TargetDb' ..."
        docker @compose exec -T db psql -U $vars.POSTGRES_USER -d postgres `
            -c "CREATE DATABASE $TargetDb" | Out-Null
        if ($LASTEXITCODE -ne 0) { Fail "CREATE DATABASE failed" }
    }
    Write-Host "restoring into '$TargetDb' ..."
    docker @compose exec -T db pg_restore --clean --if-exists --no-owner `
        --no-privileges -U $vars.POSTGRES_USER -d $TargetDb $containerFile
    # pg_restore returns non-zero on warnings too; treat hard failure only if the
    # summary query below fails
} finally {
    docker @compose exec -T db rm -f $containerFile *> $null
}

$counts = docker @compose exec -T db psql -U $vars.POSTGRES_USER -d $TargetDb -tAc `
    "SELECT 'ingredient='||count(*) FROM ingredient;
     SELECT 'recipe='||count(*) FROM recipe;
     SELECT 'published_ingredient='||count(*) FROM published_ingredient;
     SELECT 'published_recipe='||count(*) FROM published_recipe;
     SELECT 'audit_log='||count(*) FROM audit_log;" 2>$null
if (-not $counts) { Fail "restore finished but verification query failed" }

Write-Host ""
Write-Host "restore OK -> $TargetDb"
$counts | ForEach-Object { Write-Host "  $_" }
if ($StopApp) {
    docker @compose start api web | Out-Null
    Write-Host "api/web restarted"
} elseif (-not $isNewDb) {
    Write-Host "if you stopped api/web, restart with: docker compose up -d api web"
}
exit 0
