from __future__ import annotations

import getpass
import importlib.util
import os
import platform
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import (
    TOOLCHAIN_PROFILE_ID,
    CommandResult,
    artifact_public_projection,
    as_list,
    canonical_json,
    content_id,
    executable,
    hash_artifact,
    parse_json_output,
    require,
    run_command,
    run_powershell,
    sha256_bytes,
    validate_new_private_root,
    write_json,
)
from .halo3_seat import load_halo3_seat_config, resolve_halo3_seat


def module_version(name: str) -> dict[str, Any]:
    available = importlib.util.find_spec(name) is not None
    if not available:
        return {"available": False, "version": None}
    try:
        module = __import__(name)
        return {"available": True, "version": str(getattr(module, "__version__", "unknown"))}
    except Exception as error:
        return {"available": False, "version": None, "errorClass": type(error).__name__}


def torch_probe() -> dict[str, Any]:
    if importlib.util.find_spec("torch") is None:
        return {"available": False, "version": None, "cudaAvailable": False, "deviceCount": 0, "devices": []}
    try:
        import torch  # type: ignore

        cuda_available = bool(torch.cuda.is_available())
        devices = []
        if cuda_available:
            for index in range(torch.cuda.device_count()):
                properties = torch.cuda.get_device_properties(index)
                uuid_value = str(getattr(properties, "uuid", "")).strip()
                if uuid_value and not uuid_value.startswith("GPU-"):
                    uuid_value = f"GPU-{uuid_value}"
                pci_domain = getattr(properties, "pci_domain_id", None)
                pci_bus = getattr(properties, "pci_bus_id", None)
                pci_device = getattr(properties, "pci_device_id", None)
                pci_bus_id = None
                if all(isinstance(value, int) for value in (pci_domain, pci_bus, pci_device)):
                    pci_bus_id = f"{pci_domain:08X}:{pci_bus:02X}:{pci_device:02X}.0"
                devices.append({
                    "index": index,
                    "name": properties.name,
                    "uuid": uuid_value or None,
                    "pciBusId": pci_bus_id,
                    "totalMemoryBytes": int(properties.total_memory),
                    "computeCapability": [int(properties.major), int(properties.minor)],
                    "multiProcessorCount": int(properties.multi_processor_count),
                })
        return {
            "available": True,
            "version": str(torch.__version__),
            "cudaRuntime": str(getattr(torch.version, "cuda", None)),
            "cudaAvailable": cuda_available,
            "deviceCount": len(devices),
            "devices": devices,
        }
    except Exception as error:
        return {"available": False, "version": None, "cudaAvailable": False, "deviceCount": 0, "devices": [], "errorClass": type(error).__name__}


def nvidia_inventory() -> tuple[CommandResult, list[dict[str, Any]]]:
    fields = [
        "index", "name", "uuid", "pci.bus_id", "memory.total", "memory.free",
        "driver_version", "pstate", "temperature.gpu", "power.draw", "power.limit",
        "clocks.current.graphics", "compute_mode",
    ]
    query = run_command([
        "nvidia-smi",
        f"--query-gpu={','.join(fields)}",
        "--format=csv,noheader,nounits",
    ], timeout=30.0)
    rows: list[dict[str, Any]] = []
    if query.available and query.returncode == 0:
        for line in query.stdout.splitlines():
            parts = [part.strip() for part in line.split(",")]
            if len(parts) != len(fields):
                continue
            row = dict(zip(fields, parts))
            for numeric in ["index", "memory.total", "memory.free", "temperature.gpu", "clocks.current.graphics"]:
                try:
                    row[numeric] = int(float(str(row[numeric])))
                except ValueError:
                    pass
            for numeric in ["power.draw", "power.limit"]:
                try:
                    row[numeric] = float(str(row[numeric]))
                except ValueError:
                    pass
            rows.append(row)
    return query, rows


