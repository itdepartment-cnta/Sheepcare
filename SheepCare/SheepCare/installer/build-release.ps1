# ============================================================================
# SheepCare — Build del instalador (sin Docker)
#
# Requisitos en el equipo de desarrollo:
#   - Python 3.12/3.13 con el venv del proyecto activado
#   - Node.js 18+ (para compilar el frontend)
#   - PyInstaller  (pip install pyinstaller)
#   - Inno Setup 6 en AppData\Local\Programs\Inno Setup 6\
#
# Uso:
#   .\installer\build-release.ps1
#   .\installer\build-release.ps1 -Version "1.1" -SkipFrontend -SkipCalendar
# ============================================================================

param(
    [string]$Version       = '1.0',
    [switch]$SkipFrontend,   # Saltar npm run build (si dist/ ya existe)
    [switch]$SkipBackend,    # Saltar PyInstaller del backend
    [switch]$SkipCalendar,   # Saltar PyInstaller del calendar
    [switch]$SkipLauncher,   # Saltar PyInstaller del launcher
    [switch]$SkipPgsql,      # Saltar descarga de PostgreSQL portable
    [switch]$SkipInno        # Saltar compilacion Inno Setup
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Root        = Split-Path $PSScriptRoot -Parent
$InstallerDir = $PSScriptRoot
$DistDir     = Join-Path $InstallerDir 'dist'
$PgsqlDir    = Join-Path $InstallerDir 'pgsql'

$Python = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $Python)) {
    # Buscar Python en PATH
    $Python = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $Python) { Write-Error 'Python no encontrado. Activa el venv o instala Python.' }
}

$Pyinstaller = Join-Path $Root '.venv\Scripts\pyinstaller.exe'
if (-not (Test-Path $Pyinstaller)) { $Pyinstaller = 'pyinstaller' }

