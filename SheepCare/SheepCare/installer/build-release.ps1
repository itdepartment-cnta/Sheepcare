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
    [switch]$SkipGatekeeper, # Saltar PyInstaller del gatekeeper
    [switch]$SkipLauncher,   # Saltar PyInstaller del launcher
    [switch]$SkipWeather,    # Saltar PyInstaller de Weather
    [switch]$SkipReporting,  # Saltar PyInstaller de Reporting
    [switch]$SkipPgsql,      # Saltar descarga de PostgreSQL portable
    [switch]$SkipMongo,      # Saltar descarga de MongoDB portable
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

# Weather y Reporting fijan versiones (pydantic_core 2.18...) sin ruedas para
# Python 3.13: se compilan con Python 3.12 en su propio venv (.venv-weather,
# .venv-reporting), separados del venv del backend.
function Get-Python312 {
    $candidatos = @(
        (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
        'C:\Program Files\Python312\python.exe'
    )
    foreach ($c in $candidatos) { if (Test-Path $c) { return $c } }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $p = & py -3.12 -c "import sys;print(sys.executable)" 2>$null
        if ($LASTEXITCODE -eq 0 -and $p) { return $p }
    }
    Write-Error 'Python 3.12 no encontrado (hace falta para compilar Weather y Reporting). Instalalo desde python.org.'
}

# Crea (si falta) el venv de un servicio y devuelve la ruta de su pyinstaller.
function Initialize-ServiceVenv([string]$Name, [string]$Requirements) {
    $venv = Join-Path $Root ".venv-$Name"
    $venvPy = Join-Path $venv 'Scripts\python.exe'
    if (-not (Test-Path $venvPy)) {
        Write-Host "  Creando entorno .venv-$Name (Python 3.12)..."
        & (Get-Python312) -m venv $venv
        if ($LASTEXITCODE -ne 0) { Write-Error "No se pudo crear .venv-$Name" }
    }
    & $venvPy -m pip install --quiet --disable-pip-version-check -r $Requirements pyinstaller
    if ($LASTEXITCODE -ne 0) { Write-Error "Fallo pip install ($Name)" }
    return (Join-Path $venv 'Scripts\pyinstaller.exe')
}

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
        # La interfaz muestra esta versión en el menú lateral
        $env:VITE_APP_VERSION = $Version
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

# ── 3.5 PyInstaller — GateKeeper ──────────────────────────────────────────────
if (-not $SkipGatekeeper) {
    Write-Host "`n[3.5] PyInstaller — GateKeeper (Django)..." -ForegroundColor Yellow
    Push-Location $Root
    try {
        & $Pyinstaller sheepcare_gatekeeper.spec --distpath (Join-Path $InstallerDir 'dist') --workpath (Join-Path $InstallerDir 'build') --noconfirm
        if ($LASTEXITCODE -ne 0) { Write-Error 'Fallo PyInstaller (gatekeeper)' }
    } finally { Pop-Location }
    Write-Host '  OK' -ForegroundColor Green
} else {
    Write-Host "`n[3.5] GateKeeper: omitido (-SkipGatekeeper)" -ForegroundColor DarkGray
}

# ── 3.6 PyInstaller — Weather ─────────────────────────────────────────────────
if (-not $SkipWeather) {
    Write-Host "`n[3.6] PyInstaller — Weather (FastAPI + MongoDB)..." -ForegroundColor Yellow
    Push-Location $Root
    try {
        if (-not (Test-Path 'weather')) {
            & (Join-Path $Root 'setup_weather.ps1')
            if ($LASTEXITCODE -ne 0) { Write-Error 'No se pudo clonar Weather (ver setup_weather.ps1 -Source)' }
        }
        $pyi = Initialize-ServiceVenv 'weather' (Join-Path $Root 'weather\requirements-windows.txt')
        & $pyi sheepcare_weather.spec --distpath $DistDir --workpath (Join-Path $InstallerDir 'build') --noconfirm
        if ($LASTEXITCODE -ne 0) { Write-Error 'Fallo PyInstaller (weather)' }
    } finally { Pop-Location }
    Write-Host '  OK' -ForegroundColor Green
} else {
    Write-Host "`n[3.6] Weather: omitido (-SkipWeather)" -ForegroundColor DarkGray
}

