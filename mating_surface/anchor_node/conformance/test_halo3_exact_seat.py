from __future__ import annotations

import sys
import unittest
from pathlib import Path

ANCHOR = Path(__file__).resolve().parents[1]
if str(ANCHOR) not in sys.path:
    sys.path.insert(0, str(ANCHOR))

from stc_mary_local.common import ToolchainError
from stc_mary_local.halo3_seat import (
    halo3_seat_record,
    resolve_halo3_seat_observation,
)


class Halo3ExactSeatWitnesses(unittest.TestCase):
    def setUp(self) -> None:
        self.anchor = r"PCI\VEN_8086&DEV_15DA&SUBSYS_00011A58\TB"
        self.seat = halo3_seat_record(
            product_name="NVIDIA GeForce RTX 3090",
            gpu_uuid="GPU-0b31e56a-34eb-e8ef-e888-a6d6f044097b",
            pci_bus_id="00000000:25:00.0",
            pnp_instance_id=r"PCI\VEN_10DE&DEV_2204&SUBSYS_38801028\3090",
            transport_class="thunderbolt_egpu",
            transport_anchor_pnp_instance_id=self.anchor,
            initial_cuda_device_index=1,
        )
        self.nvidia = [
            {"index": 0, "name": "NVIDIA GeForce RTX 4060", "uuid": "GPU-e0b1541d-fc7d-38f5-d4c0-c15a3bd241a0", "pci.bus_id": "00000000:01:00.0"},
            {"index": 1, "name": "NVIDIA GeForce RTX 3090", "uuid": "GPU-0b31e56a-34eb-e8ef-e888-a6d6f044097b", "pci.bus_id": "00000000:25:00.0"},
        ]
        self.pnp = [
            {
                "instanceId": r"PCI\VEN_10DE&DEV_2882&SUBSYS_172619DA\4060",
                "className": "Display",
                "friendlyName": "NVIDIA GeForce RTX 4060",
                "status": "OK",
                "busNumber": 1,
                "address": 0,
                "ancestorInstanceIds": [],
            },
            {
                "instanceId": self.seat["pnpInstanceId"],
                "className": "Display",
                "friendlyName": "NVIDIA GeForce RTX 3090",
                "status": "OK",
                "busNumber": 37,
                "address": 0,
                "ancestorInstanceIds": [self.anchor],
            },
        ]

    def test_exact_thunderbolt_3090_wins_over_cuda_index_zero_4060(self) -> None:
        observation = resolve_halo3_seat_observation(
            self.seat,
            nvidia_rows=self.nvidia,
            pnp_rows=self.pnp,
            torch_devices=[
                {"index": 0, "name": "NVIDIA GeForce RTX 4060"},
                {"index": 1, "name": "NVIDIA GeForce RTX 3090"},
            ],
        )
        self.assertEqual(observation["seatId"], self.seat["seatId"])
        self.assertEqual(observation["gpuUuid"], self.seat["gpuUuid"])
        self.assertEqual(observation["currentCudaDeviceIndex"], 1)

    def test_exact_seat_survives_cuda_index_reordering(self) -> None:
        reordered = [
            {**self.nvidia[0], "index": 1},
            {**self.nvidia[1], "index": 0},
        ]
        observation = resolve_halo3_seat_observation(
            self.seat,
            nvidia_rows=reordered,
            pnp_rows=self.pnp,
            torch_devices=[
                {"index": 0, "name": "NVIDIA GeForce RTX 3090"},
                {"index": 1, "name": "NVIDIA GeForce RTX 4060"},
            ],
        )
        self.assertEqual(observation["seatId"], self.seat["seatId"])
        self.assertEqual(observation["currentCudaDeviceIndex"], 0)
        self.assertEqual(self.seat["initialCudaDeviceIndex"], 1)

    def test_internal_4060_cannot_satisfy_thunderbolt_halo3_role(self) -> None:
        wrong_seat = halo3_seat_record(
            product_name="NVIDIA GeForce RTX 4060",
            gpu_uuid="GPU-e0b1541d-fc7d-38f5-d4c0-c15a3bd241a0",
            pci_bus_id="00000000:01:00.0",
            pnp_instance_id=r"PCI\VEN_10DE&DEV_2882&SUBSYS_172619DA\4060",
            transport_class="thunderbolt_egpu",
            transport_anchor_pnp_instance_id=self.anchor,
            initial_cuda_device_index=0,
        )
        with self.assertRaises(ToolchainError) as caught:
            resolve_halo3_seat_observation(
                wrong_seat,
                nvidia_rows=self.nvidia,
                pnp_rows=self.pnp,
                torch_devices=[
                    {"index": 0, "name": "NVIDIA GeForce RTX 4060"},
                    {"index": 1, "name": "NVIDIA GeForce RTX 3090"},
                ],
            )
        self.assertEqual(caught.exception.code, "HALO3_TRANSPORT_TOPOLOGY_MISMATCH")


if __name__ == "__main__":
    unittest.main()
