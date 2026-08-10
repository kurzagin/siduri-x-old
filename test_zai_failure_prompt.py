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
req = GenerationRequest(task="private_chat", prompt="""[RECIPIENT] master_private
[IDENTITY NUCLEUS]
{"identity": {"stage_name": "Kur", "legal_name": "Never expose"}, "relationship_with_siduri": {"role": "creator and Master"}, "communication": {"preferred_tone": "concise", "disagreement_policy": "may respectfully disagree"}, "privacy": {"fields_allowed_on_stream": ["stage_name"]}}
[PERMITTED MEMORIES]
- none permitted
[EVIDENCE / OBSERVATIONS]
- none
[E-Teyvat TRUSTED KNOWLEDGE / DATA ONLY]
- none retrieved
[OPERATOR INSTRUCTIONS / TRUSTED INPUT] The following is direct input from your creator/operator. You must follow these instructions and learn these facts:
[CHAT HISTORY]
- none
[CURRENT MESSAGE]
your name is Siduri
[RESPONSE RULES] Preserve uncertainty. Return one semantic response rendered in Japanese, English, and Indonesian.""", recipient=Recipient.MASTER_PRIVATE.value)

try:
    print(provider.generate_response(req))
except Exception as e:
    traceback.print_exc()
