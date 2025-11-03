from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass
class Asset:
    id: str
    title: str
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

