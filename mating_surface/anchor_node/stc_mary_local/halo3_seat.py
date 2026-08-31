from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping, Sequence

from .common import content_id, parse_json_output, require, run_command, run_powershell, safe_int, stable_keys


GPU_UUID_RE = re.compile(r"^GPU-[0-9A-Fa-f-]{36}$")
PCI_BUS_RE = re.compile(r"^(?:[0-9A-Fa-f]{8}:)?([0-9A-Fa-f]{2}):([0-9A-Fa-f]{2})\.([0-7])$")
PNP_PCI_RE = re.compile(r"^PCI\\VEN_([0-9A-Fa-f]{4})&DEV_([0-9A-Fa-f]{4})&", re.I)
TRANSPORT_CLASSES = {"internal_pcie", "thunderbolt_egpu", "external_pcie"}


def _bounded(value: Any, code: str, label: str, maximum: int = 4096) -> str:
    require(isinstance(value, str), code, f"{label} must be a string")
    result = value.strip()
    require(0 < len(result) <= maximum, code, f"{label} is empty or unbounded")
    return result


def halo3_seat_record(
    *,
    product_name: str,
    gpu_uuid: str,
    pci_bus_id: str,
    pnp_instance_id: str,
    transport_class: str,
    transport_anchor_pnp_instance_id: str | None,
    initial_cuda_device_index: int,
) -> dict[str, Any]:
    product_name = _bounded(product_name, "HALO3_SEAT_INVALID", "HALO3 product name", 256)
    gpu_uuid = _bounded(gpu_uuid, "HALO3_SEAT_INVALID", "HALO3 GPU UUID", 64)
    require(GPU_UUID_RE.fullmatch(gpu_uuid) is not None, "HALO3_SEAT_INVALID", "HALO3 GPU UUID differs")
    pci_bus_id = _bounded(pci_bus_id, "HALO3_SEAT_INVALID", "HALO3 PCI bus identity", 32).upper()
    require(PCI_BUS_RE.fullmatch(pci_bus_id) is not None, "HALO3_SEAT_INVALID", "HALO3 PCI bus identity differs")
    pnp_instance_id = _bounded(pnp_instance_id, "HALO3_SEAT_INVALID", "HALO3 PnP instance identity").upper()
    pnp_match = PNP_PCI_RE.match(pnp_instance_id)
    require(pnp_match is not None, "HALO3_SEAT_INVALID", "HALO3 PnP identity is not one PCI device")
    transport_class = _bounded(transport_class, "HALO3_SEAT_INVALID", "HALO3 transport class", 64).lower()
    require(transport_class in TRANSPORT_CLASSES, "HALO3_SEAT_INVALID", "HALO3 transport class differs")
    if transport_anchor_pnp_instance_id is not None:
        transport_anchor_pnp_instance_id = _bounded(
            transport_anchor_pnp_instance_id,
            "HALO3_SEAT_INVALID",
            "HALO3 transport anchor PnP identity",
        ).upper()
    require(
        (transport_class == "internal_pcie" and transport_anchor_pnp_instance_id is None)
        or (transport_class != "internal_pcie" and transport_anchor_pnp_instance_id is not None),
        "HALO3_SEAT_INVALID",
        "HALO3 transport class and anchor differ",
    )
    initial_cuda_device_index = safe_int(
        initial_cuda_device_index, 0, 31, "HALO3_SEAT_INVALID", "initial CUDA device index"
    )
    body = {
        "schema": "stc-mary-halo3-seat/1",
        "role": "HALO3",
        "vendorId": pnp_match.group(1).upper(),
        "deviceId": pnp_match.group(2).upper(),
        "pnpClass": "Display",
        "productName": product_name,
        "gpuUuid": gpu_uuid,
        "pciBusId": pci_bus_id,
        "pnpInstanceId": pnp_instance_id,
        "transportClass": transport_class,
        "transportAnchorPnpInstanceId": transport_anchor_pnp_instance_id,
        "initialCudaDeviceIndex": initial_cuda_device_index,
        "authority": "none",
    }
    return {**body, "seatId": content_id("stcmaryhalo3seat1", body)}


