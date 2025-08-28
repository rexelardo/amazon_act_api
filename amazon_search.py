from nova_act import NovaAct
from dotenv import load_dotenv
import os
load_dotenv()  # this reads .env and sets os.environ

# confirm
print(os.getenv("NOVA_ACT_API_KEY"))
with NovaAct(starting_page="https://www.amazon.com") as nova:
	nova.act("search for a coffee maker")
	
