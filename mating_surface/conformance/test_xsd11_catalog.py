from __future__ import annotations

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "tools" / "xsd11_catalog.py"
SPEC = importlib.util.spec_from_file_location("xsd11_catalog", MODULE_PATH)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


XSD = b'''<?xml version="1.0" encoding="UTF-8"?>
<xs:schema xmlns:vc="http://www.w3.org/2007/XMLSchema-versioning"
           xmlns:xs="http://www.w3.org/2001/XMLSchema"
           xmlns="http://www.sisostds.org/schemas/C2SIM/1.1"
           targetNamespace="http://www.sisostds.org/schemas/C2SIM/1.1"
           elementFormDefault="qualified"
           vc:minVersion="1.1">
  <xs:simpleType name="IdentifierType">
    <xs:restriction base="xs:string">
      <xs:minLength value="1"/>
    </xs:restriction>
  </xs:simpleType>
  <xs:complexType name="MessageType">
    <xs:sequence>
      <xs:element name="Identifier" type="IdentifierType"/>
    </xs:sequence>
  </xs:complexType>
  <xs:element name="Message" type="MessageType"/>
</xs:schema>
'''


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def transaction(data: bytes, *, mode: str = "rehearsal", digest: str | None = None) -> dict:
    return {
        "schema": "standards-mating-surface-artifact-transaction/1",
        "status": "pass",
        "admission": {
            "schema": "standards-mating-surface-artifact-admission/1",
            "admissionId": "standardartifactadmission1_fixture",
            "artifactSha256": digest or sha256(data),
            "standardId": "siso-std-019-2020-c2sim",
            "standardRevision": "fixture C2SIM",
            "xml": {
                "targetNamespace": "http://www.sisostds.org/schemas/C2SIM/1.1"
            },
        },
        "use": {
            "schema": "standards-mating-surface-artifact-use/1",
            "useId": "standardartifactuse1_fixture",
            "mode": mode,
        },
    }


class Xsd11CatalogTests(unittest.TestCase):
    def compile(self, receipt: dict) -> dict:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            xsd_path = root / "fixture.xsd"
            receipt_path = root / "receipt.json"
            xsd_path.write_bytes(XSD)
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            return MODULE.compile_catalog(xsd_path, receipt_path)

    def test_compiles_exact_schema_into_deterministic_inventory(self) -> None:
        first = self.compile(transaction(XSD))
        second = self.compile(transaction(XSD))
        self.assertEqual(first["catalogId"], second["catalogId"])
        self.assertEqual(first["targetNamespace"], "http://www.sisostds.org/schemas/C2SIM/1.1")
        self.assertEqual(first["xsdVersion"], "1.1")
        self.assertEqual(first["counts"]["globalElements"], 1)
        self.assertEqual(first["counts"]["globalTypes"], 2)
        self.assertEqual(first["globalElements"][0]["localName"], "Message")
        self.assertIn("IdentifierType", {row["localName"] for row in first["globalTypes"]})
        self.assertNotIn("fixture value", json.dumps(first))

    def test_refuses_bytes_outside_the_admission(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "do not match the admitted artifact"):
            self.compile(transaction(XSD, digest="0" * 64))

    def test_refuses_operational_use_of_public_reference_catalog(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "test or rehearsal"):
            self.compile(transaction(XSD, mode="operational"))

    def test_refuses_another_standard(self) -> None:
        receipt = transaction(XSD)
        receipt["admission"]["standardId"] = "invented-standard"
        with self.assertRaisesRegex(RuntimeError, "another standard"):
            self.compile(receipt)


if __name__ == "__main__":
    unittest.main()
