from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from typing import Optional
import threading
import os

from nova_act import NovaAct
try:
    from nova_act.types.errors import AuthError
except Exception:
    class AuthError(Exception): ...

app = FastAPI(title="NovaAct Minimal API")

# --- single instance + locks ---
NOVA: Optional[NovaAct] = None
START_LOCK = threading.Lock()  # prevents double-starts
ACT_LOCK = threading.Lock()    # serialize .act() calls

class StartBody(BaseModel):
    starting_page: str = "https://www.amazon.com"
    headless: bool = True

class ActBody(BaseModel):
    query: str

@app.on_event("startup")
def on_startup():
    load_dotenv()
    if not os.getenv("NOVA_ACT_API_KEY"):
        print("[WARN] NOVA_ACT_API_KEY not set; /start will fail auth.")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/start")
def start(body: StartBody):
    global NOVA
    with START_LOCK:
        if NOVA is not None:
            return {"ok": True, "note": "already running"}
        if not os.getenv("NOVA_ACT_API_KEY"):
            raise HTTPException(status_code=401, detail="NOVA_ACT_API_KEY is not set")
        try:
            n = NovaAct(starting_page=body.starting_page, headless=body.headless)
            n.start()
        except AuthError as e:
            raise HTTPException(status_code=401, detail=f"NovaAct auth failed: {e}")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to start NovaAct: {repr(e)}")
        NOVA = n
        return {"ok": True}

@app.post("/search")
def search(body: ActBody):
    if NOVA is None:
        raise HTTPException(status_code=400, detail="Not running. POST /start first.")
    # Ensure only one .act() runs at a time
    with ACT_LOCK:
        try:
            result = NOVA.act(body.query)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"act() failed: {repr(e)}")
    # nova_act often returns None and just logs; still return 200 to the client
    return {"ok": True, "result": repr(result)}

@app.post("/stop")
def stop():
    global NOVA
    if NOVA is None:
        return {"ok": True, "note": "already stopped"}
    try:
        closer = getattr(NOVA, "stop", None) or getattr(NOVA, "close", None)
        if callable(closer):
            closer()
    finally:
        NOVA = None
    return {"ok": True, "stopped": True}
