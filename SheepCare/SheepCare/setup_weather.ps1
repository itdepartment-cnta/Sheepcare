# SHEEPCARE - OpenAgri Weather Service setup script
# Clones the CNTA fork (branch cnta-patches-local) used by the installer build.
#
# Parametros:
#   -Source  URL o ruta local del fork. Por defecto, el fork de CNTA en GitHub.
#            (La rama cnta-patches-local puede no estar publicada aun: en ese
#            caso se indica la ruta del clon local.)
#   -Branch  Rama a clonar.

param(
    [string]$Source = "https://github.com/itdepartment-cnta/OpenAgri-WeatherService.git",
    [string]$Branch = "cnta-patches-local"
)

$targetDir = "weather"

if (Test-Path $targetDir) {
    Write-Host "Directory '$targetDir' already exists." -ForegroundColor Green
    exit 0
}

Write-Host "Cloning OpenAgri Weather Service ($Branch)..." -ForegroundColor Cyan
git clone --branch $Branch $Source $targetDir

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to clone repository." -ForegroundColor Red
    exit 1
}

Write-Host "Weather ready!" -ForegroundColor Green
