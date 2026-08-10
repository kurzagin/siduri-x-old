import urllib.request
import json
import traceback

data = json.dumps({"speaker": "Kur", "text": "Your name is Siduri"}).encode("utf-8")
req = urllib.request.Request(
    "http://127.0.0.1:8765/chat",
    data=data,
    headers={"Content-Type": "application/json", "Origin": "http://localhost:3000"}
)
try:
    with urllib.request.urlopen(req) as response:
        print("Status:", response.status)
        print("Body:", response.read().decode("utf-8"))
except Exception as e:
    traceback.print_exc()
