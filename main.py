from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
import os

from nova_act import NovaAct
try:
    from nova_act.types.errors import AuthError
except Exception:
    class AuthError(Exception): ...

app = FastAPI(title="NovaAct Minimal API")

# --- Single, global NovaAct (keep one process/worker) ---
NOVA: Optional[NovaAct] = None
SESSION_ID: Optional[str] = None
LOGS_DIR: Optional[str] = None

class StartBody(BaseModel):
    starting_page: str = "https://www.amazon.com"
    headless: bool = True

class ActBody(BaseModel):
    command: str

def run_and_capture(fn, *args, **kwargs) -> str:
    """Run a function and capture ONLY the console output produced during it."""
    buf_out, buf_err = StringIO(), StringIO()
    try:
        with redirect_stdout(buf_out), redirect_stderr(buf_err):
            return_val = fn(*args, **kwargs)
    except Exception as e:
        # include captured logs in the error so the client sees what happened
        logs = buf_out.getvalue() + buf_err.getvalue()
        raise HTTPException(status_code=500, detail={"error": repr(e), "logs": logs})
    # Return both streams and (optionally) a repr of return value
    return (buf_out.getvalue() + buf_err.getvalue()).rstrip()

@app.on_event("startup")
def on_startup():
    load_dotenv()
    if not os.getenv("NOVA_ACT_API_KEY"):
        print("[WARN] NOVA_ACT_API_KEY not set; /nova/start will fail.")

@app.get("/health")
def health():
    return {"ok": True}

@app.post("/nova/start")
def nova_start(body: StartBody):
    global NOVA, SESSION_ID, LOGS_DIR
    if NOVA is not None:
        return {
            "ok": True,
            "note": "already running",
            "session_id": SESSION_ID,
            "logs_dir": LOGS_DIR,
        }
    if not os.getenv("NOVA_ACT_API_KEY"):
        raise HTTPException(status_code=401, detail="NOVA_ACT_API_KEY is not set")

    def do_start():
        # Instantiate & start NovaAct
        global NOVA, SESSION_ID, LOGS_DIR
        NOVA = NovaAct(starting_page=body.starting_page, headless=body.headless)
        NOVA.start()
        SESSION_ID = getattr(NOVA, "session_id", None)
        LOGS_DIR = getattr(NOVA, "logs_dir", None)

    try:
        logs = run_and_capture(do_start)
    except AuthError as e:
        NOVA = None
        raise HTTPException(status_code=401, detail=f"NovaAct auth failed: {e}")
    return {
        "ok": True,
        "session_id": SESSION_ID,
        "logs_dir": LOGS_DIR,
        "logs": logs,  # <- this includes lines like the Playwright warning + "start session ... logs dir ..."
    }

@app.post("/nova/act")
def nova_act(body: ActBody):
    if NOVA is None:
        raise HTTPException(status_code=400, detail="NovaAct not running; POST /nova/start first.")
    # Capture exactly what nova.act printed for this command
    logs = run_and_capture(NOVA.act, body.command)
    return {"ok": True, "session_id": SESSION_ID, "logs_dir": LOGS_DIR, "logs": logs}

@app.get("/nova/status")
def nova_status():
    return {"running": NOVA is not None, "session_id": SESSION_ID, "logs_dir": LOGS_DIR}

@app.post("/nova/stop")
def nova_stop():
    global NOVA, SESSION_ID, LOGS_DIR
    if NOVA is None:
        return {"running": False, "note": "not running"}
    try:
        # capture shutdown logs too (if any)
        _ = run_and_capture(getattr(NOVA, "stop", getattr(NOVA, "close", lambda: None)))
    finally:
        NOVA = None
        SESSION_ID = None
        LOGS_DIR = None
    return {"running": False, "stopped": True}