$Iscc = "C:\Users\$env:USERNAME\AppData\Local\Programs\Inno Setup 6\ISCC.exe"
if (-not (Test-Path $Iscc)) { $Iscc = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe" }
if (-not (Test-Path $Iscc)) { $Iscc = "${env:ProgramFiles}\Inno Setup 6\ISCC.exe" }

New-Item -ItemType Directory -Force $DistDir | Out-Null

Write-Host ''
Write-Host '======================================================' -ForegroundColor Cyan
Write-Host "  SheepCare Build v$Version (sin Docker)" -ForegroundColor Cyan
Write-Host '======================================================' -ForegroundColor Cyan

# ── 1. Frontend React ─────────────────────────────────────────────────────────
if (-not $SkipFrontend) {
    Write-Host "`n[1] Compilando frontend React..." -ForegroundColor Yellow
    Push-Location (Join-Path $Root 'frontend')
    try {
        & npm run build
        if ($LASTEXITCODE -ne 0) { Write-Error 'Fallo npm run build' }
    } finally { Pop-Location }
    Write-Host '  OK' -ForegroundColor Green
} else {
    Write-Host "`n[1] Frontend: omitido (-SkipFrontend)" -ForegroundColor DarkGray
}

# ── 2. PyInstaller — Backend ──────────────────────────────────────────────────
if (-not $SkipBackend) {
    Write-Host "`n[2] PyInstaller — Backend FastAPI..." -ForegroundColor Yellow
    Push-Location $Root
    try {
        & $Pyinstaller sheepcare.spec --distpath (Join-Path $InstallerDir 'dist') --workpath (Join-Path $InstallerDir 'build') --noconfirm
        if ($LASTEXITCODE -ne 0) { Write-Error 'Fallo PyInstaller (backend)' }
    } finally { Pop-Location }
    Write-Host '  OK' -ForegroundColor Green
} else {
    Write-Host "`n[2] Backend: omitido (-SkipBackend)" -ForegroundColor DarkGray
}

# ── 3. PyInstaller — FarmCalendar ─────────────────────────────────────────────
if (-not $SkipCalendar) {
    Write-Host "`n[3] PyInstaller — FarmCalendar (Django)..." -ForegroundColor Yellow
    Push-Location $Root
    try {
        & $Pyinstaller sheepcare_calendar.spec --distpath (Join-Path $InstallerDir 'dist') --workpath (Join-Path $InstallerDir 'build') --noconfirm
        if ($LASTEXITCODE -ne 0) { Write-Error 'Fallo PyInstaller (calendar)' }
    } finally { Pop-Location }
    Write-Host '  OK' -ForegroundColor Green
} else {
    Write-Host "`n[3] Calendar: omitido (-SkipCalendar)" -ForegroundColor DarkGray
}

# ── 4. PyInstaller — Launcher ─────────────────────────────────────────────────
if (-not $SkipLauncher) {
    Write-Host "`n[4] PyInstaller — Launcher GUI..." -ForegroundColor Yellow
    # Instalar pyinstaller si no está
    $prevEAP = $ErrorActionPreference; $ErrorActionPreference = 'SilentlyContinue'
    $null = & $Python -m pyinstaller --version 2>&1
    $ErrorActionPreference = $prevEAP
    if ($LASTEXITCODE -ne 0) {
        & $Python -m pip install pyinstaller --quiet
    }
    Push-Location $Root
    try {
        & $Pyinstaller sheepcare_launcher.spec --distpath (Join-Path $InstallerDir 'dist') --workpath (Join-Path $InstallerDir 'build') --noconfirm
        if ($LASTEXITCODE -ne 0) { Write-Error 'Fallo PyInstaller (launcher)' }
    } finally { Pop-Location }
    Write-Host '  OK' -ForegroundColor Green
} else {
    Write-Host "`n[4] Launcher: omitido (-SkipLauncher)" -ForegroundColor DarkGray
}

# ── 5. PostgreSQL portable ────────────────────────────────────────────────────
if (-not $SkipPgsql) {
    Write-Host "`n[5] PostgreSQL portable..." -ForegroundColor Yellow
    if (Test-Path $PgsqlDir) {
        Write-Host "  Ya existe en installer\pgsql\, omitiendo descarga."
    } else {
        Write-Host "  Descargando PostgreSQL 16 para Windows x64..."
        Write-Host "  (Esto puede tardar varios minutos)"
        $zip = Join-Path $env:TEMP 'postgresql-win64-binaries.zip'
        $url = 'https://get.enterprisedb.com/postgresql/postgresql-16.9-1-windows-x64-binaries.zip'
        Invoke-WebRequest -Uri $url -OutFile $zip -UseBasicParsing
        Write-Host "  Extrayendo..."
        Expand-Archive -Path $zip -DestinationPath (Join-Path $InstallerDir '_pgsql_tmp') -Force
        # El zip contiene una carpeta 'pgsql/' con bin/, lib/, share/
        Move-Item (Join-Path $InstallerDir '_pgsql_tmp\pgsql') $PgsqlDir
        Remove-Item (Join-Path $InstallerDir '_pgsql_tmp') -Recurse -Force
        Remove-Item $zip
        Write-Host "  OK — PostgreSQL en installer\pgsql\" -ForegroundColor Green
    }

    # Mostrar tamaño
    $sizeMB = [math]::Round((Get-ChildItem $PgsqlDir -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB, 1)
    Write-Host "  Tamano: $sizeMB MB"
} else {
    Write-Host "`n[5] PostgreSQL: omitido (-SkipPgsql)" -ForegroundColor DarkGray
}

# ── 6. Compilar instalador Inno Setup ────────────────────────────────────────
if (-not $SkipInno) {
    Write-Host "`n[6] Compilando instalador Inno Setup..." -ForegroundColor Yellow
    if (-not (Test-Path $Iscc)) {
        Write-Warning "Inno Setup no encontrado. Descargalo de https://jrsoftware.org/isdl.php"
    } else {
        $issFile = Join-Path $InstallerDir 'SheepCare.iss'
        Push-Location $InstallerDir
        try {
            & $Iscc $issFile "/DAppVersion=$Version"
            if ($LASTEXITCODE -ne 0) { Write-Error 'Fallo Inno Setup' }
        } finally { Pop-Location }
        Write-Host ''
        $exe = Get-ChildItem $DistDir -Filter '*.exe' | Select-Object -First 1
        if ($exe) {
            $sizeMB = [math]::Round($exe.Length / 1MB, 1)
            Write-Host "  Instalador: $($exe.Name)  ($sizeMB MB)" -ForegroundColor Green
        }
    }
} else {
    Write-Host "`n[6] Inno Setup: omitido (-SkipInno)" -ForegroundColor DarkGray
}

# ── Resumen ───────────────────────────────────────────────────────────────────
Write-Host ''
Write-Host '======================================================' -ForegroundColor Cyan
Write-Host '  Build completado.' -ForegroundColor Green
Write-Host "  Instalador en: $DistDir" -ForegroundColor Cyan
Write-Host '======================================================' -ForegroundColor Cyan
Write-Host ''
