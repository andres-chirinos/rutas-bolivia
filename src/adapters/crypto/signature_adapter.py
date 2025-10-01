from typing import Dict, Any
from pathlib import Path
import json
import base64
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives import serialization, hashes


class SignatureAdapter:
    """Simple RSA-based signature adapter that stores keys under `keys/`.

    This is NOT a full Verifiable Credential implementation but provides a
    deterministic 'proof' object with a base64 signature over sorted JSON.
    """

    KEY_DIR = Path("keys")
    PRIV_KEY_PATH = KEY_DIR / "key.pem"
    PUB_KEY_PATH = KEY_DIR / "key.pub.pem"

    def __init__(self):
        self.KEY_DIR.mkdir(parents=True, exist_ok=True)
        if not self.PRIV_KEY_PATH.exists():
            self._generate_keys()
        self._load_keys()

    def _generate_keys(self):
        priv = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        priv_pem = priv.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub = priv.public_key()
        pub_pem = pub.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        self.PRIV_KEY_PATH.write_bytes(priv_pem)
        self.PUB_KEY_PATH.write_bytes(pub_pem)

    def _load_keys(self):
        priv_pem = self.PRIV_KEY_PATH.read_bytes()
        pub_pem = self.PUB_KEY_PATH.read_bytes()
        self._priv = serialization.load_pem_private_key(priv_pem, password=None)
        self._pub = serialization.load_pem_public_key(pub_pem)

    def sign(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        # canonicalize JSON: sort keys to get deterministic bytes
        data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        sig = self._priv.sign(
            data,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )
        proof = {
            "type": "RsaSignature2018",
            "created": datetime.utcnow().isoformat() + "Z",
            "proofValue": base64.b64encode(sig).decode("ascii"),
            "signed_representation": base64.b64encode(data).decode("ascii"),
        }
        # return payload copy with proof and marker
        out = dict(payload)
        out["proof"] = proof
        out["__signed"] = True
        return out

    def verify(self, payload: Dict[str, Any]) -> bool:
        proof = payload.get("proof")
        if not proof:
            return False
        proof_value = base64.b64decode(proof.get("proofValue"))
        # If the proof contains the exact signed representation, use it.
        signed_repr_b64 = proof.get("signed_representation")
        if signed_repr_b64:
            data = base64.b64decode(signed_repr_b64)
        else:
            # fallback: canonicalize current payload without proof
            copy = dict(payload)
            copy.pop("proof", None)
            data = json.dumps(copy, sort_keys=True, separators=(",", ":")).encode("utf-8")
        try:
            self._pub.verify(
                proof_value,
                data,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False

