# FreshBox AI

FreshBox AI explores sensor-based food-storage monitoring through ESP32 firmware, a FastAPI backend, and a React web interface.


## What’s included

- **REST API:** FastAPI endpoints for food profiles, storage batches, sensor readings, baselines, observations, and assessments.
- **Web interface:** A React application built with Vite for inventory, monitoring, and food-reference views.
- **Embedded firmware:** ESP32 sketches for collecting and displaying sensor readings.
- **Analysis modules:** Python components for sensor baselines, temporal features, reliability, adaptive fusion, and model evaluation.
- **Local persistence:** SQLite storage for API records.

## Technology

- Python, FastAPI, and SQLite
- React and Vite
- ESP32 firmware (Arduino-compatible)
- pandas, NumPy, scikit-learn, XGBoost, and SHAP

## Prerequisites

- Python 3.10 or later
- Node.js and npm

Hardware is only required to run the ESP32 firmware; the API and frontend can be run locally without a device.

## Run locally

Run the backend and frontend in separate terminals from the project root.

### 1. Start the API

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn src.api:app --reload --host 127.0.0.1 --port 8000
```

The API listens at <http://127.0.0.1:8000>. Interactive API documentation is available at <http://127.0.0.1:8000/docs>, and the health endpoint is <http://127.0.0.1:8000/api/health>.

The API creates and uses `data/freshbox.sqlite3` for local runtime records. This database is intentionally excluded from version control.

### 2. Start the web app

In a second terminal:

```bash
cd Frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open the local address printed by Vite (typically <http://127.0.0.1:5173/>). By default, the frontend connects to the API at `http://localhost:8000`.

To use a different API address, set `VITE_FRESHBOX_API_URL` when starting Vite:

```bash
VITE_FRESHBOX_API_URL=http://127.0.0.1:8001 npm run dev -- --host 127.0.0.1
```

### Demo sign-in

Authentication is not implemented. The frontend demo sign-in accepts any valid email address and any non-empty password. This is not secure authentication and must not be used to protect sensitive information.

## API overview

The API includes endpoints for:

- Health checks, foods, and reference information
- Batch creation and lifecycle
- Sensor reading ingestion and history
- Baselines and quality observations
- Assessments, live inventory, and dataset readiness

See the interactive API documentation at `/docs` while the backend is running for request and response schemas.

## Repository layout

```text
.
├── Frontend/      React and Vite web application
├── FreshBoxAI/    ESP32 firmware sketch
├── firmware/      ESP32 firmware sketch
├── data/          Food profiles and reference summaries
├── src/           API, persistence, and analysis modules
├── tests/         API and storage tests
├── main.py        Offline analysis/demo pipeline
└── requirements.txt
```

## Data and validation notes

- External reference datasets are not included. Before adding any third-party dataset, verify that its license permits redistribution and document its source.
- Food profiles and reference summaries may have incomplete sensor coverage and are not validated food-safety thresholds.
- The offline analysis pipeline is separate from the REST API; API readings are not automatically used to produce validated shelf-life predictions.
- The API currently has no authentication. Run it only in a trusted local development environment.

## Development

Install the frontend dependencies with `npm ci` from `Frontend/`. Install the Python dependencies with `python -m pip install -r requirements.txt` in an activated virtual environment. Tests are located in `tests/`.
