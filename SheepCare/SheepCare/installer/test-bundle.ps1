# ============================================================================
# SheepCare — Test rápido del bundle (sin Inno Setup, sin instalador)
# Prueba los exes compilados directamente desde installer/dist/
#
# Uso:
#   .\installer\test-bundle.ps1              # prueba el backend + pgsql + calendar
#   .\installer\test-bundle.ps1 -StopAll     # detiene todos los procesos de prueba
#   .\installer\test-bundle.ps1 -BackendOnly # solo el backend (sin pgsql ni calendar)
# ============================================================================
param(
    [switch]$StopAll,
    [switch]$BackendOnly
)

$root     = Split-Path $PSScriptRoot -Parent
$dist     = Join-Path $PSScriptRoot 'dist'
$pgsql    = Join-Path $PSScriptRoot 'pgsql'
$appdata  = Join-Path $env:APPDATA 'SheepCare-test'
$pgdata   = Join-Path $appdata 'pgdata'
$logdir   = Join-Path $appdata 'logs'
$dbpath   = Join-Path $appdata 'sheepcare.db'

$pgBin    = Join-Path $pgsql 'bin'
$pgCtl    = Join-Path $pgBin 'pg_ctl.exe'
$initdb   = Join-Path $pgBin 'initdb.exe'
$psql     = Join-Path $pgBin 'psql.exe'
$backend  = Join-Path $dist 'backend\sheepcare-backend.exe'
$calendar = Join-Path $dist 'calendar\sheepcare-calendar.exe'

$PG_PORT = 5434   # Puerto distinto al de produccion para no interferir
$PG_USER = 'farmcalendar'; $PG_PASS = 'farmcalendar_pass'; $PG_DB = 'farm_calendar'
$NO_WIN  = 0x08000000

