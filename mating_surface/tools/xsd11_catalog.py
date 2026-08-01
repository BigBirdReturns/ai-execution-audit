#!/usr/bin/env python3
"""Compile an admitted XSD 1.1 artifact into a deterministic structural catalog.

The catalog is test and integration metadata. It inventories schema-defined global
components without inventing messages, field values, operator workflows, or
command semantics.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import xmlschema


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()}"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def local_name(value: str | None) -> str | None:
    if value is None:
        return None
    if value.startswith("{") and "}" in value:
        return value.split("}", 1)[1]
    return value


def qname(value: str | None, target_namespace: str) -> str | None:
    if value is None:
        return None
    if value.startswith("{"):
        return value
    return f"{{{target_namespace}}}{value}"


def component_type_name(component: Any) -> str | None:
    component_type = getattr(component, "type", None)
    name = getattr(component_type, "name", None)
    return str(name) if name is not None else None


def element_row(name: str, element: Any, target_namespace: str) -> dict[str, Any]:
    resolved_name = str(getattr(element, "name", None) or name)
    return {
        "localName": local_name(resolved_name),
        "qualifiedName": qname(resolved_name, target_namespace),
        "typeName": component_type_name(element),
        "abstract": bool(getattr(element, "abstract", False)),
        "nillable": bool(getattr(element, "nillable", False)),
    }


def type_row(name: str, component: Any, target_namespace: str) -> dict[str, Any]:
    resolved_name = str(getattr(component, "name", None) or name)
    kind = component.__class__.__name__
    return {
        "localName": local_name(resolved_name),
        "qualifiedName": qname(resolved_name, target_namespace),
        "kind": kind,
        "abstract": bool(getattr(component, "abstract", False)),
    }


def compile_catalog(xsd_path: Path, artifact_receipt_path: Path) -> dict[str, Any]:
    transaction = json.loads(artifact_receipt_path.read_text(encoding="utf-8"))
    if transaction.get("schema") != "standards-mating-surface-artifact-transaction/1":
        raise RuntimeError("artifact transaction receipt schema is invalid")
    if transaction.get("status") != "pass":
        raise RuntimeError("artifact transaction did not pass")
    admission = transaction.get("admission")
    use = transaction.get("use")
    if not isinstance(admission, dict) or not isinstance(use, dict):
        raise RuntimeError("artifact transaction is missing admission or use")

    observed_sha256 = sha256(xsd_path)
    if admission.get("artifactSha256") != observed_sha256:
        raise RuntimeError("XSD bytes do not match the admitted artifact")
    if admission.get("standardId") != "siso-std-019-2020-c2sim":
        raise RuntimeError("catalog compiler received another standard")
    if use.get("mode") not in {"test", "rehearsal"}:
        raise RuntimeError("public reference schema may only compile in test or rehearsal mode")

    schema = xmlschema.XMLSchema11(
        str(xsd_path),
        validation="strict",
        allow="local",
        defuse="always",
        use_fallback=False,
    )
    if not schema.built:
        raise RuntimeError("XMLSchema11 did not build the schema")

    target_namespace = str(schema.target_namespace or "")
    if target_namespace != admission["xml"]["targetNamespace"]:
        raise RuntimeError("XMLSchema11 target namespace differs from the artifact admission")

    elements = sorted(
        (
            element_row(str(name), element, target_namespace)
            for name, element in schema.elements.items()
        ),
        key=lambda row: (row["qualifiedName"] or "", row["typeName"] or ""),
    )
    types = sorted(
        (
            type_row(str(name), component, target_namespace)
            for name, component in schema.types.items()
        ),
        key=lambda row: (row["qualifiedName"] or "", row["kind"]),
    )
    namespaces = [
        {"prefix": str(prefix), "namespace": str(namespace)}
        for prefix, namespace in sorted(schema.namespaces.items(), key=lambda item: str(item[0]))
    ]

    body = {
        "artifactAdmissionId": admission["admissionId"],
        "artifactUseId": use["useId"],
        "artifactSha256": observed_sha256,
        "standardId": admission["standardId"],
        "standardRevision": admission["standardRevision"],
        "targetNamespace": target_namespace,
        "schemaVersionAttribute": str(schema.version) if schema.version is not None else None,
        "xsdVersion": str(schema.xsd_version),
        "validator": {
            "package": "xmlschema",
            "version": str(xmlschema.__version__),
            "class": "XMLSchema11",
            "validation": "strict",
            "networkPolicy": "local_only",
            "entityPolicy": "defuse_always",
        },
        "counts": {
            "globalElements": len(elements),
            "globalTypes": len(types),
            "namespaces": len(namespaces),
        },
        "namespaces": namespaces,
        "globalElements": elements,
        "globalTypes": types,
    }
    return {
        "schema": "standards-mating-surface-xsd11-catalog/1",
        "catalogId": digest("standardxsd11catalog1", body),
        **body,
        "claimBoundary": (
            "XMLSchema11 built this exact admitted XSD under strict, local-only, "
            "entity-defused conditions and inventoried its global components. "
            "No XML message instance was validated, no component was promoted into "
            "command authority, and this receipt does not convert a public reference "
            "snapshot into an official or operational standard artifact."
        ),
    }


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: xsd11_catalog.py <schema.xsd> <artifact-transaction.json> <catalog.json>",
            file=sys.stderr,
        )
        return 2
    xsd_path = Path(argv[0])
    artifact_receipt_path = Path(argv[1])
    output_path = Path(argv[2])
    catalog = compile_catalog(xsd_path, artifact_receipt_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(catalog, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "pass",
                "catalogId": catalog["catalogId"],
                "artifactSha256": catalog["artifactSha256"],
                "globalElements": catalog["counts"]["globalElements"],
                "globalTypes": catalog["counts"]["globalTypes"],
                "output": str(output_path),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
