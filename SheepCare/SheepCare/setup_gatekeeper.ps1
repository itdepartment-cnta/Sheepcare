# SHEEPCARE - OpenAgri GateKeeper setup script
# Clones and configures the GateKeeper auth/proxy service from GitHub.

$repoUrl = "https://github.com/agstack/OpenAgri-GateKeeper.git"
$targetDir = "gatekeeper"

# Commit fijado explicitamente: GateKeeper no publica releases/tags todavia
# (repo activo, esquema RBAC en desarrollo). Ver docs/gatekeeper-integration-analysis.md
# para el detalle de por que se fija un commit en vez de clonar "main" a pelo.
$pinnedCommit = "49f4bc3c37e5c2d08e715049b55ae8d902e2ec7a"

if (Test-Path $targetDir) {
    Write-Host "Directory '$targetDir' already exists." -ForegroundColor Green
    exit 0
}

Write-Host "Cloning OpenAgri GateKeeper..." -ForegroundColor Cyan
git clone $repoUrl $targetDir

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to clone repository." -ForegroundColor Red
    exit 1
}

Push-Location $targetDir
git checkout $pinnedCommit
$checkoutOk = ($LASTEXITCODE -eq 0)
Pop-Location

if (-not $checkoutOk) {
    Write-Host "Failed to checkout pinned commit $pinnedCommit." -ForegroundColor Red
    exit 1
}

# Copiar la migracion que registra el ServiceMaster/PermissionMaster/ServiceRole
# de SheepCare en el esquema RBAC de GateKeeper (ver installer/gatekeeper-patches/).
$patchesDir = Join-Path $PSScriptRoot "installer\gatekeeper-patches"
Copy-Item (Join-Path $patchesDir "*.py") (Join-Path $targetDir "aegis\migrations\") -Force

# Copiar .env por defecto (el launcher sobreescribe las variables criticas —
# JWT_SIGNING_KEY, DATABASE_URL, APP_PORT — al arrancar el proceso).
Copy-Item "$targetDir/.env.sample" "$targetDir/.env" -ErrorAction SilentlyContinue

# run_waitress.py escribe en logs/waitress.log relativo a su directorio de
# trabajo; el directorio no viene versionado en el repo de GateKeeper.
New-Item -ItemType Directory -Force (Join-Path $targetDir "logs") | Out-Null

Write-Host "GateKeeper ready!" -ForegroundColor Green
