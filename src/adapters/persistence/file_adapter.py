import json
from pathlib import Path
from typing import Any, Dict


class FileAdapter:
    """Simple file adapter to read/write local artifacts like dcat-fed.json"""

    def __init__(self, base_dir: str = "."):
        self.base = Path(base_dir)

    def write_json(self, path: str, data: Dict[str, Any]):
        p = self.base / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def read_json(self, path: str) -> Dict[str, Any]:
        p = self.base / path
        if not p.exists():
            return {}
        return json.loads(p.read_text())

