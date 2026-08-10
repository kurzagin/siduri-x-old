from packages.memory.service import MemoryService
from pathlib import Path
from apps.orchestrator.src.siduri_orchestrator.server import memory_dict

db_path = Path("data/memory.sqlite3").resolve()
service = MemoryService(db_path)
item = service.approve("proposal_13ce59f1f03840d5b96cece0fdc4d062")
try:
    print(memory_dict(item))
except Exception as e:
    import traceback
    traceback.print_exc()