# ── 3.7 PyInstaller — Reporting ───────────────────────────────────────────────
if (-not $SkipReporting) {
    Write-Host "`n[3.7] PyInstaller — Reporting (FastAPI + PostgreSQL + PDF)..." -ForegroundColor Yellow
    Push-Location $Root
    try {
        if (-not (Test-Path 'reporting')) {
            & (Join-Path $Root 'setup_reporting.ps1')
            if ($LASTEXITCODE -ne 0) { Write-Error 'No se pudo clonar Reporting (ver setup_reporting.ps1 -Source)' }
        }
        $pyi = Initialize-ServiceVenv 'reporting' (Join-Path $Root 'reporting\requirements-windows.txt')
        & $pyi sheepcare_reporting.spec --distpath $DistDir --workpath (Join-Path $InstallerDir 'build') --noconfirm
        if ($LASTEXITCODE -ne 0) { Write-Error 'Fallo PyInstaller (reporting)' }
    } finally { Pop-Location }
    Write-Host '  OK' -ForegroundColor Green
} else {
    Write-Host "`n[3.7] Reporting: omitido (-SkipReporting)" -ForegroundColor DarkGray
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

# ── 5.5 MongoDB portable (solo mongod.exe: cache de Weather) ──────────────────
if (-not $SkipMongo) {
    Write-Host "`n[5.5] MongoDB portable..." -ForegroundColor Yellow
    $MongoDir = Join-Path $InstallerDir 'mongodb'
    if (Test-Path (Join-Path $MongoDir 'bin\mongod.exe')) {
        Write-Host "  Ya existe en installer\mongodb\, omitiendo descarga."
    } else {
        # 4.4 y no 5+: las versiones nuevas exigen CPU con AVX (igual que mongo:4 en la nube).
        # Licencia SSPL: se redistribuye sin modificar y con sus avisos de licencia.
        $mongoVersion = '4.4.29'
        $mongoSha256 = '900f0c4223f418468c77e2fc966776a0c199174eb91912af0255c075162aff03'
        $zip = Join-Path $env:TEMP "mongodb-windows-x86_64-$mongoVersion.zip"
        Write-Host "  Descargando MongoDB $mongoVersion (unos 290 MB)..."
        Invoke-WebRequest -Uri "https://fastdl.mongodb.org/windows/mongodb-windows-x86_64-$mongoVersion.zip" -OutFile $zip -UseBasicParsing
        if ((Get-FileHash $zip -Algorithm SHA256).Hash.ToLower() -ne $mongoSha256) {
            Remove-Item $zip -Force
            Write-Error 'El SHA256 del zip de MongoDB no coincide con el publicado.'
        }
        New-Item -ItemType Directory -Force (Join-Path $MongoDir 'bin') | Out-Null
        Add-Type -AssemblyName System.IO.Compression.FileSystem
        $arch = [System.IO.Compression.ZipFile]::OpenRead($zip)
        try {
            foreach ($e in $arch.Entries) {
                if ($e.FullName -match '/bin/mongod\.exe$') {
                    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($e, (Join-Path $MongoDir 'bin\mongod.exe'), $true)
                } elseif ($e.FullName -match '/(LICENSE-Community\.txt|THIRD-PARTY-NOTICES|README|MPL-2)$') {
                    [System.IO.Compression.ZipFileExtensions]::ExtractToFile($e, (Join-Path $MongoDir ($e.FullName -split '/')[-1]), $true)
                }
            }
        } finally { $arch.Dispose() }
        Remove-Item $zip -Force
        Write-Host "  OK — mongod.exe en installer\mongodb\" -ForegroundColor Green
    }
} else {
    Write-Host "`n[5.5] MongoDB: omitido (-SkipMongo)" -ForegroundColor DarkGray
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
