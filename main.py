from dotenv import load_dotenv
from nova_act import NovaAct
from fastapi import FastAPI
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

@app.get("/start")
def read_root():
        nova = NovaAct(starting_page="https://www.amazon.com", headless=True)

        return nova.start()


@app.get("/search/{query}")
def read_item(query: str):
    if query:
        nova = NovaAct(starting_page="https://www.amazon.com", headless=True)

        return nova.act(f"{query}")