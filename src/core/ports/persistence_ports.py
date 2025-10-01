from abc import ABC, abstractmethod
from typing import Any, Dict


class IPersistencePort(ABC):
    """Abstract persistence port for storing catalogs/assets."""

    @abstractmethod
    def save_catalog(self, catalog: Dict[str, Any]) -> None:
        raise NotImplementedError

    @abstractmethod
    def load_catalog(self) -> Dict[str, Any]:
        raise NotImplementedError
