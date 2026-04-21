import asyncio
import random

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Test Service", description="Simulates UP/DOWN/partial failures")

_mode = "healthy"
_mode_lock = asyncio.Lock()


class ModeRequest(BaseModel):
    mode: str


@app.get("/health", tags=["test"])
async def health():
    return {"status": "ok"}


@app.get("/api/v1/data", tags=["test"])
async def get_data():
    async with _mode_lock:
        mode = _mode
    if mode == "down":
        from fastapi import Response
        return Response(status_code=500, content="Service unavailable")
    return {"data": "ok", "mode": mode}


@app.get("/api/v1/users", tags=["test"])
async def get_users():
    async with _mode_lock:
        mode = _mode
    if mode == "down":
        from fastapi import Response
        return Response(status_code=500, content="Service unavailable")
    if mode == "partial":
        from fastapi import Response
        return Response(status_code=404, content="Not found")
    return {"users": [], "mode": mode}


@app.get("/api/v1/slow", tags=["test"])
async def get_slow():
    delay = random.uniform(8, 12)
    await asyncio.sleep(delay)
    return {"data": "slow response", "delay_seconds": delay}


@app.post("/admin/mode", tags=["admin"])
async def set_mode(request: ModeRequest):
    allowed = {"healthy", "down", "partial"}
    if request.mode not in allowed:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"mode must be one of {allowed}")
    global _mode
    async with _mode_lock:
        _mode = request.mode
    return {"mode": _mode}


@app.get("/admin/mode", tags=["admin"])
async def get_mode():
    async with _mode_lock:
        return {"mode": _mode}
