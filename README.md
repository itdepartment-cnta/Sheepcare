# SheepCare — Estrus Detection System

SheepCare is an AI-powered estrus detection system for sheep, developed by [CNTA](https://www.cnta.es). It analyses data from livestock sensors to detect reproductive events and supports farm management through integration with the [OpenAgri Farm Calendar](https://github.com/openagri-eu/openagri-farmcalendar).

This repository contains the **Edge version**, designed to run locally on-farm as a native Windows application without a permanent internet connection.

---

## Features

- AI-based estrus detection from USB sensor data
- Local data storage with SQLite (no cloud dependency required)
- Farm Calendar integration via OpenAgri
- Optional synchronisation with SheepCare Cloud

## Architecture

The Edge version runs as a native Windows application. The launcher starts three services locally:

| Service | Technology | Port |
|---|---|---|
| Backend + Frontend | FastAPI + React (Python) | 8000 |
| Farm Calendar | OpenAgri / Django | 8002 |
| Database | PostgreSQL (portable, bundled) | 5433 |

Data is persisted in a local SQLite database (for SheepCare) and a local PostgreSQL database (for the Farm Calendar). When internet connectivity is available, readings can be synchronised to the SheepCare Cloud.

## Prerequisites

- Windows 10 (64-bit) or Windows 11
- Python 3.12 or 3.13 with a virtual environment set up
- Node.js 18+ (to build the frontend)
- [PyInstaller](https://pyinstaller.org) (`pip install pyinstaller`)
- [Inno Setup 6](https://jrsoftware.org/isdl.php) (to compile the installer)

### ML model

The estrus detection model (`models/estrus_clasification.joblib`) is **not included in this repository** as it is proprietary to CNTA.

To run the application you must place the file at:

```
models/estrus_clasification.joblib
```

Contact the CNTA development team to obtain the model file.

## Development setup

### 1. Clone the repository

```bash
git clone https://github.com/itdepartment-cnta/SheepCare.git
cd SheepCare
```

### 2. Create and activate the virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
```

### 3. Set up the Farm Calendar

```powershell
.\setup_farmcalendar.ps1
```

This clones the OpenAgri Farm Calendar into the `/farmcalendar` directory.

### 4. Build the frontend

```powershell
cd frontend
npm install
npm run build
cd ..
```

### 5. Run the backend locally

```powershell
python -m uvicorn backend.main:app --reload --port 8000
```

## Building the installer

The `installer/build-release.ps1` script orchestrates the full build:

```powershell
.\installer\build-release.ps1
```

This compiles the backend, Farm Calendar and launcher with PyInstaller, then packages everything into a single `SheepCare-Setup-1.0.exe` installer using Inno Setup.

Optional flags to skip steps during development:

```powershell
.\installer\build-release.ps1 -SkipFrontend -SkipCalendar
```

### Testing the bundle without the installer

```powershell
.\installer\test-bundle.ps1          # start backend + calendar + postgres
.\installer\test-bundle.ps1 -StopAll # stop all test processes
```

## Cloud synchronisation

SheepCare Edge can optionally synchronise data with SheepCare Cloud. Configure the cloud URL and credentials through the application settings interface. The sync process runs asynchronously and only transmits readings flagged as unsynced.

## Licensing

The SheepCare Edge source code is licensed under the **GNU General Public License v3.0** — see the [LICENSE](LICENSE) file for details.

The following components are governed by their own licences:

| Component | Licence |
|---|---|
| OpenAgri Farm Calendar | Apache License 2.0 |

The logos in the `/logos` directory are trademarks of their respective owners (CNTA, OpenAgri, European Union, Genovis) and are **not** covered by the GPL v3 licence of this project.

The application icon (`installer/assets/sheepcare.ico`) is based on an icon by [shmai on Flaticon](https://www.flaticon.es/iconos-gratis/oveja "oveja iconos").

## Acknowledgements

SheepCare has been developed with the support of the [OpenAgri](https://horizon-openagri.eu) project, funded by the European Union's Horizon Europe programme.

The SheepCare Edge version integrates the [OpenAgri Farm Calendar](https://github.com/openagri-eu/openagri-farmcalendar), developed by the OpenAgri consortium and licensed under the Apache License 2.0.
