# FreshBox AI

FreshBox AI is a local food-freshness monitoring prototype with a FastAPI backend, a React/Vite frontend, and ESP32 firmware.

## Requirements

- Python 3
- Node.js and npm

## Run the backend

From the project root:

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn src.api:app --reload --host 127.0.0.1 --port 8000
```

The API documentation is available at <http://127.0.0.1:8000/docs>. Runtime records are stored in `data/freshbox.sqlite3`.

## Run the frontend

In another terminal:

```sh
cd Frontend
npm ci
npm run dev -- --host 127.0.0.1
```

Open the URL printed by Vite (by default <http://127.0.0.1:5173/>). The frontend uses `http://localhost:8000` for the API by default. To use another backend URL, set `VITE_FRESHBOX_API_URL` when starting Vite.

## Prototype limitations

This is a local prototype. API authentication is not implemented, and the frontend demo login accepts any valid email and non-empty password. Do not expose it to untrusted networks or use it for food-safety decisions.

The optional offline analysis pipeline can use files placed in `data/external_datasets/`. Those external datasets are not included in this repository; confirm redistribution rights before adding them.
