from src.core.services.plugin_manager import PluginManager
from src.adapters.base_plugins.compute_local import LocalComputeDriver
from src.adapters.base_plugins.format_dcat import DCATFormatter
import json


def test_discover_base_plugins():
    pm = PluginManager()
    # discover base plugins by importing the base_plugins package
    pm.discover("src.adapters.base_plugins")

    assert "dcat" in pm.formatters or any(isinstance(v, type) for v in pm.formatters.values())
    assert "local" in pm.compute_drivers or any(isinstance(v, type) for v in pm.compute_drivers.values())


def test_dcat_formatter_output():
    asset = type("A", (), {"id": "1", "title": "T", "description": "D", "metadata": {}})()
    f = DCATFormatter()
    out = f.format(asset)
    assert out["id"] == "1"
    assert out["title"] == "T"


def test_local_compute_echo(tmp_path):
    driver = LocalComputeDriver()
    res = driver.run(["/bin/echo", "hello"]) 
    assert res["returncode"] == 0
    assert "hello" in res["stdout"]


def test_asset_publish_creates_catalog(tmp_path, monkeypatch):
    # run asset_publish pointing to tmp_path as working dir
    from src.adapters.cli.dm_cli import asset_publish
    import os

    monkeypatch.chdir(tmp_path)
    sample = tmp_path / "data.csv"
    sample.write_text("a,b,c\n1,2,3")

    asset_publish(str(sample))

    catalog_file = tmp_path / "catalog.json"
    assert catalog_file.exists()
    import json

    catalog = json.loads(catalog_file.read_text())
    assert "assets" in catalog
    assert len(catalog["assets"]) == 1
    a = catalog["assets"][0]
    assert a.get("__signed") is True
    assert "prov" in a
    # descriptor file
    # descriptor file should use the uuid and be under descriptors/{uuid}.jsonld
    catalog_asset = catalog["assets"][0]
    assert "uuid" in catalog_asset or "descriptor_uri" in catalog_asset
    desc_uri = catalog_asset.get("descriptor_uri")
    assert desc_uri is not None
    # descriptor path expected relative under descriptors/{uuid}.jsonld
    # extract uuid from descriptor_uri (last segment)
    uuid_seg = desc_uri.rstrip("/").split("/")[-1]
    desc_file = tmp_path / "descriptors" / (uuid_seg + ".jsonld")
    assert desc_file.exists()
    desc = json.loads(desc_file.read_text())
    assert "@id" in desc
    assert "dcat:title" in desc
    # ensure the descriptor points to the data
    assert "dcat:distribution" in desc and "@id" in desc["dcat:distribution"]


def test_signature_verifies(tmp_path, monkeypatch):
    # publish asset into tmp_path and verify signature via adapter
    from src.adapters.cli.dm_cli import asset_publish
    from src.adapters.crypto.signature_adapter import SignatureAdapter
    import json

    monkeypatch.chdir(tmp_path)
    sample = tmp_path / "data.csv"
    sample.write_text("x,y\n1,2")
    asset_publish(str(sample))

    catalog = json.loads((tmp_path / "catalog.json").read_text())
    a = catalog["assets"][0]
    assert "proof" in a

    signer = SignatureAdapter()
    assert signer.verify(a)


def test_asset_verify_cli_outputs(tmp_path, monkeypatch, capsys):
    from src.adapters.cli.dm_cli import asset_publish, asset_verify

    monkeypatch.chdir(tmp_path)
    sample = tmp_path / "data.csv"
    sample.write_text("x,y\n1,2")
    asset_publish(str(sample))

    catalog = json.loads((tmp_path / "catalog.json").read_text())
    a = catalog["assets"][0]
    # use id
    asset_verify(a.get("id"))
    captured = capsys.readouterr()
    assert "Signature valid: True" in captured.out
    assert ("Descriptor links to data: True" in captured.out) or ("Descriptor unavailable for checking relation" in captured.out) or (
        "Descriptor uses external scheme" in captured.out
    )
