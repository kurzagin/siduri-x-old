from packages.memory.service import MemoryService
from pathlib import Path
db_path = Path("data/memory.sqlite3").resolve()
service = MemoryService(db_path)
print("Proposals:", service.proposals())
try:
    service.approve("proposal_80fc3d8c5b474825b61a8f55bca06c35")
except Exception as e:
    import traceback
    traceback.print_exc()
