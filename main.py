from fastapi import FastAPI, HTTPException
from nova_act import NovaAct
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

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
    global nova
    if nova is None:
        raise HTTPException(status_code=400, detail="Session not started")
    return {"result": nova.act(query)}

@app.post("/stop")
def stop():
    global nova
    if nova is not None:
        nova.stop()
        quit()
        nova = None
        return {"status": "stopped"}
    return {"status": "not running"}







