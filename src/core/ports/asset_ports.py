from abc import ABC, abstractmethod
from typing import Any, Dict
from ..domain.asset import Asset


class IAssetFormatPort(ABC):
    """Port for formatting/publishing assets (e.g., DCAT, JSON-LD)."""

    @abstractmethod
    def format(self, asset: Asset) -> Dict[str, Any]:
        raise NotImplementedError


class IAssetPublisherPort(ABC):
    """Port to publish an already formatted asset to a target (e.g., IPFS, web)."""

    @abstractmethod
    def publish(self, formatted: Dict[str, Any]) -> str:
        """Returns a location/URL/identifier where the asset was published."""
        raise NotImplementedError