# ── Detener todo ──────────────────────────────────────────────────────────────
if ($StopAll) {
    Write-Host "Deteniendo servicios de prueba..." -ForegroundColor Yellow
    & $pgCtl stop -D $pgdata -m fast 2>$null
    Get-Process | Where-Object { $_.Path -like "*sheepcare-backend*" -or $_.Path -like "*sheepcare-calendar*" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Write-Host "Detenido." -ForegroundColor Green
    exit 0
}

New-Item -ItemType Directory -Force $appdata, $logdir | Out-Null

function Run-Hidden { param([string[]]$Cmd, [int]$Timeout=120)
    $p = Start-Process $Cmd[0] -ArgumentList $Cmd[1..($Cmd.Length-1)] `
         -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $logdir 'cmd.log') `
         -RedirectStandardError (Join-Path $logdir 'cmd.err') 2>$null
    if ($p) { $p.WaitForExit($Timeout * 1000) | Out-Null; return $p.ExitCode }
    return -1
}

Write-Host ""
Write-Host "=== SheepCare Bundle Test ===" -ForegroundColor Cyan
Write-Host "dist/: $dist"
Write-Host ""

# ── Verificar exes ────────────────────────────────────────────────────────────
$missing = @()
if (-not (Test-Path $backend))  { $missing += "dist\backend\sheepcare-backend.exe" }
if (-not $BackendOnly) {
    if (-not (Test-Path $calendar)) { $missing += "dist\calendar\sheepcare-calendar.exe" }
    if (-not (Test-Path $pgCtl))    { $missing += "pgsql\bin\pg_ctl.exe" }
}
if ($missing) {
    Write-Host "FALTAN ARCHIVOS:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    exit 1
}
Write-Host "[OK] Todos los exes presentes" -ForegroundColor Green

if (-not $BackendOnly) {
    # ── PostgreSQL ────────────────────────────────────────────────────────────
    Write-Host ""
    Write-Host "[1] PostgreSQL..." -ForegroundColor Yellow
    if (-not (Test-Path $pgdata)) {
        Write-Host "  initdb (primera vez, ~30s)..."
        & $initdb -D $pgdata -U postgres --encoding=UTF8 --locale=C 2>&1 | Out-Null
        Add-Content (Join-Path $pgdata 'pg_hba.conf') "`nhost all all 127.0.0.1/32 trust`n"
    }
    & $pgCtl start -D $pgdata -l (Join-Path $logdir 'postgres.log') -o "-p $PG_PORT" 2>$null
    Write-Host "  Esperando..." -NoNewline
    $ok = $false
    for ($i=0; $i -lt 15; $i++) {
        Start-Sleep 2; Write-Host "." -NoNewline
        # Usar subprocess.run con array de argumentos para evitar problemas de escapado
        $r = & $psql -U postgres -p $PG_PORT -c "SELECT 1" postgres 2>$null
        if ($LASTEXITCODE -eq 0) { $ok = $true; break }
    }
    if (-not $ok) { Write-Host "`n  FALLO: PostgreSQL no responde" -ForegroundColor Red; exit 1 }
    Write-Host " OK" -ForegroundColor Green

    # Crear BD (idempotente — ignorar error si ya existe)
    & $psql -U postgres -p $PG_PORT -c "CREATE USER $PG_USER WITH PASSWORD '$PG_PASS';" postgres 2>$null | Out-Null
    & $psql -U postgres -p $PG_PORT -c "CREATE DATABASE $PG_DB OWNER $PG_USER;" postgres 2>$null | Out-Null

    # ── FarmCalendar ──────────────────────────────────────────────────────────
    Write-Host "[2] FarmCalendar..." -ForegroundColor Yellow
    $calEnv = [System.Collections.Generic.Dictionary[string,string]]::new()
    $calEnv["POSTGRES_HOST"] = "127.0.0.1"
    $calEnv["POSTGRES_PORT"] = "$PG_PORT"
    $calEnv["POSTGRES_DB"]   = $PG_DB
    $calEnv["POSTGRES_USER"] = $PG_USER
    $calEnv["POSTGRES_PASSWORD"] = $PG_PASS
    $calEnv["APP_PORT"] = "8002"
    $calEnv["DJANGO_SECRET_KEY"] = "test-secret-key"

    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $calendar
    $psi.CreateNoWindow = $true
    $psi.UseShellExecute = $false
    foreach ($k in $calEnv.Keys) { $psi.EnvironmentVariables[$k] = $calEnv[$k] }
    [System.Diagnostics.Process]::Start($psi) | Out-Null
    Write-Host "  Iniciado (PID guardado)" -ForegroundColor Green
}

# ── Backend ───────────────────────────────────────────────────────────────────
Write-Host "[3] Backend FastAPI..." -ForegroundColor Yellow
$bkEnv = [System.Collections.Generic.Dictionary[string,string]]::new()
$bkEnv["SHEEPCARE_DB_PATH"]    = $dbpath
$bkEnv["FARMCALENDAR_API_URL"] = "http://127.0.0.1:8002/api/v1/"
$bkEnv["BACKEND_PORT"]         = "8000"
if (-not $BackendOnly) {
    $bkEnv["POSTGRES_HOST"]     = "127.0.0.1"
    $bkEnv["POSTGRES_PORT"]     = "$PG_PORT"
    $bkEnv["POSTGRES_DB"]       = $PG_DB
    $bkEnv["POSTGRES_USER"]     = $PG_USER
    $bkEnv["POSTGRES_PASSWORD"] = $PG_PASS
}

$psi2 = New-Object System.Diagnostics.ProcessStartInfo
$psi2.FileName = $backend
$psi2.CreateNoWindow = $false   # Mostrar consola para ver errores
$psi2.UseShellExecute = $false
foreach ($k in $bkEnv.Keys) { $psi2.EnvironmentVariables[$k] = $bkEnv[$k] }
$bkProc = [System.Diagnostics.Process]::Start($psi2)

# ── Esperar al backend ────────────────────────────────────────────────────────
Write-Host "  Esperando http://localhost:8000/api/health..." -NoNewline
$ready = $false
for ($i=0; $i -lt 30; $i++) {
    Start-Sleep 2; Write-Host "." -NoNewline
    try {
        $r = Invoke-WebRequest http://localhost:8000/api/health -TimeoutSec 2 -UseBasicParsing -EA Stop
        if ($r.StatusCode -lt 400) { $ready = $true; break }
    } catch {}
}

if ($ready) {
    Write-Host " OK" -ForegroundColor Green
    Write-Host ""
    Write-Host "=== Bundle funcionando ===" -ForegroundColor Green
    Write-Host "  Frontend: http://localhost:8000"
    Write-Host "  API:      http://localhost:8000/api/health"
    Write-Host "  Calendar: http://localhost:8002"
    Write-Host ""
    Write-Host "Para detener: .\installer\test-bundle.ps1 -StopAll" -ForegroundColor DarkGray
} else {
    Write-Host " FALLO" -ForegroundColor Red
    Write-Host ""
    Write-Host "El backend no respondio. Revisa la ventana de consola del backend." -ForegroundColor Red
    Write-Host "Logs en: $logdir"
}
