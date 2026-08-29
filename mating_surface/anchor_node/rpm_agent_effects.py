from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping

EFFECT_RECEIPT_SCHEMA = "estate/effect-receipt@1"
TELEMETRY_OBSERVATION_SCHEMA = "estate/telemetry-observation@1"
TELEMETRY_SNAPSHOT_SCHEMA = "estate/telemetry-snapshot@1"
TRANSITION_RECEIPT_SCHEMA = "estate/transition-receipt@1"

_REF_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{1,255}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class ContractError(ValueError):
    """Raised when a caller attempts to promote evidence or authority."""


class EffectClass(str, Enum):
    SIMULATED = "SIMULATED"
    OBSERVED = "OBSERVED"
    REQUESTED = "REQUESTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    REFUSED = "REFUSED"


class TelemetrySource(str, Enum):
    DEVICE_OBSERVED = "DEVICE_OBSERVED"
    PATIENT_REPORTED = "PATIENT_REPORTED"
    SIMULATED = "SIMULATED"
    MODEL_DERIVED = "MODEL_DERIVED"


class WorkflowMode(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    SIMULATION = "SIMULATION"


def canonical_json_bytes(value: Any) -> bytes:
    try:
        text = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise ContractError(f"value is not canonical JSON: {exc}") from exc
    return (text + "\n").encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _require_ref(value: str, label: str) -> str:
    if not isinstance(value, str) or _REF_RE.fullmatch(value) is None:
        raise ContractError(f"{label} must be a bounded public reference")
    return value


def _require_digest(value: str | None, label: str) -> str | None:
    if value is not None and (
        not isinstance(value, str) or _HEX64_RE.fullmatch(value) is None
    ):
        raise ContractError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _require_scalar_readings(readings: Mapping[str, int | float]) -> dict[str, int | float]:
    if not isinstance(readings, Mapping) or not readings:
        raise ContractError("readings must contain at least one scalar field")
    normalized: dict[str, int | float] = {}
    for key, value in readings.items():
        if not isinstance(key, str) or _REF_RE.fullmatch(key) is None:
            raise ContractError("reading field names must be bounded public identifiers")
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ContractError(f"reading {key} must be an integer or finite float")
        if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
            raise ContractError(f"reading {key} must be finite")
        normalized[key] = value
    return normalized


@dataclass(frozen=True)
class EffectReceipt:
    """A body-free statement about what an adapter actually proved happened."""

    operation: str
    subject_ref: str
    effect_class: EffectClass
    terminal: str
    evidence_ref: str | None = None
    acknowledgement_ref: str | None = None
    payload_sha256: str | None = None
    external_effect_claimed: bool = False
    schema: str = field(default=EFFECT_RECEIPT_SCHEMA, init=False)

    def __post_init__(self) -> None:
        _require_ref(self.operation, "operation")
        _require_ref(self.subject_ref, "subject_ref")
        _require_ref(self.terminal, "terminal")
        if self.evidence_ref is not None:
            _require_ref(self.evidence_ref, "evidence_ref")
        if self.acknowledgement_ref is not None:
            _require_ref(self.acknowledgement_ref, "acknowledgement_ref")
        _require_digest(self.payload_sha256, "payload_sha256")
        if type(self.external_effect_claimed) is not bool:
            raise ContractError("external_effect_claimed must be boolean")

        expected_terminal = self.effect_class.value
        if self.terminal != expected_terminal:
            raise ContractError(
                f"terminal {self.terminal!r} cannot represent {self.effect_class.value}"
            )

        if self.effect_class is EffectClass.SIMULATED:
            if self.external_effect_claimed:
                raise ContractError("simulated work cannot claim an external effect")
            if self.acknowledgement_ref is not None:
                raise ContractError("simulated work cannot carry an acknowledgement")
        elif self.effect_class is EffectClass.OBSERVED:
            if self.evidence_ref is None:
                raise ContractError("observed work requires an evidence_ref")
            if self.external_effect_claimed:
                raise ContractError(
                    "observation alone cannot claim completion of an external effect"
                )
            if self.acknowledgement_ref is not None:
                raise ContractError("an observation cannot carry an external acknowledgement")
        elif self.effect_class is EffectClass.REQUESTED:
            if self.evidence_ref is None:
                raise ContractError("requested effects require request evidence")
            if self.external_effect_claimed:
                raise ContractError("a request cannot claim an external effect")
            if self.acknowledgement_ref is not None:
                raise ContractError("a request cannot carry an acknowledgement")
        elif self.effect_class is EffectClass.ACKNOWLEDGED:
            if self.evidence_ref is None or self.acknowledgement_ref is None:
                raise ContractError(
                    "acknowledged effects require evidence_ref and acknowledgement_ref"
                )
            if not self.external_effect_claimed:
                raise ContractError(
                    "ACKNOWLEDGED is the only class that may claim an external effect"
                )
        elif self.effect_class is EffectClass.REFUSED:
            if self.external_effect_claimed:
                raise ContractError("refused work cannot claim an external effect")
            if self.acknowledgement_ref is not None:
                raise ContractError("refused work cannot carry an acknowledgement")

    def body(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "operation": self.operation,
            "subjectRef": self.subject_ref,
            "effectClass": self.effect_class.value,
            "terminal": self.terminal,
            "evidenceRef": self.evidence_ref,
            "acknowledgementRef": self.acknowledgement_ref,
            "payloadSha256": self.payload_sha256,
            "externalEffectClaimed": self.external_effect_claimed,
            "authority": "none",
        }

    @property
    def receipt_id(self) -> str:
        return f"rpmeffect1_{sha256_bytes(canonical_json_bytes(self.body()))}"

    def as_dict(self) -> dict[str, Any]:
        return {"receiptId": self.receipt_id, **self.body()}


@dataclass(frozen=True)
class TelemetryObservation:
    """One indivisible telemetry observation with one declared provenance class."""

    sequence: int
    measurement_type: str
    readings: Mapping[str, int | float]
    source: TelemetrySource
    evidence_ref: str | None = None
    payload_sha256: str | None = None
    schema: str = field(default=TELEMETRY_OBSERVATION_SCHEMA, init=False)

    def __post_init__(self) -> None:
        if type(self.sequence) is not int or self.sequence < 0:
            raise ContractError("sequence must be a non-negative integer")
        _require_ref(self.measurement_type, "measurement_type")
        normalized = _require_scalar_readings(self.readings)
        object.__setattr__(self, "readings", normalized)
        if self.evidence_ref is not None:
            _require_ref(self.evidence_ref, "evidence_ref")
        _require_digest(self.payload_sha256, "payload_sha256")

        if self.source is TelemetrySource.MODEL_DERIVED:
            raise ContractError(
                "model-derived prose cannot enter the telemetry ledger as evidence"
            )
        if self.source in {
            TelemetrySource.DEVICE_OBSERVED,
            TelemetrySource.PATIENT_REPORTED,
        } and self.evidence_ref is None:
            raise ContractError(f"{self.source.value} requires an evidence_ref")
        if self.source is TelemetrySource.SIMULATED and self.evidence_ref is not None:
            raise ContractError("simulated telemetry cannot masquerade as observed evidence")

    def body(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "sequence": self.sequence,
            "measurementType": self.measurement_type,
            "readings": dict(self.readings),
            "source": self.source.value,
            "evidenceRef": self.evidence_ref,
            "payloadSha256": self.payload_sha256,
            "clinicalInterpretation": False,
            "authority": "none",
        }

    @property
    def observation_id(self) -> str:
        return f"rpmobservation1_{sha256_bytes(canonical_json_bytes(self.body()))}"


class TelemetryLedger:
    """Retains each telemetry provenance lane without selecting clinical truth."""

    def __init__(self) -> None:
        self._observations: list[TelemetryObservation] = []
        self._sequences: set[int] = set()

    def record(self, observation: TelemetryObservation) -> str:
        if observation.sequence in self._sequences:
            raise ContractError("telemetry sequence values must be unique")
        self._sequences.add(observation.sequence)
        self._observations.append(observation)
        return observation.observation_id

    def observations(self, measurement_type: str | None = None) -> tuple[TelemetryObservation, ...]:
        values = self._observations
        if measurement_type is not None:
            values = [
                observation
                for observation in values
                if observation.measurement_type == measurement_type
            ]
        return tuple(sorted(values, key=lambda item: item.sequence))

    def lineage_snapshot(self, measurement_type: str) -> dict[str, Any] | None:
        _require_ref(measurement_type, "measurement_type")
        candidates = [
            observation
            for observation in self._observations
            if observation.measurement_type == measurement_type
        ]
        if not candidates:
            return None

        latest: dict[TelemetrySource, TelemetryObservation] = {}
        for observation in sorted(candidates, key=lambda item: item.sequence):
            latest[observation.source] = observation

        lanes: dict[str, dict[str, Any]] = {}
        for source in sorted(latest, key=lambda item: item.value):
            observation = latest[source]
            lanes[source.value] = {
                "observationId": observation.observation_id,
                "sequence": observation.sequence,
                "readings": dict(observation.readings),
                "evidenceRef": observation.evidence_ref,
                "payloadSha256": observation.payload_sha256,
                "simulated": source is TelemetrySource.SIMULATED,
            }

        body = {
            "schema": TELEMETRY_SNAPSHOT_SCHEMA,
            "measurementType": measurement_type,
            "latestBySource": lanes,
            "selectedObservationId": None,
            "selectionPolicyRef": None,
            "clinicalInterpretation": False,
            "authority": "none",
        }
        body["snapshotId"] = f"rpmsnapshot1_{sha256_bytes(canonical_json_bytes(body))}"
        return body


class TransitionGuard:
    """Owns device completion and consumes typed evidence outside inference."""

    def __init__(
        self,
        required_devices: set[str] | frozenset[str],
        mode: WorkflowMode = WorkflowMode.OPERATIONAL,
    ) -> None:
        if not isinstance(required_devices, (set, frozenset)) or not required_devices:
            raise ContractError("required_devices must be a non-empty set")
        if not isinstance(mode, WorkflowMode):
            raise ContractError("mode must be a WorkflowMode")
        normalized = frozenset(_require_ref(item, "required_device") for item in required_devices)
        self.required_devices = normalized
        self.mode = mode
        self.checked_devices: set[str] = set()
        self.paired_devices: set[str] = set()
        self._check_receipts: dict[str, str] = {}
        self._pair_receipts: dict[str, str] = {}

    def mark_checked(self, device_id: str, effect: EffectReceipt) -> dict[str, Any]:
        self._require_declared_device(device_id)
        self._validate_effect(
            effect,
            operation="check_device_status",
            device_id=device_id,
            operational_classes={EffectClass.OBSERVED, EffectClass.ACKNOWLEDGED},
        )
        self.checked_devices.add(device_id)
        self._check_receipts[device_id] = effect.receipt_id
        return self._transition_receipt("check_device_status", device_id, effect)

    def mark_paired(self, device_id: str, effect: EffectReceipt) -> dict[str, Any]:
        self._require_declared_device(device_id)
        if device_id not in self.checked_devices:
            raise ContractError("pairing requires a prior successful status check")
        self._validate_effect(
            effect,
            operation="pair_device",
            device_id=device_id,
            operational_classes={EffectClass.ACKNOWLEDGED},
        )
        self.paired_devices.add(device_id)
        self._pair_receipts[device_id] = effect.receipt_id
        return self._transition_receipt("pair_device", device_id, effect)

    def _require_declared_device(self, device_id: str) -> None:
        _require_ref(device_id, "device_id")
        if device_id not in self.required_devices:
            raise ContractError("undeclared devices cannot satisfy required-device completion")

    def _validate_effect(
        self,
        effect: EffectReceipt,
        *,
        operation: str,
        device_id: str,
        operational_classes: set[EffectClass],
    ) -> None:
        if not isinstance(effect, EffectReceipt):
            raise ContractError("device transitions require an EffectReceipt")
        if effect.operation != operation:
            raise ContractError(f"effect operation must be {operation}")
        if effect.subject_ref != f"device/{device_id}":
            raise ContractError("effect subject does not match the transitioned device")
        if self.mode is WorkflowMode.SIMULATION:
            if effect.effect_class is not EffectClass.SIMULATED:
                raise ContractError("simulation workflows accept only SIMULATED effects")
        elif effect.effect_class not in operational_classes:
            raise ContractError(
                f"{operation} cannot advance from {effect.effect_class.value} in operational mode"
            )

    @property
    def completion_reached(self) -> bool:
        return self.required_devices.issubset(self.paired_devices)

    @property
    def next_state(self) -> str:
        return "4_education" if self.completion_reached else "2_device_setup"

    def _transition_receipt(
        self,
        operation: str,
        device_id: str,
        effect: EffectReceipt,
    ) -> dict[str, Any]:
        body = {
            "schema": TRANSITION_RECEIPT_SCHEMA,
            "operation": operation,
            "deviceId": device_id,
            "effectReceiptId": effect.receipt_id,
            "effectClass": effect.effect_class.value,
            "workflowMode": self.mode.value,
            "requiredDevices": sorted(self.required_devices),
            "checkedDevices": sorted(self.checked_devices),
            "pairedDevices": sorted(self.paired_devices),
            "checkReceiptIds": dict(sorted(self._check_receipts.items())),
            "pairReceiptIds": dict(sorted(self._pair_receipts.items())),
            "completionReached": self.completion_reached,
            "nextState": self.next_state,
            "authority": "none",
        }
        body["transitionReceiptId"] = (
            f"rpmtransition1_{sha256_bytes(canonical_json_bytes(body))}"
        )
        return body
