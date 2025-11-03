from datetime import datetime
from typing import Dict, Any
import uuid


def generate_prov_for_asset(asset: Dict[str, Any], actor: str = "did:example:1234") -> Dict[str, Any]:
    """Return a minimal PROV-O-like structure for an asset.

    This is intentionally small: activity, entity, and generation time.
    """
    now = datetime.utcnow().isoformat() + "Z"
    prov = {
        "entity": {"id": asset.get("id"), "title": asset.get("title")},
        "activity": {"type": "creation", "time": now, "agent": actor},
        "generatedAt": now,
    }
    return prov


def generate_asset_descriptor_jsonld(
    asset: Dict[str, Any], base_url: str = "http://example.org/", data_uri: str | None = None
) -> Dict[str, Any]:
    """Generate a JSON-LD descriptor representing the asset.

    The descriptor will include:
    - a UUID `id` if asset doesn't include one
    - references to the data location (`data_uri`) and the descriptor URI
    - relationships linking descriptor -> data and catalog entries
    """
    # ensure asset has a uuid id
    if not asset.get("uuid"):
        asset_uuid = str(uuid.uuid4())
        asset["uuid"] = asset_uuid
    else:
        asset_uuid = asset["uuid"]

    descriptor_id = base_url.rstrip("/") + "/descriptors/" + asset_uuid
    data_ref = data_uri or asset.get("data_uri") or base_url.rstrip("/") + "/data/" + asset.get("id")

    descriptor = {
        "@context": {
            "dcat": "http://www.w3.org/ns/dcat#",
            "prov": "http://www.w3.org/ns/prov#",
            "schema": "http://schema.org/",
        },
        "@id": descriptor_id,
        "@type": ["dcat:Dataset"],
        "dcat:title": asset.get("title"),
        "schema:identifier": asset_uuid,
        "dcat:distribution": {"@id": data_ref},
        "prov:wasGeneratedBy": asset.get("prov", {}).get("activity", {}),
    }

    # link back: asset will include descriptor_uri
    asset["descriptor_uri"] = descriptor_id
    asset["data_uri"] = data_ref

    return descriptor