def windows_inventory() -> dict[str, Any]:
    if os.name != "nt":
        return {"applicable": False}
    scripts = {
        "operatingSystem": "Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,BuildNumber,OSArchitecture,LastBootUpTime | ConvertTo-Json -Compress",
        "computerSystem": "Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,TotalPhysicalMemory | ConvertTo-Json -Compress",
        "processors": "@(Get-CimInstance Win32_Processor | Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,MaxClockSpeed) | ConvertTo-Json -Compress",
        "displayAndAiDevices": "@(Get-PnpDevice -PresentOnly | Where-Object { $_.Class -eq 'Display' -or $_.FriendlyName -match 'NPU|AI Boost|Neural|Thunderbolt' } | Select-Object Class,FriendlyName,Status,InstanceId) | ConvertTo-Json -Compress",
        "volumes": "@(Get-Volume | Select-Object DriveLetter,FileSystemLabel,FileSystem,HealthStatus,Size,SizeRemaining) | ConvertTo-Json -Compress",
        "networkAdapters": "@(Get-NetAdapter | Select-Object Name,InterfaceDescription,Status,LinkSpeed,MacAddress) | ConvertTo-Json -Compress",
        "defaultRoutes": "@(Get-NetRoute -DestinationPrefix '0.0.0.0/0' -ErrorAction SilentlyContinue | Select-Object InterfaceAlias,NextHop,RouteMetric,State) | ConvertTo-Json -Compress",
        "listeners": "@(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Select-Object LocalAddress,LocalPort,OwningProcess) | ConvertTo-Json -Compress",
        "latticeProcesses": "@(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match 'lattice' } | Select-Object ProcessName,Id,Path) | ConvertTo-Json -Compress",
        "latticeServices": "@(Get-Service -ErrorAction SilentlyContinue | Where-Object { $_.Name -match 'lattice' -or $_.DisplayName -match 'lattice' } | Select-Object Name,DisplayName,Status,StartType) | ConvertTo-Json -Compress",
    }
    output: dict[str, Any] = {"applicable": True, "raw": {}, "parsed": {}}
    for label, script in scripts.items():
        result = run_powershell(script, timeout=60.0)
        output["raw"][label] = result.private_record()
        output["parsed"][label] = parse_json_output(result)
    power = run_command(["powercfg", "/getactivescheme"], timeout=20.0)
    output["raw"]["activePowerScheme"] = power.private_record()
    output["parsed"]["activePowerScheme"] = power.stdout.strip() if power.returncode == 0 else None
    return output


def git_probe(repository: Path) -> dict[str, Any]:
    head = run_command(["git", "rev-parse", "HEAD"], cwd=repository)
    root = run_command(["git", "rev-parse", "--show-toplevel"], cwd=repository)
    status = run_command(["git", "status", "--porcelain=v1", "--untracked-files=normal"], cwd=repository)
    branch = run_command(["git", "branch", "--show-current"], cwd=repository)
    return {
        "head": head.stdout.strip() if head.returncode == 0 else None,
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "root": root.stdout.strip() if root.returncode == 0 else None,
        "clean": status.returncode == 0 and status.stdout == "",
        "statusSha256": sha256_bytes(status.stdout.encode("utf-8")),
        "commandReceipts": {
            "head": head.public_record(),
            "root": root.public_record(),
            "status": status.public_record(),
            "branch": branch.public_record(),
        },
        "privateStatus": status.private_record(),
    }


def local_probe(
    repository: Path,
    artifacts: Sequence[tuple[str, Path]],
    halo3_seat: Mapping[str, Any],
) -> dict[str, Any]:
    repository = repository.expanduser().resolve()
    require(repository.is_dir(), "REPOSITORY_MISSING", f"repository is absent: {repository}")
    commands = {
        "gitVersion": run_command(["git", "--version"]),
        "nodeVersion": run_command(["node", "--version"]),
        "pythonVersion": run_command([sys.executable, "--version"]),
        "powerShellVersion": run_powershell("$PSVersionTable.PSVersion.ToString()"),
        "nvidiaSmiVersion": run_command(["nvidia-smi", "--version"], timeout=30.0),
    }
    nvidia_query, gpus = nvidia_inventory()
    artifact_manifests = [hash_artifact(label, path) for label, path in artifacts]
    windows = windows_inventory()
    torch = torch_probe()
    halo3_observation = resolve_halo3_seat(
        halo3_seat,
        torch_devices=torch.get("devices", []),
    )
    body = {
        "schema": "stc-mary-local-readiness-private/1",
        "profileId": TOOLCHAIN_PROFILE_ID,
        "capturedAtUnixNs": time.time_ns(),
        "host": {
            "node": platform.node(),
            "user": getpass.getuser(),
            "platform": platform.platform(),
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "pythonExecutable": str(Path(sys.executable).resolve()),
            "pythonVersion": platform.python_version(),
        },
        "repository": git_probe(repository),
        "commands": {label: result.private_record() for label, result in commands.items()},
        "pythonModules": {
            "numpy": module_version("numpy"),
            "torch": {key: value for key, value in torch.items() if key != "devices"},
            "onnxruntime": module_version("onnxruntime"),
        },
        "torch": torch,
        "nvidiaQuery": nvidia_query.private_record(),
        "nvidiaGpus": gpus,
        "halo3Seat": dict(halo3_seat),
        "halo3SeatObservation": halo3_observation,
        "windows": windows,
        "artifacts": artifact_manifests,
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "authority": "none",
        "claimBoundary": "Private local readiness observation. It records actual local environment data but grants no physical, representative-operator, field-network, operational-C2, production-Lattice, mission, command, targeting, engagement, effector, or weapons qualification or authority.",
    }
    return {**body, "readinessId": content_id("stcmarylocalreadiness1", body)}


