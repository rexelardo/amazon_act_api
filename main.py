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
#         nova = None
#         return {"status": "stopped"}
#     return {"status": "not running"}










import sys
from io import StringIO
import contextlib
from fastapi import FastAPI, HTTPException
from nova_act import NovaAct
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()




@contextlib.contextmanager
def capture_output():
    old_stdout, old_stderr = sys.stdout, sys.stderr
    stdout, stderr = StringIO(), StringIO()
    try:
        sys.stdout, sys.stderr = stdout, stderr
        yield stdout, stderr
    finally:
        sys.stdout, sys.stderr = old_stdout, old_stderr


nova = None  # Global NovaAct instance

@app.post("/start")
def start():
    global nova
    if nova is not None:
        return {"status": "already started"}
    nova = NovaAct(starting_page="https://www.amazon.com", headless=True)
    nova.start()
    return {"status": "started"}

@app.post("/act")
def act(query: str):
    with capture_output() as (stdout, stderr):
        global nova
        if nova is None:
            raise HTTPException(status_code=400, detail="Session not started")
        result = nova.act(query)
        return {"result": result, "stdout": stdout.getvalue(), "stderr": stderr.getvalue()}

@app.post("/stop")
def stop():
    global nova
    if nova is not None:
        nova.stop()
        nova = None
        return {"status": "stopped"}
    return {"status": "not running"}



