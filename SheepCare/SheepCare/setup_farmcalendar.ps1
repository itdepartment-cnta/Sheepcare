# SHEEPCARE - OpenAgri Farm Calendar setup script
# Clones and configures the Farm Calendar service from GitHub.

$repoUrl = "https://github.com/agstack/OpenAgri-FarmCalendar.git"
$targetDir = "farmcalendar"

if (Test-Path $targetDir) {
    Write-Host "Directory '$targetDir' already exists." -ForegroundColor Green
    exit 0
}

Write-Host "Cloning OpenAgri Farm Calendar..." -ForegroundColor Cyan
git clone $repoUrl $targetDir

if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to clone repository." -ForegroundColor Red
    exit 1
}

# Copy default .env
Copy-Item "$targetDir/.env.sample" "$targetDir/.env" -ErrorAction SilentlyContinue

Write-Host "Farm Calendar ready!" -ForegroundColor Green
