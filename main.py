# from fastapi import FastAPI, HTTPException
# from nova_act import NovaAct
# from dotenv import load_dotenv

# load_dotenv()
# app = FastAPI()

# nova = None  # Global NovaAct instance

# @app.post("/start")
# def start():
#     global nova
#     if nova is not None:
#         return {"status": "already started"}
#     nova = NovaAct(starting_page="https://www.amazon.com", headless=True)
#     nova.start()
#     return {"status": "started"}

# @app.post("/act")
# def act(query: str):
#     global nova
#     if nova is None:
#         raise HTTPException(status_code=400, detail="Session not started")
#     return {"result": nova.act(query)}

# @app.post("/stop")
# def stop():
#     global nova
#     if nova is not None:
#         nova.stop()
#         quit()
#         nova = None
#         return {"status": "stopped"}
#     return {"status": "not running"}








from typing import Annotated
import os
import secrets

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel
from dotenv import load_dotenv

from nova_act import NovaAct  # your existing import

# --- Setup ---
load_dotenv()
app = FastAPI()

security = HTTPBasic()

# Load creds from .env
EXPECTED_USER = os.getenv("USERNAME") or ""
EXPECTED_PASS = os.getenv("PASSWORD") or ""

if not EXPECTED_USER or not EXPECTED_PASS:
    # Fail fast so you don't accidentally deploy with no auth
    raise RuntimeError("BASIC_USERNAME and BASIC_PASSWORD must be set in your .env")

def verify_credentials(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    user_ok = secrets.compare_digest(credentials.username, EXPECTED_USER)
    pass_ok = secrets.compare_digest(credentials.password, EXPECTED_PASS)
    if not (user_ok and pass_ok):
        # Return 401 with a WWW-Authenticate header so clients know to prompt for creds
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
    return credentials.username  # handy to have if you want to log user

# If you want ALL routes gated, you can add a global dependency like:
# app = FastAPI(dependencies=[Depends(verify_credentials)])
# But here we'll add it per-route for clarity.

# --- App state ---
nova = None  # Global NovaAct instance (simple; not threadsafe for heavy concurrency)

class ActRequest(BaseModel):
    query: str

# --- Routes ---
@app.post("/start")
def start(_: Annotated[str, Depends(verify_credentials)]):
    global nova
    if nova is not None:
        return {"status": "already started"}
    nova = NovaAct(starting_page="https://www.amazon.com", headless=True)
    nova.start()
    return {"status": "started"}

@app.post("/act")
def act(payload: ActRequest, _: Annotated[str, Depends(verify_credentials)]):
    global nova
    if nova is None:
        raise HTTPException(status_code=400, detail="Session not started")
    result = nova.act(payload.query)
    return {"result": result}

@app.post("/stop")
def stop(_: Annotated[str, Depends(verify_credentials)]):
    global nova
    if nova is not None:
        try:
            nova.stop()
        finally:
            nova = None
        return {"status": "stopped"}
    return {"status": "not running"}

