import requests
from typing import Any, Dict


class SimpleNetworkAdapter:
    """Tiny network adapter using requests for basic fetch/discovery.

    Note: requests is optional; callers should handle absence or install the dep.
    """

    def fetch_json(self, url: str) -> Dict[str, Any]:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()

