"""Vendor SDK adapter stub.

This file is a template. It does not import any vendor libraries.

A real implementation would:
- Call a vendor SDK for execution (inference, graph execution, runtime API).
- Capture SDK versions, license mode, and any remote control-plane references.
- Emit those hints into provenance so the suite can reject vendor dependency.

This is the path for testing CUDA, TensorRT, Triton, and similar layers.
"""

from __future__ import annotations

from .base import RunResult


class VendorSDKAdapterStub:
    name = "vendor_sdk_stub"

    def run(self, ir_path: str, user_input: str, out_dir: str, **kwargs) -> RunResult:
        raise NotImplementedError("Implement vendor SDK execution and artifact capture here.")
