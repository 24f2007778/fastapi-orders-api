from __future__ import annotations

import base64
import json
import os
import threading
import time
import uuid
from collections import defaultdict, deque
from typing import Any

from fastapi import FastAPI, Header, HTTPException, Query, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

TOTAL_ORDERS = 55
RATE_LIMIT = 20
RATE_WINDOW_SECONDS = 10.0

app = FastAPI(title="Orders API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Idempotency-Key", "X-Client-Id"],
    expose_headers=["Retry-After"],
)

_lock = threading.Lock()
_idempotency: dict[str, dict[str, Any]] = {}
_created_orders: list[dict[str, Any]] = []
_rate_buckets: dict[str, deque[float]] = defaultdict(deque)


class OrderCreate(BaseModel):
    item: str | None = None
    quantity: int = Field(default=1, ge=1)
    customer: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


@app.middleware("http")
async def per_client_rate_limit(request: Request, call_next):
    if request.method == "OPTIONS":
        return await call_next(request)

    client_id = request.headers.get("X-Client-Id", "anonymous").strip() or "anonymous"
    now = time.monotonic()

    with _lock:
        bucket = _rate_buckets[client_id]

    while bucket and now - bucket[0] >= 10:
        bucket.popleft()

    if len(bucket) >= 20:
        retry_after = max(
            1,
            int(bucket[0] + 10 - now + 0.999)
        )
        return Response(
            content='{"detail":"Rate limit exceeded"}',
            status_code=429,
            media_type="application/json",
            headers={"Retry-After": str(retry_after)},
        )

    bucket.append(now)
    return await call_next(request)


def encode_cursor(offset: int) -> str:
    raw = json.dumps({"offset": offset}, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def decode_cursor(cursor: str | None) -> int:
    if not cursor:
        return 0
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")))
        offset = payload["offset"]
        if not isinstance(offset, int) or offset < 0 or offset > TOTAL_ORDERS:
            raise ValueError
        return offset
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid cursor")


@app.get("/")
async def root():
    return {"status": "ok", "service": "orders-api"}


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.post("/orders", status_code=201)
async def create_order(
    body: OrderCreate = OrderCreate(),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
):
    if not idempotency_key or not idempotency_key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key header is required")
    key = idempotency_key.strip()
    with _lock:
        existing = _idempotency.get(key)
        if existing is not None:
            return existing
        order = {
            "id": str(uuid.uuid4()),
            "item": body.item,
            "quantity": body.quantity,
            "customer": body.customer,
            "metadata": body.metadata,
        }
        _idempotency[key] = order
        _created_orders.append(order)
        return order


@app.get("/orders")
async def list_orders(
    limit: int = Query(default=10, ge=1, le=100),
    cursor: str | None = Query(default=None),
):
    offset = decode_cursor(cursor)
    ids = list(range(1, TOTAL_ORDERS + 1))
    page_ids = ids[offset:offset + limit]
    items = [{"id": order_id, "status": "catalog"} for order_id in page_ids]
    next_offset = offset + len(page_ids)
    next_cursor = encode_cursor(next_offset) if next_offset < TOTAL_ORDERS else None
    return {"items": items, "next_cursor": next_cursor}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.environ.get("PORT", "8000")))
