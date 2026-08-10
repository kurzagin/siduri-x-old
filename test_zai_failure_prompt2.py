import os
import json
import urllib.request
from packages.model_router.zai import ZaiStructuredProvider
from packages.model_router.router import GenerationRequest
from packages.persona.domain import Recipient

with open('.env') as f:
    for line in f:
        if line.strip() and not line.startswith('#'):
            k, v = line.strip().split('=', 1)
            os.environ[k] = v

provider = ZaiStructuredProvider(os.environ.get("ZAI_API_KEY", ""), model="glm-5.2", base_url=os.environ.get("ZAI_API_BASE_URL", ""))
req = GenerationRequest(task="private_chat", prompt="""[RECIPIENT] master_private
[IDENTITY NUCLEUS]
{"identity": {"stage_name": "Kur", "legal_name": "Never expose"}}
[PERMITTED MEMORIES]
- none permitted
[EVIDENCE / OBSERVATIONS]
- none
[OPERATOR INSTRUCTIONS / TRUSTED INPUT] The following is direct input from your creator/operator. You must follow these instructions and learn these facts:
[CHAT HISTORY]
- none
[CURRENT MESSAGE]
your name is Siduri
[RESPONSE RULES] Preserve uncertainty. Return one semantic response rendered in Japanese, English, and Indonesian.""", recipient=Recipient.MASTER_PRIVATE.value)

try:
    provider.generate_response(req)
except Exception as e:
    # Just print the raw JSON that ZAI returned
    pass

class InterceptZai(ZaiStructuredProvider):
    def _parse_response(self, value, expected_recipient=None):
        content = value["choices"][0]["message"]["content"]
        print("MODEL RETURNED:")
        print(content)
        return super()._parse_response(value, expected_recipient)

provider = InterceptZai(os.environ.get("ZAI_API_KEY", ""), model="glm-5.2", base_url=os.environ.get("ZAI_API_BASE_URL", ""))
try:
    provider.generate_response(req)
except Exception:
    pass
