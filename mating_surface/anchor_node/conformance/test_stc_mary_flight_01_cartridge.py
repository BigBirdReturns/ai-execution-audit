from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ANCHOR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ANCHOR))

import stc_mary_flight_01_cartridge as tool
import verify_stc_mary_flight_01_cartridge as verifier
import verify_stc_mary_flight_01_cartridge_bootstrap as bootstrap

PROFILE = ANCHOR / "stc-mary-flight-01-cartridge-profile-01.json"
BOOTSTRAP = ANCHOR / "verify_stc_mary_flight_01_cartridge_bootstrap.py"
MAIN_TOOL = ANCHOR / "stc_mary_flight_01_cartridge.py"
EMBEDDED_VERIFIER_SOURCE = ANCHOR / "verify_stc_mary_flight_01_cartridge.py"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_pretty(path: Path, value: dict) -> None:
    path.write_bytes(verifier.pretty_json_bytes(value))


def resign_manifest(root: Path) -> None:
    manifest = load_json(root / "MANIFEST.json")
    rows = []
    for relative in sorted(verifier.EXPECTED_FILES):
        data = (root / relative).read_bytes()
        rows.append({"path": relative, "bytes": len(data), "sha256": verifier.sha256_bytes(data)})
    manifest_body = {
        "schema": verifier.MANIFEST_SCHEMA,
        "profileId": verifier.PROFILE_ID,
        "cartridgeId": manifest["cartridgeId"],
        "terminal": verifier.TERMINAL,
        "memberCount": len(rows),
        "members": rows,
        "authority": verifier.AUTHORITY,
        "claimBoundary": manifest["claimBoundary"],
    }
    manifest = {**manifest_body, "bundleId": verifier.content_id("stcmarycartridgebundle1", manifest_body)}
    write_pretty(root / "MANIFEST.json", manifest)


def mutate_json_and_resign(root: Path, relative: str, mutation) -> None:
    path = root / relative
    value = load_json(path)
    mutation(value)
    write_pretty(path, value)
    resign_manifest(root)


def run_bootstrap(
    root: Path,
    out: Path | None = None,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
) -> tuple[int, dict]:
    command = [sys.executable, str(BOOTSTRAP), str(root)]
    if out is not None:
        command.extend(["--out", str(out)])
    completed = subprocess.run(
        command,
        cwd=str(cwd or root.parent),
        check=False,
        capture_output=True,
        env=env,
    )
    payload = out.read_bytes() if out is not None and out.exists() and completed.returncode == 0 else completed.stdout
    return completed.returncode, json.loads(payload.decode("utf-8"))


class CartridgeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="stc-mary-cartridge-test-")
        self.parent = Path(self.temp.name)
        self.root = self.parent / "cartridge"
        self.build = tool.build_cartridge(PROFILE, self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_01_profile_validates(self) -> None:
        profile = tool.load_profile(PROFILE)
        self.assertEqual(profile["profileId"], verifier.PROFILE_ID)
        self.assertEqual(verifier.PROFILE_CANONICAL_SHA256, "c3f4f7a2ca45a9cfd08cc4d19cd48b5c0c4fbf013f6783e092cb8a3701902b50")

    def test_02_build_and_authenticated_verify(self) -> None:
        code, verdict = run_bootstrap(self.root)
        self.assertEqual(code, 0)
        self.assertEqual(verdict["status"], "PASS")
        self.assertTrue(verdict["bootstrapAuthenticated"])
        self.assertEqual(verdict["measuredVerifierSha256"], tool.EXPECTED_VERIFIER_SHA256)
        self.assertIn("measured-verifier-member-binding", verdict["checks"])
        self.assertEqual(verdict["authority"], "none")

    def test_03_deterministic_authoritative_bytes(self) -> None:
        other = self.parent / "cartridge-two"
        tool.build_cartridge(PROFILE, other)
        for relative in ("MANIFEST.json", *verifier.EXPECTED_FILES):
            self.assertEqual((self.root / relative).read_bytes(), (other / relative).read_bytes(), relative)

    def test_04_exact_file_and_directory_denominator(self) -> None:
        files = {p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_file()}
        dirs = {p.relative_to(self.root).as_posix() for p in self.root.rglob("*") if p.is_dir()}
        self.assertEqual(files, {"MANIFEST.json", *verifier.EXPECTED_FILES})
        self.assertEqual(dirs, verifier.EXPECTED_DIRECTORIES)

    def test_05_terminal_is_prepared_not_armed(self) -> None:
        status = load_json(self.root / "PUBLIC/status.json")
        self.assertEqual(status["terminal"], "PREPARED_NOT_ARMED")
        self.assertFalse(status["authorizationProduced"])
        self.assertFalse(status["workstationInitialized"])
        self.assertEqual(status["packetStagesRecorded"], 0)

    def test_06_cartridge_id_binds_mission_work_and_source(self) -> None:
        mission = load_json(self.root / "CARTRIDGE/mission.json")
        work = load_json(self.root / "CARTRIDGE/work-unit.json")
        source = load_json(self.root / "RECOVERY/source-binding.json")
        self.assertEqual(mission["workUnitId"], work["workUnitId"])
        self.assertEqual(mission["sourceBindingId"], source["sourceBindingId"])
        self.assertEqual(self.build["cartridgeId"], mission["cartridgeId"])
        profile = load_json(PROFILE)
        self.assertNotIn("flightConductor", profile["sourceCoordinates"])
        self.assertNotIn("flightConductor", source["sourceCoordinates"])
        provenance_before = {"activeConductor": "772ce582e1b19b7a2060c50be8ebf40c1f8723b2"}
        provenance_after = {"activeConductor": "dd486472a8c610a20ee062dd6746c86fe8ede4b4"}
        self.assertNotEqual(provenance_before, provenance_after)
        other = self.parent / "cartridge-provenance-independent"
        rebuilt = tool.build_cartridge(PROFILE, other)
        self.assertEqual(self.build["bundleId"], rebuilt["bundleId"])
        self.assertEqual(self.build["cartridgeId"], rebuilt["cartridgeId"])
        self.assertEqual(self.build["missionId"], rebuilt["missionId"])
        self.assertEqual(self.build["workUnitId"], rebuilt["workUnitId"])
        self.assertEqual(self.build["sourceBindingId"], rebuilt["sourceBindingId"])

    def test_07_mission_authority_promotion_refused_after_resign(self) -> None:
        mutate_json_and_resign(self.root, "CARTRIDGE/mission.json", lambda value: value.__setitem__("systemAuthority", "mission"))
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "MISSION_RECONSTRUCTION_FAILED")

    def test_08_stage_denominator_mutation_refused_after_resign(self) -> None:
        mutate_json_and_resign(self.root, "CARTRIDGE/mission.json", lambda value: value["packetStageSequence"].pop())
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "MISSION_RECONSTRUCTION_FAILED")

    def test_09_source_coordinate_mutation_refused_after_resign(self) -> None:
        def change(value: dict) -> None:
            value["sourceCoordinates"]["axmHeadSupplier"]["commit"] = "0" * 40
        mutate_json_and_resign(self.root, "RECOVERY/source-binding.json", change)
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "SOURCE_BINDING_RECONSTRUCTION_FAILED")

    def test_10_work_unit_feed_mutation_refused_after_resign(self) -> None:
        mutate_json_and_resign(self.root, "CARTRIDGE/work-unit.json", lambda value: value["feed"].__setitem__("records", 1))
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "WORK_UNIT_RECONSTRUCTION_FAILED")

    def test_11_status_workstation_promotion_refused_after_resign(self) -> None:
        mutate_json_and_resign(self.root, "PUBLIC/status.json", lambda value: value.__setitem__("workstationInitialized", True))
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "PUBLIC_STATUS_RECONSTRUCTION_FAILED")

    def test_12_status_boolean_integer_substitution_refused_after_resign(self) -> None:
        mutate_json_and_resign(self.root, "PUBLIC/status.json", lambda value: value.__setitem__("packetStagesRecorded", False))
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "PUBLIC_STATUS_RECONSTRUCTION_FAILED")

    def test_13_unknown_file_refused(self) -> None:
        (self.root / "UNKNOWN.txt").write_text("x\n", encoding="utf-8")
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "FILE_DENOMINATOR_INVALID")

    def test_14_missing_file_refused(self) -> None:
        (self.root / "PUBLIC/status.json").unlink()
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "FILE_DENOMINATOR_INVALID")

    def test_15_unknown_directory_refused(self) -> None:
        (self.root / "EXTRA").mkdir()
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "DIRECTORY_DENOMINATOR_INVALID")

    def test_16_verifier_substitution_refused_before_execution(self) -> None:
        embedded = self.root / "RECOVERY/verify_cartridge.py"
        embedded.write_text("raise SystemExit('MALICIOUS EXECUTED')\n", encoding="utf-8")
        resign_manifest(self.root)
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "EMBEDDED_VERIFIER_UNTRUSTED")
        self.assertFalse(verdict["embeddedVerifierExecuted"])

        hijack = self.parent / "cartridge-import-hijack"
        tool.build_cartridge(PROFILE, hijack)
        marker = self.parent / "import-hijack-executed.txt"
        malicious_module = "\n".join(
            (
                "import os",
                "with open(os.environ['STC_MARY_IMPORT_HIJACK_MARKER'], 'w', encoding='utf-8') as handle:",
                "    handle.write('executed')",
                "print('{\"status\":\"PASS\",\"bootstrapAuthenticated\":false,\"authority\":\"none\"}')",
                "raise SystemExit(0)",
                "",
            )
        )
        (hijack / "RECOVERY/hashlib.py").write_text(malicious_module, encoding="utf-8", newline="\n")
        environment = os.environ.copy()
        environment["STC_MARY_IMPORT_HIJACK_MARKER"] = str(marker)
        code, verdict = run_bootstrap(hijack, env=environment)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "FILE_DENOMINATOR_INVALID")
        self.assertFalse(marker.exists())

        member_race = self.parent / "cartridge-verifier-member-race"
        tool.build_cartridge(PROFILE, member_race)
        measured_bytes = (member_race / "RECOVERY/verify_cartridge.py").read_bytes()
        (member_race / "RECOVERY/verify_cartridge.py").write_text(
            "# substituted after bootstrap measurement\n",
            encoding="utf-8",
            newline="\n",
        )
        resign_manifest(member_race)
        raced = subprocess.run(
            [
                sys.executable,
                "-I",
                "-S",
                "-c",
                bootstrap.ISOLATED_VERIFIER_LAUNCHER,
                str(member_race),
            ],
            input=measured_bytes,
            check=False,
            capture_output=True,
        )
        raced_verdict = json.loads(raced.stdout.decode("utf-8"))
        self.assertNotEqual(raced.returncode, 0)
        self.assertEqual(raced_verdict["code"], "MEASURED_VERIFIER_MEMBER_MISMATCH")

    def test_17_profile_substitution_refused_after_resign(self) -> None:
        mutate_json_and_resign(self.root, "RECOVERY/profile.json", lambda value: value.__setitem__("claimBoundary", "promoted"))
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "PROFILE_CANONICAL_DIGEST_INVALID")

    def test_18_manifest_member_count_type_refused(self) -> None:
        manifest = load_json(self.root / "MANIFEST.json")
        manifest["memberCount"] = True
        write_pretty(self.root / "MANIFEST.json", manifest)
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "INTEGER_REQUIRED")

    def test_19_manifest_bundle_id_forgery_refused(self) -> None:
        manifest = load_json(self.root / "MANIFEST.json")
        manifest["bundleId"] = "stcmarycartridgebundle1_" + "0" * 64
        write_pretty(self.root / "MANIFEST.json", manifest)
        code, verdict = run_bootstrap(self.root)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "BUNDLE_ID_INVALID")

    def test_20_output_inside_cartridge_refused(self) -> None:
        verdict_output = self.root / "verdict.json"
        code, verdict = run_bootstrap(self.root, verdict_output)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "VERDICT_INSIDE_CARTRIDGE")
        self.assertFalse(verdict_output.exists())

        projection_output = self.root / "projection.json"
        completed = subprocess.run(
            [sys.executable, str(MAIN_TOOL), "public-projection", str(self.root), "--out", str(projection_output)],
            check=False,
            capture_output=True,
        )
        projection_verdict = json.loads(completed.stdout.decode("utf-8"))
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(projection_verdict["code"], "PROJECTION_INSIDE_CARTRIDGE")
        self.assertFalse(projection_output.exists())
        verify_code, verify_verdict = run_bootstrap(self.root)
        self.assertEqual(verify_code, 0)
        self.assertEqual(verify_verdict["status"], "PASS")

        symlink_root = self.parent / "cartridge-root-symlink"
        try:
            symlink_root.symlink_to(self.root, target_is_directory=True)
        except OSError as exc:
            if os.name == "nt":
                self.skipTest(f"Windows runner cannot create directory symlink: {exc}")
            raise

        symlink_verdict_out = self.parent / "symlink-verdict.json"
        code, symlink_verdict = run_bootstrap(symlink_root, symlink_verdict_out)
        self.assertNotEqual(code, 0)
        self.assertEqual(symlink_verdict["code"], "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(symlink_verdict_out.exists())

        direct = subprocess.run(
            [sys.executable, str(EMBEDDED_VERIFIER_SOURCE), str(symlink_root)],
            check=False,
            capture_output=True,
        )
        direct_verdict = json.loads(direct.stdout.decode("utf-8"))
        self.assertNotEqual(direct.returncode, 0)
        self.assertEqual(direct_verdict["code"], "CARTRIDGE_ROOT_INVALID")

        symlink_projection_out = self.parent / "symlink-projection.json"
        projected = subprocess.run(
            [sys.executable, str(MAIN_TOOL), "public-projection", str(symlink_root), "--out", str(symlink_projection_out)],
            check=False,
            capture_output=True,
        )
        projected_verdict = json.loads(projected.stdout.decode("utf-8"))
        self.assertNotEqual(projected.returncode, 0)
        self.assertEqual(projected_verdict["code"], "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(symlink_projection_out.exists())

        with self.assertRaises(tool.BuildError) as library_projection:
            tool.public_projection(symlink_root)
        self.assertEqual(library_projection.exception.code, "CARTRIDGE_ROOT_INVALID")
        with self.assertRaises(verifier.CartridgeError) as library_verification:
            verifier.verify_cartridge(symlink_root)
        self.assertEqual(library_verification.exception.code, "CARTRIDGE_ROOT_INVALID")

        ancestor_link = self.parent / "cartridge-parent-symlink"
        ancestor_link.symlink_to(self.root.parent, target_is_directory=True)
        nested_symlink_root = ancestor_link / self.root.name

        nested_bootstrap_out = self.parent / "nested-symlink-bootstrap-verdict.json"
        code, nested_bootstrap = run_bootstrap(nested_symlink_root, nested_bootstrap_out)
        self.assertNotEqual(code, 0)
        self.assertEqual(nested_bootstrap["code"], "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(nested_bootstrap_out.exists())

        nested_direct_out = self.parent / "nested-symlink-direct-verdict.json"
        nested_direct = subprocess.run(
            [sys.executable, str(EMBEDDED_VERIFIER_SOURCE), str(nested_symlink_root), "--out", str(nested_direct_out)],
            check=False,
            capture_output=True,
        )
        nested_direct_verdict = json.loads(nested_direct.stdout.decode("utf-8"))
        self.assertNotEqual(nested_direct.returncode, 0)
        self.assertEqual(nested_direct_verdict["code"], "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(nested_direct_out.exists())

        nested_tool_verify_out = self.parent / "nested-symlink-tool-verdict.json"
        nested_tool_verify = subprocess.run(
            [sys.executable, str(MAIN_TOOL), "verify", str(nested_symlink_root), "--out", str(nested_tool_verify_out)],
            check=False,
            capture_output=True,
        )
        nested_tool_verify_verdict = json.loads(nested_tool_verify.stdout.decode("utf-8"))
        self.assertNotEqual(nested_tool_verify.returncode, 0)
        self.assertEqual(nested_tool_verify_verdict["code"], "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(nested_tool_verify_out.exists())

        nested_projection_out = self.parent / "nested-symlink-projection.json"
        nested_projected = subprocess.run(
            [sys.executable, str(MAIN_TOOL), "public-projection", str(nested_symlink_root), "--out", str(nested_projection_out)],
            check=False,
            capture_output=True,
        )
        nested_projected_verdict = json.loads(nested_projected.stdout.decode("utf-8"))
        self.assertNotEqual(nested_projected.returncode, 0)
        self.assertEqual(nested_projected_verdict["code"], "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(nested_projection_out.exists())

        nested_library_bootstrap_out = self.parent / "nested-symlink-library-bootstrap.json"
        with self.assertRaises(tool.BuildError) as nested_library_bootstrap:
            tool.run_bootstrap(nested_symlink_root, nested_library_bootstrap_out)
        self.assertEqual(nested_library_bootstrap.exception.code, "CARTRIDGE_ROOT_INVALID")
        self.assertFalse(nested_library_bootstrap_out.exists())

        with self.assertRaises(tool.BuildError) as nested_library_projection:
            tool.public_projection(nested_symlink_root)
        self.assertEqual(nested_library_projection.exception.code, "CARTRIDGE_ROOT_INVALID")
        with self.assertRaises(verifier.CartridgeError) as nested_library_verification:
            verifier.verify_cartridge(nested_symlink_root)
        self.assertEqual(nested_library_verification.exception.code, "CARTRIDGE_ROOT_INVALID")

    def test_21_existing_output_refused(self) -> None:
        out = self.parent / "verdict.json"
        out.write_text("existing\n", encoding="utf-8")
        code, verdict = run_bootstrap(self.root, out)
        self.assertNotEqual(code, 0)
        self.assertEqual(verdict["code"], "VERDICT_OUTPUT_EXISTS")

    def test_22_repository_local_build_refused(self) -> None:
        repo = self.parent / "repo"
        repo.mkdir()
        (repo / ".git").mkdir()
        with self.assertRaises(tool.BuildError) as caught:
            tool.build_cartridge(PROFILE, repo / "product")
        self.assertEqual(caught.exception.code, "REPOSITORY_LOCAL_OUTPUT_REFUSED")

    def test_23_foreign_working_directory_bootstrap(self) -> None:
        foreign = self.parent / "foreign"
        foreign.mkdir()
        code, verdict = run_bootstrap(self.root, cwd=foreign)
        self.assertEqual(code, 0)
        self.assertTrue(verdict["bootstrapAuthenticated"])

        relative_parent = self.parent / "relative-base"
        relative_parent.mkdir()
        relative_root = relative_parent / "cartridge"
        shutil.copytree(self.root, relative_root)
        relative_root_argument = Path("relative-base") / "cartridge"
        relative_output_argument = Path("relative-verdict.json")
        relative_output = self.parent / relative_output_argument
        misplaced_output = relative_parent / relative_output_argument

        relative_verify = subprocess.run(
            [
                sys.executable,
                str(MAIN_TOOL),
                "verify",
                str(relative_root_argument),
                "--out",
                str(relative_output_argument),
            ],
            cwd=str(self.parent),
            check=False,
            capture_output=True,
        )
        self.assertEqual(relative_verify.returncode, 0, relative_verify.stdout.decode("utf-8", errors="replace"))
        self.assertTrue(relative_output.is_file())
        relative_verdict = load_json(relative_output)
        self.assertEqual(relative_verdict["status"], "PASS")
        self.assertTrue(relative_verdict["bootstrapAuthenticated"])
        self.assertFalse(misplaced_output.exists())

        relative_projection = subprocess.run(
            [sys.executable, str(MAIN_TOOL), "public-projection", str(relative_root_argument)],
            cwd=str(self.parent),
            check=False,
            capture_output=True,
        )
        self.assertEqual(relative_projection.returncode, 0, relative_projection.stdout.decode("utf-8", errors="replace"))
        relative_projection_value = json.loads(relative_projection.stdout.decode("utf-8"))
        self.assertEqual(relative_projection_value["authority"], "none")
        self.assertEqual(relative_projection_value["publicEvidenceBodies"], 0)

    def test_24_public_projection_is_body_free(self) -> None:
        projection = tool.public_projection(self.root)
        encoded = json.dumps(projection, sort_keys=True)
        self.assertNotIn("privatePath", encoded)
        self.assertNotIn("hostname", encoded)
        self.assertNotIn("credential", encoded)
        self.assertEqual(projection["publicEvidenceBodies"], 0)
        self.assertEqual(projection["authority"], "none")

        authenticated_projection = dict(projection)
        original_bootstrap = tool.run_bootstrap

        def mutate_status_after_authentication(root: Path, out: Path | None = None) -> dict:
            verdict = original_bootstrap(root, out)
            (self.root / "PUBLIC/status.json").write_text(
                json.dumps(
                    {
                        "privatePath": "unverified-post-authentication-substitution",
                        "authority": "mission",
                    },
                    sort_keys=True,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            return verdict

        with patch.object(tool, "run_bootstrap", side_effect=mutate_status_after_authentication):
            projection_after_disk_mutation = tool.public_projection(self.root)

        self.assertEqual(projection_after_disk_mutation, authenticated_projection)
        self.assertNotIn("privatePath", projection_after_disk_mutation)
        self.assertEqual(projection_after_disk_mutation["authority"], "none")

    def test_25_lf_only_and_no_network_clients(self) -> None:
        for relative in ("MANIFEST.json", *verifier.EXPECTED_FILES):
            self.assertNotIn(b"\r", (self.root / relative).read_bytes(), relative)
        for source in (MAIN_TOOL, EMBEDDED_VERIFIER_SOURCE, BOOTSTRAP):
            text = source.read_text(encoding="utf-8")
            for forbidden in ("import socket", "import urllib", "import requests", "import httpx", "import aiohttp"):
                self.assertNotIn(forbidden, text, f"{source.name}: {forbidden}")


if __name__ == "__main__":
    unittest.main()
