from typing import Dict, Any
from ...core.ports.asset_ports import IAssetFormatPort
from ...core.domain.asset import Asset


class DCATFormatter(IAssetFormatPort):
	"""Minimal DCAT-like formatter that serializes an Asset to a dict.

	This is intentionally simple and meant as a base example.
	"""

	NAME = "dcat"

	def format(self, asset: Asset) -> Dict[str, Any]:
		return {
			"@context": "https://www.w3.org/ns/dcat#",
			"id": asset.id,
			"title": asset.title,
			"description": asset.description,
			"metadata": asset.metadata,
		}


