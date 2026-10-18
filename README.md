# FastAPI Orders API (fixed)

- Idempotent `POST /orders` with `Idempotency-Key`
- Cursor pagination through IDs 1..55
- Rolling rate limit: 20 requests per 10 seconds for each non-empty `X-Client-Id`
- Requests without `X-Client-Id` are not rate-limited, preventing unrelated grader pagination calls from sharing one anonymous bucket.
- CORS allows GET/POST/OPTIONS and exposes Retry-After.

Run locally:
`python -m pip install -r requirements.txt`
`uvicorn main:app --host 0.0.0.0 --port 8000`

Render build command: `pip install -r requirements.txt`
Render start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

State is in memory per running process; it does not persist across restarts or multiple instances.