def validate_halo3_seat(value: Any) -> Mapping[str, Any]:
    stable_keys(value, [
        "schema", "seatId", "role", "vendorId", "deviceId", "pnpClass", "productName", "gpuUuid",
        "pciBusId", "pnpInstanceId", "transportClass", "transportAnchorPnpInstanceId",
        "initialCudaDeviceIndex", "authority",
    ], "HALO3_SEAT_INVALID", "HALO3 seat")
    rebuilt = halo3_seat_record(
        product_name=value["productName"],
        gpu_uuid=value["gpuUuid"],
        pci_bus_id=value["pciBusId"],
        pnp_instance_id=value["pnpInstanceId"],
        transport_class=value["transportClass"],
        transport_anchor_pnp_instance_id=value["transportAnchorPnpInstanceId"],
        initial_cuda_device_index=value["initialCudaDeviceIndex"],
    )
    require(dict(value) == rebuilt, "HALO3_SEAT_INVALID", "HALO3 seat identity differs")
    return value


def load_halo3_seat_config(path: str | Path) -> Mapping[str, Any]:
    value = json.loads(Path(path).expanduser().resolve().read_text(encoding="utf-8"))
    require(isinstance(value, Mapping) and "halo3Seat" in value, "HALO3_SEAT_CONFIG_INVALID", "campaign config lacks HALO3 seat")
    return validate_halo3_seat(value["halo3Seat"])


def nvidia_inventory() -> list[dict[str, Any]]:
    fields = ["index", "name", "uuid", "pci.bus_id"]
    query = run_command([
        "nvidia-smi",
        f"--query-gpu={','.join(fields)}",
        "--format=csv,noheader,nounits",
    ], timeout=30.0)
    require(query.available and query.returncode == 0, "HALO3_NVIDIA_INVENTORY_UNAVAILABLE", "NVIDIA inventory is unavailable")
    rows: list[dict[str, Any]] = []
    for line in query.stdout.splitlines():
        parts = [part.strip() for part in line.split(",")]
        if len(parts) != len(fields):
            continue
        row = dict(zip(fields, parts))
        try:
            row["index"] = int(row["index"])
        except ValueError:
            continue
        rows.append(row)
    return rows


def windows_display_topology() -> list[dict[str, Any]]:
    require(os.name == "nt", "HALO3_PNP_TOPOLOGY_UNAVAILABLE", "Windows PnP topology is required")
    script = r"""
$rows = @()
foreach ($device in @(Get-PnpDevice -Class Display -PresentOnly -ErrorAction Stop)) {
    function Read-Property([string]$key) {
        try { return (Get-PnpDeviceProperty -InstanceId $device.InstanceId -KeyName $key -ErrorAction Stop).Data }
        catch { return $null }
    }
    $parents = @()
    $cursor = $device.InstanceId
    for ($depth = 0; $depth -lt 16 -and $cursor; $depth++) {
        try { $parent = (Get-PnpDeviceProperty -InstanceId $cursor -KeyName 'DEVPKEY_Device_Parent' -ErrorAction Stop).Data }
        catch { $parent = $null }
        if ($parent) { $parents += [string]$parent }
        $cursor = [string]$parent
    }
    $rows += [pscustomobject]@{
        instanceId = [string]$device.InstanceId
        className = [string]$device.Class
        friendlyName = [string]$device.FriendlyName
        status = [string]$device.Status
        busNumber = Read-Property 'DEVPKEY_Device_BusNumber'
        address = Read-Property 'DEVPKEY_Device_Address'
        locationInfo = Read-Property 'DEVPKEY_Device_LocationInfo'
        locationPaths = @(Read-Property 'DEVPKEY_Device_LocationPaths')
        ancestorInstanceIds = @($parents)
    }
}
@($rows) | ConvertTo-Json -Compress -Depth 8
"""
    result = run_powershell(script, timeout=60.0)
    value = parse_json_output(result)
    require(isinstance(value, list), "HALO3_PNP_TOPOLOGY_UNAVAILABLE", "Windows PnP topology is unavailable")
    return [dict(row) for row in value if isinstance(row, Mapping)]


