import os
import json
import urllib.request
from packages.model_router.zai import ZaiStructuredProvider
from packages.model_router.router import GenerationRequest
from packages.persona.domain import Recipient
import traceback

with open('.env') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            os.environ[k] = v

provider = ZaiStructuredProvider(os.environ.get("ZAI_API_KEY", ""), model="glm-5.2", base_url=os.environ.get("ZAI_API_BASE_URL", ""))
req = GenerationRequest(task="private_chat", prompt="test", recipient=Recipient.MASTER_PRIVATE.value)

try:
    print(provider.generate_response(req))
except Exception as e:
    traceback.print_exc()
