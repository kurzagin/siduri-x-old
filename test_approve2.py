from packages.memory.service import MemoryService
from pathlib import Path
from apps.orchestrator.src.siduri_orchestrator.server import memory_dict

db_path = Path("data/memory.sqlite3").resolve()
service = MemoryService(db_path)
item = service.approve("proposal_80fc3d8c5b474825b61a8f55bca06c35")
try:
    print(memory_dict(item))
except Exception as e:
    import traceback
    traceback.print_exc()
