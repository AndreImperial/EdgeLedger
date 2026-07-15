# EdgeLedger

EdgeLedger is a local-first trading journal and research workspace with the
CMM strategy engine bundled directly in this repository.

## Start

Double-click `Start EdgeLedger.bat`. The launcher prepares and starts:

- the EdgeLedger interface at `http://127.0.0.1:5173`
- the bundled Python scanner behind EdgeLedger's same-origin `/api` route

The scanner uses public Bitunix USDT perpetual candles and optional Coinalyze
open-interest context. EdgeLedger remains paper/manual only and never places
trades.

## Requirements

- Node.js 20 or newer with `pnpm`
- Python 3.11 or newer

Copy `backend/.env.example` to `backend/.env` to customize scanner limits or add
an optional Coinalyze API key. Never commit the populated `.env` file.

## Development

Run `pnpm install` and `pnpm dev` for the frontend. Run the bundled backend from
`backend` with `./.venv/Scripts/python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000`.
Vite proxies `/api` to it during development. `VITE_CMM_API_URL` is optional and
is only needed when intentionally hosting the scanner elsewhere.
