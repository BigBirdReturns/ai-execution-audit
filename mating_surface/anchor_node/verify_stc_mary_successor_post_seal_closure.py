"""Close one sealed 0.2 successor flight, after sealing and after detached verification.

This is the only surface in the source set permitted to assert any of the following, and
it can assert them only because the objects they describe now exist:

    sealed run present
    public disposition present
    public disposition body-free
    sealed manifest valid
    detached verification PASS
    public evidence bodies 0
    private physical flight complete
    all stronger qualifications false

Every one of those was reserved away from Stage 16 precisely so that no stage record and
no pre-seal object would ever certify a future object. This verifier is where the debt is
paid, from measurement rather than from assertion: it re-reads the sealed directory,
re-hashes every manifest entry, and requires the supplied detached verification to be the
one the sealed run reproduces.

Completion of a private physical flight is *not* qualification of anything else. The
closure records, and requires, that every stronger qualification remains false.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

PROFILE_SCHEMA = "stc-mary/successor-packet-flight-profile/1"
PROFILE_ID = "stc-mary/successor-packet-flight-01@1"

AUTHORITY = "none"
MINIMUM_PYTHON = (3, 12)

CONTENT_ID_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*_[0-9a-f]{64}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

MAX_JSON_BYTES = 64 * 1024 * 1024

PRIVATE_VALUE_FRAGMENTS = ("password", "secret", "token", "credential", "api_key", "apikey")
WINDOWS_PATH_RE = re.compile(r"[A-Za-z]:[\\/]")
UNC_PATH_RE = re.compile(r"^\\\\")
POSIX_PATH_RE = re.compile(r"(?:^|\s)/(?:home|root|mnt|media|var|etc|opt|Users)/")

CLAIM_BOUNDARY = (
    "Post-seal closure for one synthetic sealed successor flight. It is the only surface that "
    "asserts the sealed run, public disposition, sealed manifest and detached verification, and "
    "it asserts them from measurement. Completing one local private physical flight qualifies no "
    "physical estate, representative operator, field network, operational C2 or production "
    "Lattice, and grants no mission, command, targeting, engagement, effector or weapons "
    "authority."
)


class PostSealClosureError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def fail(code: str, message: str) -> None:
    raise PostSealClosureError(code, message)


def require(condition: bool, code: str, message: str) -> None:
    if not condition:
        fail(code, message)


def canonical_json(value: Any) -> str:
    try:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    except (TypeError, ValueError) as exc:
        fail("NON_CANONICAL_JSON", str(exc))
        raise


def canonical_json_bytes(value: Any) -> bytes:
    return (canonical_json(value) + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def content_id(prefix: str, value: Any) -> str:
    return f"{prefix}_{sha256_bytes(canonical_json(value).encode('utf-8'))}"


def assert_identity(value: Mapping[str, Any], id_key: str, prefix: str, code: str, label: str) -> str:
    observed = value.get(id_key)
    require(isinstance(observed, str), code, f"{label} {id_key} is missing")
    body = {key: item for key, item in value.items() if key != id_key}
    require(observed == content_id(prefix, body), code, f"{label} {id_key} differs from its content identity")
    return observed


def exact_keys(value: Any, expected: Iterable[str], code: str, label: str) -> Mapping[str, Any]:
    require(isinstance(value, Mapping), code, f"{label} must be an object")
    require(set(value.keys()) == set(expected), code, f"{label} field denominator differs")
    return value


def assert_content_id(value: Any, code: str, label: str) -> str:
    require(
        isinstance(value, str) and CONTENT_ID_RE.fullmatch(value) is not None,
        code,
        f"{label} is not a content identity",
    )
    return value


def coordinate_component_is_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        if os.name == "nt" and path.exists():
            try:
                return bool(path.lstat().st_file_attributes & 0x400)
            except (OSError, AttributeError):
                return False
        return False
    except OSError:
        return False


def validate_lexical_coordinate(path: Path, *, label: str, code: str) -> Path:
    if any(part == os.pardir for part in path.parts):
        fail(code, f"{label} may not contain a parent-directory segment")
    absolute = Path(os.path.abspath(os.fspath(path.expanduser())))
    current = Path(absolute.parts[0])
    if coordinate_component_is_link(current):
        fail(code, f"{label} contains a symlink or junction component")
    for part in absolute.parts[1:]:
        current = current / part
        if coordinate_component_is_link(current):
            fail(code, f"{label} contains a symlink or junction component")
    return absolute


def is_within(path: Path, parent: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(parent.resolve(strict=False))
        return True
    except ValueError:
        return False


def read_bounded_bytes(path: Path, maximum: int, *, code: str, label: str) -> bytes:
    if coordinate_component_is_link(path):
        fail(code, f"{label} is a symlink or junction")
    try:
        stat = path.stat()
    except OSError as exc:
        fail(code, f"{label} could not be inspected: {exc}")
        raise
    require(path.is_file(), code, f"{label} is not a regular file")
    require(stat.st_size <= maximum, code, f"{label} exceeds the bounded read allocation")
    with path.open("rb") as handle:
        data = handle.read(maximum + 1)
    require(len(data) <= maximum, code, f"{label} changed during the bounded read")
    return data


def read_json_file(path: Path, *, code: str, label: str) -> Mapping[str, Any]:
    data = read_bounded_bytes(path, MAX_JSON_BYTES, code=code, label=label)
    try:
        value = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail(code, f"{label} is not valid UTF-8 JSON: {exc}")
        raise
    require(isinstance(value, Mapping), code, f"{label} must be a JSON object")
    return value


def iter_string_values(value: Any) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, Mapping):
        for key, item in value.items():
            yield str(key)
            yield from iter_string_values(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from iter_string_values(item)


def assert_no_private_material(value: Any, *, code: str, label: str) -> None:
    for text in iter_string_values(value):
        lowered = text.lower()
        for fragment in PRIVATE_VALUE_FRAGMENTS:
            require(fragment not in lowered, code, f"{label} carries a private-looking value")
        require(WINDOWS_PATH_RE.search(text) is None, code, f"{label} carries a local filesystem coordinate")
        require(UNC_PATH_RE.search(text) is None, code, f"{label} carries a UNC coordinate")
        require(POSIX_PATH_RE.search(text) is None, code, f"{label} carries a local filesystem coordinate")


# --------------------------------------------------------------------------------
# closure
# --------------------------------------------------------------------------------


def close_post_seal(
    *,
    packet: Path,
    sealed: Path,
    pre_seal_closure: Path,
    detached_verification: Path,
    profile_path: Path,
    repository: Path,
) -> dict[str, Any]:
    require(
        sys.version_info[:2] >= MINIMUM_PYTHON,
        "PYTHON_RUNTIME_UNSUPPORTED",
        f"this verifier requires Python {MINIMUM_PYTHON[0]}.{MINIMUM_PYTHON[1]} or newer",
    )
    packet = validate_lexical_coordinate(packet, label="packet root", code="PACKET_ROOT_INVALID")
    sealed = validate_lexical_coordinate(sealed, label="sealed directory", code="SEALED_OUTPUT_UNSAFE")
    repository = validate_lexical_coordinate(repository, label="repository root", code="SOURCE_ROOT_INVALID")
    profile = read_json_file(
        validate_lexical_coordinate(profile_path, label="successor flight profile", code="PROFILE_UNREADABLE"),
        code="PROFILE_UNREADABLE",
        label="successor flight profile",
    )
    require(profile.get("schema") == PROFILE_SCHEMA, "PROFILE_INVALID", "successor flight profile schema differs")
    require(profile.get("profileId") == PROFILE_ID, "PROFILE_INVALID", "successor flight profile identity differs")
    require(
        not is_within(sealed, repository),
        "SEALED_OUTPUT_UNSAFE",
        "the sealed directory must remain outside the public repository",
    )

    closure_law = profile["postSealClosure"]
    seal_law = profile["seal"]
    packet_law = profile["packet"]
    files = seal_law["files"]
    require(
        closure_law["mayBeAssertedBeforeSealing"] is False,
        "PROFILE_INVALID",
        "the profile permits post-seal assertions before sealing",
    )

    # ---- the packet actually sealed ------------------------------------------------
    state = read_json_file(
        packet / packet_law["files"]["state"], code="PACKET_STATE_INVALID", label="packet state"
    )
    exact_keys(state, packet_law["stateKeys"], "PACKET_STATE_INVALID", "packet state")
    assert_identity(
        state, packet_law["stateIdKey"], packet_law["stateIdPrefix"], "PACKET_STATE_INVALID", "packet state"
    )
    require(
        state["sealed"] is True,
        "POST_SEAL_ASSERTION_BEFORE_SEALING",
        "the packet is not sealed; no post-seal assertion may be made about it",
    )
    packet_id = assert_content_id(state["packetId"], "PACKET_STATE_INVALID", "packet identity")
    disposition_id = assert_content_id(
        state["sealedDispositionId"], "PACKET_STATE_INVALID", "sealed disposition identity"
    )

    # ---- the pre-seal closure this flight was sealed under ---------------------------
    pre_law = profile["preSealClosure"]
    closure = read_json_file(
        validate_lexical_coordinate(
            pre_seal_closure, label="pre-seal closure", code="PRE_SEAL_CLOSURE_ABSENT"
        ),
        code="PRE_SEAL_CLOSURE_INVALID",
        label="pre-seal closure",
    )
    exact_keys(closure, pre_law["keys"], "PRE_SEAL_CLOSURE_INVALID", "pre-seal closure")
    pre_seal_closure_id = assert_identity(
        closure, pre_law["idKey"], pre_law["idPrefix"], "PRE_SEAL_CLOSURE_INVALID", "pre-seal closure"
    )
    require(
        closure["status"] == pre_law["requiredStatus"] and closure["packetId"] == packet_id,
        "PRE_SEAL_CLOSURE_BINDING_INVALID",
        "the pre-seal closure does not close this packet",
    )

    # ---- sealed run, disposition, marker, manifest ------------------------------------
    marker = read_json_file(sealed / files["marker"], code="SEALED_MARKER_INVALID", label="sealed marker")
    exact_keys(marker, seal_law["markerKeys"], "SEALED_MARKER_INVALID", "sealed marker")
    assert_identity(
        marker, seal_law["markerIdKey"], seal_law["markerIdPrefix"], "SEALED_MARKER_INVALID", "sealed marker"
    )
    run_present = (sealed / files["run"]).is_file()
    require(run_present, "SEALED_RUN_ABSENT", "the sealed directory carries no sealed run")
    run = read_json_file(sealed / files["run"], code="SEALED_RUN_INVALID", label="sealed run")
    exact_keys(run, seal_law["runKeys"], "SEALED_RUN_INVALID", "sealed run")
    run_id = assert_identity(
        run, seal_law["runIdKey"], seal_law["runIdPrefix"], "SEALED_RUN_INVALID", "sealed run"
    )
    require(
        run["preSealClosureId"] == pre_seal_closure_id,
        "SEALED_RUN_BINDING_INVALID",
        "the sealed run was not sealed under this pre-seal closure",
    )

    disposition_present = (sealed / files["disposition"]).is_file()
    require(disposition_present, "SEALED_DISPOSITION_ABSENT", "the sealed directory carries no public disposition")
    disposition = read_json_file(
        sealed / files["disposition"], code="SEALED_DISPOSITION_INVALID", label="public disposition"
    )
    exact_keys(disposition, seal_law["dispositionKeys"], "SEALED_DISPOSITION_INVALID", "public disposition")
    assert_identity(
        disposition,
        seal_law["dispositionIdKey"],
        seal_law["dispositionIdPrefix"],
        "SEALED_DISPOSITION_INVALID",
        "public disposition",
    )
    require(
        disposition[seal_law["dispositionIdKey"]] == disposition_id
        and disposition["runId"] == run_id
        and disposition["packetId"] == packet_id
        and marker["runId"] == run_id
        and marker["dispositionId"] == disposition_id,
        "SEALED_BINDING_INVALID",
        "the packet, marker, run and disposition do not name one sealed flight",
    )

    manifest = read_json_file(sealed / files["manifest"], code="SEALED_MANIFEST_INVALID", label="sealed manifest")
    exact_keys(manifest, seal_law["manifestKeys"], "SEALED_MANIFEST_INVALID", "sealed manifest")
    assert_identity(
        manifest,
        seal_law["manifestIdKey"],
        seal_law["manifestIdPrefix"],
        "SEALED_MANIFEST_INVALID",
        "sealed manifest",
    )
    require(
        manifest["runId"] == run_id and manifest["dispositionId"] == disposition_id,
        "SEALED_MANIFEST_INVALID",
        "the sealed manifest belongs to another flight",
    )
    require(
        manifest["fileCount"] == len(manifest["files"])
        and [row["path"] for row in manifest["files"]] == list(seal_law["manifestFiles"]),
        "SEALED_MANIFEST_INVALID",
        "the sealed manifest file denominator differs",
    )
    manifest_valid = True
    for row in manifest["files"]:
        exact_keys(row, seal_law["manifestFileKeys"], "SEALED_MANIFEST_INVALID", "sealed manifest file")
        data = read_bounded_bytes(
            sealed / row["path"], MAX_JSON_BYTES, code="SEALED_FILE_MISMATCH", label=f"sealed file {row['path']}"
        )
        require(
            len(data) == row["bytes"] and sha256_bytes(data) == row["sha256"],
            "SEALED_FILE_MISMATCH",
            f"sealed file differs from the manifest: {row['path']}",
        )

    # ---- body freedom, measured rather than asserted -----------------------------------
    body_free = (
        disposition["publicEvidenceBodyCount"] == 0
        and marker["publicEvidenceBodyCount"] == 0
        and manifest["publicEvidenceBodyCount"] == 0
    )
    require(body_free, "PUBLIC_DISPOSITION_NOT_BODY_FREE", "the sealed result publishes evidence bodies")
    assert_no_private_material(
        disposition, code="PUBLIC_DISPOSITION_NOT_BODY_FREE", label="public disposition"
    )
    assert_no_private_material(run, code="SEALED_RUN_PRIVATE_MATERIAL", label="sealed run")

    # ---- the detached verification, and that it is this flight's --------------------------
    verification = read_json_file(
        validate_lexical_coordinate(
            detached_verification, label="detached verification", code="DETACHED_VERIFICATION_ABSENT"
        ),
        code="DETACHED_VERIFICATION_INVALID",
        label="detached verification",
    )
    exact_keys(verification, seal_law["verificationKeys"], "DETACHED_VERIFICATION_INVALID", "detached verification")
    assert_identity(
        verification,
        seal_law["verificationIdKey"],
        seal_law["verificationIdPrefix"],
        "DETACHED_VERIFICATION_INVALID",
        "detached verification",
    )
    stored = read_json_file(
        sealed / files["verification"], code="SEALED_VERIFICATION_INVALID", label="sealed verification"
    )
    require(
        canonical_json(stored) == canonical_json(verification),
        "DETACHED_VERIFICATION_MISMATCH",
        "the supplied detached verification is not the verification this sealed directory carries",
    )
    require(
        verification["runId"] == run_id
        and verification["dispositionId"] == disposition_id
        and verification["packetId"] == packet_id,
        "DETACHED_VERIFICATION_BINDING_INVALID",
        "the detached verification describes another flight",
    )
    require(
        verification["status"] == "PASS",
        "DETACHED_VERIFICATION_REFUSED",
        "the detached verification did not pass",
    )

    # ---- completion is not qualification ------------------------------------------------
    stronger = closure_law["strongerQualifications"]
    all_stronger_false = all(
        disposition[key] is False and verification[key] is False for key in stronger
    )
    require(
        all_stronger_false,
        "STRONGER_QUALIFICATION_CLAIMED",
        "the sealed result claims a stronger qualification than a local private flight",
    )
    require(
        disposition["missionAuthorityGranted"] is False
        and disposition["commandAuthorityGranted"] is False
        and verification["missionAuthorityGranted"] is False
        and verification["commandAuthorityGranted"] is False
        and disposition["authority"] == AUTHORITY
        and verification["authority"] == AUTHORITY
        and run["authority"] == AUTHORITY
        and marker["authority"] == AUTHORITY
        and manifest["authority"] == AUTHORITY,
        "AUTHORITY_WIDENED",
        "the sealed result grants authority",
    )
    require(
        disposition["privatePhysicalFlightCompleted"] is True,
        "PRIVATE_FLIGHT_NOT_COMPLETE",
        "the public disposition does not report a completed private physical flight",
    )

    body = {
        "schema": closure_law["schema"],
        "status": closure_law["requiredStatus"],
        "packetId": packet_id,
        "preSealClosureId": pre_seal_closure_id,
        "runId": run_id,
        "dispositionId": disposition_id,
        "verificationId": verification[seal_law["verificationIdKey"]],
        "sealedRunPresent": True,
        "dispositionPresent": True,
        "bodyFreePublicDisposition": True,
        "sealedManifestValid": manifest_valid,
        "detachedVerificationStatus": verification["status"],
        "publicEvidenceBodyCount": 0,
        "privatePhysicalFlightCompleted": True,
        "allStrongerQualificationsFalse": True,
        "missionAuthorityGranted": False,
        "commandAuthorityGranted": False,
        "authority": AUTHORITY,
        "claimBoundary": CLAIM_BOUNDARY,
    }
    closure_receipt = {**body, closure_law["idKey"]: content_id(closure_law["idPrefix"], body)}
    exact_keys(closure_receipt, closure_law["keys"], "POST_SEAL_CLOSURE_INVALID", "post-seal closure")
    for key, expected in closure_law["requiredValues"].items():
        require(
            closure_receipt[key] == expected and type(closure_receipt[key]) is type(expected),
            "POST_SEAL_CLOSURE_INVALID",
            f"the post-seal closure field {key} is not the exact value the contract requires",
        )
    assert_no_private_material(
        closure_receipt, code="POST_SEAL_CLOSURE_PRIVATE_MATERIAL", label="post-seal closure"
    )
    return closure_receipt


def refusal_document(code: str, message: str) -> dict[str, Any]:
    return {
        "schema": "stc-mary/successor-flight-post-seal-closure/1",
        "status": "REFUSED",
        "code": code,
        "message": message,
        "allStrongerQualificationsFalse": True,
        "missionAuthorityGranted": False,
        "commandAuthorityGranted": False,
        "authority": AUTHORITY,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Close one sealed 0.2 successor flight after detached verification")
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--sealed", type=Path, required=True)
    parser.add_argument("--pre-seal-closure", type=Path, required=True)
    parser.add_argument("--detached-verification", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--out", type=Path)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    try:
        output = None
        if args.out is not None:
            output = validate_lexical_coordinate(args.out, label="closure output", code="CLOSURE_PATH_INVALID")
            for forbidden, label in ((args.packet, "packet"), (args.sealed, "sealed directory")):
                if is_within(output, Path(os.path.abspath(os.fspath(forbidden)))):
                    fail("CLOSURE_INSIDE_MEASURED_SURFACE", f"the closure may not be written inside the {label}")
            if output.exists():
                fail("CLOSURE_OUTPUT_EXISTS", "post-seal closure output must not already exist")
        closure = close_post_seal(
            packet=args.packet,
            sealed=args.sealed,
            pre_seal_closure=args.pre_seal_closure,
            detached_verification=args.detached_verification,
            profile_path=args.profile,
            repository=args.repository_root,
        )
        data = canonical_json_bytes(closure)
        if output is None:
            sys.stdout.buffer.write(data)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_bytes(data)
        return 0
    except PostSealClosureError as exc:
        sys.stdout.buffer.write(canonical_json_bytes(refusal_document(exc.code, str(exc))))
        return 1
    except (OSError, ValueError) as exc:
        sys.stdout.buffer.write(
            canonical_json_bytes(refusal_document("POST_SEAL_CLOSURE_FILESYSTEM_ERROR", str(exc)))
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
