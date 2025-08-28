from nova_act import NovaAct
from dotenv import load_dotenv
import os
load_dotenv()  # this reads .env and sets os.environ

# confirm
print(os.getenv("NOVA_ACT_API_KEY"))
nova = NovaAct(starting_page="https://www.amazon.com", headless=True)
nova.start()
nova.act("search for a coffee maker")
	
