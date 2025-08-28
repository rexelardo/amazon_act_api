# app/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, AnyUrl
from typing import Optional, Dict, Any
import os
from dotenv import load_dotenv

# Nova Act
from nova_act import NovaAct
# If you want to catch auth errors specifically:
try:
    from nova_act.types.errors import AuthError
except Exception:
    class AuthError(Exception):  # fallback if import path changes
        pass

app = FastAPI(title="NovaAct Control API")

class StartBody(BaseModel):
    starting_page: Optional[AnyUrl] = "https://www.amazon.com"
    headless: bool = True
    # You can add more NovaAct kwargs here if needed, e.g. chrome_channel

class NovaManager:
    def __init__(self):
        self.nova: Optional[NovaAct] = None
        self.session_id: Optional[str] = None
        self.logs_dir: Optional[str] = None

    def start(self, starting_page: str, headless: bool) -> Dict[str, Any]:
        if self.nova is not None:
            # Already running; return status instead of duplicating sessions
            return {
                "running": True,
                "session_id": self.session_id,
                "logs_dir": self.logs_dir,
                "note": "NovaAct already running",
            }

        # Initialize and start NovaAct
        try:
            self.nova = NovaAct(starting_page=starting_page, headless=headless)
            # nova.start() typically prints and returns nothing; capture side-effects
            self.nova.start()
        except AuthError as e:
            self.nova = None
            raise HTTPException(status_code=401, detail=f"NovaAct auth failed: {str(e)}")
        except Exception as e:
            self.nova = None
            raise HTTPException(status_code=500, detail=f"Failed to start NovaAct: {repr(e)}")

        # Best-effort: pull session/log info if exposed
        # NovaAct often logs these; not all attributes are public, so we keep this generic
        self.session_id = getattr(self.nova, "session_id", None)
        self.logs_dir = getattr(self.nova, "logs_dir", None)

        return {
            "running": True,
            "session_id": self.session_id,
            "logs_dir": self.logs_dir,
            "starting_page": starting_page,
            "headless": headless,
        }

    def status(self) -> Dict[str, Any]:
        running = self.nova is not None
        return {
            "running": running,
            "session_id": self.session_id,
            "logs_dir": self.logs_dir,
        }

    def stop(self) -> Dict[str, Any]:
        if self.nova is None:
            return {"running": False, "note": "NovaAct not running"}

        try:
            # NovaAct may expose a close/stop; if not, deleting the instance is a fallback.
            close_fn = getattr(self.nova, "stop", None) or getattr(self.nova, "close", None)
            if callable(close_fn):
                close_fn()
        except Exception as e:
            # We still clear our handle even if stop fails
            self.nova = None
            self.session_id = None
            self.logs_dir = None
            raise HTTPException(status_code=500, detail=f"Error stopping NovaAct: {repr(e)}")

        self.nova = None
        self.session_id = None
        self.logs_dir = None
        return {"running": False, "stopped": True}

manager = NovaManager()

@app.on_event("startup")
def on_startup():
    load_dotenv()
    key = os.getenv("NOVA_ACT_API_KEY")
    if not key:
        # We don't crash: we allow the API to run so you can set the key later.
        print("[WARN] NOVA_ACT_API_KEY not set; POST /nova/start will fail auth until it is set.")
    # Optional: ensure Playwright browsers are installed in advance.
    # You can preinstall via shell. See step 2.

@app.get("/health")
def health():
    return {"ok": True}

@app.get("/env")
def env():
    key = os.getenv("NOVA_ACT_API_KEY")
    masked = f"{key[:4]}…{key[-4:]}" if key and len(key) >= 8 else (key or None)
    return {"NOVA_ACT_API_KEY_present": bool(key), "NOVA_ACT_API_KEY_masked": masked}

@app.get("/nova/status")
def nova_status():
    return manager.status()

@app.post("/nova/start")
def nova_start(body: StartBody):
    # Fail fast if key missing
    if not os.getenv("NOVA_ACT_API_KEY"):
        raise HTTPException(status_code=401, detail="NOVA_ACT_API_KEY is not set in environment/.env")
    return manager.start(starting_page=str(body.starting_page), headless=body.headless)

@app.post("/nova/stop")
def nova_stop():
    return manager.stop()
