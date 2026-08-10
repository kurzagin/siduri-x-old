import os
import json

env_path = ".env"
env_vars = {}
with open(env_path, "r") as f:
    for line in f:
        line = line.strip()
        if line and not line.startswith("#"):
            key, val = line.split("=", 1)
            env_vars[key] = val

os.environ.update(env_vars)

from packages.model_router.zai import ZaiStructuredProvider, GenerationRequest

provider = ZaiStructuredProvider(os.environ.get("ZAI_API_KEY", ""))
try:
    print("Generating response...")
    plan = provider.generate_response(GenerationRequest("Say hello", "Your name is Siduri"))
    print("Success:", plan)
except Exception as e:
    import traceback
    traceback.print_exc()