def _pci_coordinate(value: str) -> tuple[int, int, int]:
    match = PCI_BUS_RE.fullmatch(value)
    require(match is not None, "HALO3_SEAT_INVALID", "HALO3 PCI bus identity differs")
    return int(match.group(1), 16), int(match.group(2), 16), int(match.group(3), 16)


def resolve_halo3_seat_observation(
    seat: Mapping[str, Any],
    *,
    nvidia_rows: Sequence[Mapping[str, Any]],
    pnp_rows: Sequence[Mapping[str, Any]],
    torch_devices: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    seat = validate_halo3_seat(seat)
    nvidia_matches = [
        row for row in nvidia_rows
        if row.get("uuid") == seat["gpuUuid"]
        and str(row.get("pci.bus_id", "")).upper() == seat["pciBusId"]
        and row.get("name") == seat["productName"]
    ]
    require(len(nvidia_matches) == 1, "HALO3_NVIDIA_IDENTITY_NOT_UNIQUE", "exact HALO3 NVIDIA identity did not resolve once")
    current_index = safe_int(nvidia_matches[0].get("index"), 0, 31, "HALO3_NVIDIA_IDENTITY_INVALID", "observed NVIDIA index")

    pnp_matches = [row for row in pnp_rows if str(row.get("instanceId", "")).upper() == seat["pnpInstanceId"]]
    require(len(pnp_matches) == 1, "HALO3_PNP_IDENTITY_NOT_UNIQUE", "exact HALO3 PnP identity did not resolve once")
    pnp = pnp_matches[0]
    require(
        pnp.get("className") == seat["pnpClass"] and pnp.get("friendlyName") == seat["productName"] and pnp.get("status") == "OK",
        "HALO3_PNP_IDENTITY_INVALID",
        "HALO3 PnP class, product, or status differs",
    )
    bus, device, function = _pci_coordinate(seat["pciBusId"])
    observed_address = safe_int(pnp.get("address"), 0, 0xFFFFFFFF, "HALO3_PNP_IDENTITY_INVALID", "PnP address")
    require(
        pnp.get("busNumber") == bus
        and ((observed_address >> 16) & 0xFFFF) == device
        and (observed_address & 0xFFFF) == function,
        "HALO3_PNP_PCI_BINDING_MISMATCH",
        "HALO3 PnP and PCI coordinates differ",
    )
    ancestors = [str(row).upper() for row in pnp.get("ancestorInstanceIds", [])]
    anchor = seat["transportAnchorPnpInstanceId"]
    if anchor is not None:
        require(anchor in ancestors, "HALO3_TRANSPORT_TOPOLOGY_MISMATCH", "HALO3 transport anchor is absent from PnP ancestry")
    else:
        require(seat["transportClass"] == "internal_pcie", "HALO3_TRANSPORT_TOPOLOGY_MISMATCH", "HALO3 transport anchor is absent")

    if torch_devices is not None:
        torch_matches = [
            row for row in torch_devices
            if row.get("name") == seat["productName"]
            and row.get("uuid") == seat["gpuUuid"]
            and str(row.get("pciBusId", "")).upper() == seat["pciBusId"]
        ]
        require(len(torch_matches) == 1, "HALO3_TORCH_IDENTITY_NOT_UNIQUE", "Torch did not expose the exact HALO3 seat at its observed CUDA index")
        current_index = safe_int(torch_matches[0].get("index"), 0, 31, "HALO3_TORCH_IDENTITY_INVALID", "observed Torch CUDA device index")

    return {
        "schema": "stc-mary-halo3-seat-observation/1",
        "seatId": seat["seatId"],
        "role": "HALO3",
        "currentCudaDeviceIndex": current_index,
        "gpuUuid": seat["gpuUuid"],
        "pciBusId": seat["pciBusId"],
        "pnpInstanceId": seat["pnpInstanceId"],
        "transportClass": seat["transportClass"],
        "transportAnchorObserved": anchor is None or anchor in ancestors,
        "authority": "none",
    }


def resolve_halo3_seat(seat: Mapping[str, Any], *, torch_devices: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    return resolve_halo3_seat_observation(
        seat,
        nvidia_rows=nvidia_inventory(),
        pnp_rows=windows_display_topology(),
        torch_devices=torch_devices,
    )