def public_readiness_projection(private: Mapping[str, Any]) -> dict[str, Any]:
    git_info = private["repository"]
    torch = private["torch"]
    gpus = private["nvidiaGpus"]
    windows = private.get("windows", {})
    windows_parsed = windows.get("parsed", {}) if isinstance(windows, Mapping) else {}
    lattice_processes = as_list(windows_parsed.get("latticeProcesses"))
    lattice_services = as_list(windows_parsed.get("latticeServices"))
    listeners = as_list(windows_parsed.get("listeners"))
    lattice_probe_complete = bool(isinstance(windows, Mapping) and windows.get("applicable") is True and "latticeProcesses" in windows_parsed and "latticeServices" in windows_parsed)
    body = {
        "schema": "stc-mary-local-readiness-public-projection/1",
        "profileId": private["profileId"],
        "readinessId": private["readinessId"],
        "repository": {
            "head": git_info["head"],
            "clean": git_info["clean"],
            "headRecorded": git_info["head"] is not None,
            "statusSha256": git_info["statusSha256"],
        },
        "commandAvailability": {
            label: {
                "available": row["available"],
                "returncode": row["returncode"],
                "receiptSha256": sha256_bytes(canonical_json(row).encode("utf-8")),
            }
            for label, row in private["commands"].items()
        },
        "backends": {
            "python": True,
            "numpy": bool(private["pythonModules"]["numpy"]["available"]),
            "torchCpu": bool(private["pythonModules"]["torch"]["available"]),
            "torchCuda": bool(torch["cudaAvailable"]),
        },
        "nvidia": {
            "seatCount": len(gpus),
            "memoryClassMiB": sorted([row.get("memory.total") for row in gpus if isinstance(row.get("memory.total"), int)]),
            "queryReceiptSha256": sha256_bytes(canonical_json(private["nvidiaQuery"]).encode("utf-8")),
        },
        "localSurfaces": {
            "listenerCount": len(listeners),
            "latticeProcessCount": len(lattice_processes),
            "latticeServiceCount": len(lattice_services),
            "latticeProbeComplete": lattice_probe_complete,
            "latticeAbsentByProcessServiceProbe": lattice_probe_complete and not lattice_processes and not lattice_services,
        },
        "artifacts": [artifact_public_projection(row) for row in private["artifacts"]],
        "privateBodyCount": 1,
        "publicPrivatePaths": 0,
        "externalServiceCalls": 0,
        "operationalCredentials": 0,
        "physicalEstateQualified": False,
        "representativeOperatorQualified": False,
        "fieldNetworkQualified": False,
        "operationalC2Qualified": False,
        "productionLatticeQualified": False,
        "authority": "none",
        "claimBoundary": "Body-free readiness projection. It reports counts, content identities, and admission facts only and grants no physical, representative-operator, field-network, operational-C2, production-Lattice, mission, command, targeting, engagement, effector, or weapons qualification or authority.",
    }
    return {**body, "projectionId": content_id("stcmarylocalreadinessprojection1", body)}


def doctor_command(args: Any) -> dict[str, Any]:
    repository = Path(args.repository)
    output = validate_new_private_root(Path(args.out), repository_root=repository)
    output.mkdir()
    artifacts: list[tuple[str, Path]] = []
    for item in args.artifact:
        require("=" in item, "ARTIFACT_ARGUMENT_INVALID", "artifact must be LABEL=PATH")
        label, raw_path = item.split("=", 1)
        artifacts.append((label, Path(raw_path)))
    halo3_seat = load_halo3_seat_config(args.halo3_seat_config)
    private = local_probe(repository, artifacts, halo3_seat)
    public = public_readiness_projection(private)
    marker_body = {
        "schema": "stc-mary-local-prep-root/1",
        "profileId": TOOLCHAIN_PROFILE_ID,
        "kind": "readiness",
        "readinessId": private["readinessId"],
        "authority": "none",
        "claimBoundary": "Marker for one private local readiness root outside public Git.",
    }
    marker = {**marker_body, "markerId": content_id("stcmarylocalpreproot1", marker_body)}
    write_json(output / "PREP-ROOT.json", marker)
    write_json(output / "readiness-private.json", private)
    write_json(output / "readiness-public-projection.json", public)
    return {"status": "PASS", "output": str(output), "readinessId": private["readinessId"], "projectionId": public["projectionId"]}
