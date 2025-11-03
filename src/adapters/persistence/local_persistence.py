from typing import Dict, Any
from pathlib import Path
import json

from ...core.ports.persistence_ports import IPersistencePort


class LocalPersistence(IPersistencePort):
    NAME = "local"

    def __init__(self, base_dir: str = "."):
        self.base = Path(base_dir)
        self.catalog_path = self.base / "catalog.json"

    def save_catalog(self, catalog: Dict[str, Any]) -> None:
        self.catalog_path.parent.mkdir(parents=True, exist_ok=True)
        self.catalog_path.write_text(json.dumps(catalog, indent=2, ensure_ascii=False))

    def load_catalog(self) -> Dict[str, Any]:
        if not self.catalog_path.exists():
            return {"assets": []}
        return json.loads(self.catalog_path.read_text())

    def save_asset_descriptor(self, relative_path: str, descriptor: Dict[str, Any]) -> None:
        p = Path(relative_path)
        # If a relative path is provided, store under base; if absolute, use as-is
        if not p.is_absolute():
            p = self.base / relative_path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(descriptor, indent=2, ensure_ascii=False))

    def load_asset_descriptor(self, relative_path: str) -> Dict[str, Any]:
        p = Path(relative_path)
        if not p.is_absolute():
            p = self.base / relative_path
        if not p.exists():
            return {}
        return json.loads(p.read_text())

