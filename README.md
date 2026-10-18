# FastAPI Orders API

Implements idempotent `POST /orders`, cursor pagination over catalog IDs 1..55,
and a per-`X-Client-Id` limit of 20 requests per rolling 10-second window.
CORS is enabled for browser-based grading.

## Run locally
```bash
python -m pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

## Deploy
Build command: `pip install -r requirements.txt`
Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

In-memory idempotency and rate-limit state is shared within one process, but
does not survive restarts or span multiple instances. For multi-instance
production use, replace these stores with Redis or a database.
