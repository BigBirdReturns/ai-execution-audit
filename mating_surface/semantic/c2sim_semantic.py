#!/usr/bin/env python3
"""Generate and validate a minimal, deterministic C2SIM rehearsal conversation.

The conversation is standards-native XML. AXM does not add fields to the C2SIM
message. The resulting receipts bind exact bytes to the admitted rehearsal
artifact and XSD 1.1 validator.
"""
from __future__ import annotations

import hashlib
import json
import sys
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid5
import xml.etree.ElementTree as ET

import xmlschema

NS = "http://www.sisostds.org/schemas/C2SIM/1.1"
ET.register_namespace("", NS)
FIXTURE_NAMESPACE = UUID("8f5f5c13-b210-47fc-afb5-2a8c7a0f4201")
EXPECTED_CLASSES = [
    "submit_initialization",
    "object_initialization",
    "order",
    "report",
]


class SemanticError(RuntimeError):
    pass


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(prefix: str, value: Any) -> str:
    return f"{prefix}_{hashlib.sha256(canonical_json(value).encode('utf-8')).hexdigest()}"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def deterministic_uuid(name: str) -> str:
    return str(uuid5(FIXTURE_NAMESPACE, name))


def q(name: str) -> str:
    return f"{{{NS}}}{name}"


def element(name: str, text: str | None = None) -> ET.Element:
    node = ET.Element(q(name))
    if text is not None:
        node.text = text
    return node


def child(parent: ET.Element, name: str, text: str | None = None) -> ET.Element:
    node = ET.SubElement(parent, q(name))
    if text is not None:
        node.text = text
    return node


def append_datetime(parent: ET.Element, name: str, value: str) -> ET.Element:
    wrapper = child(parent, name)
    child(wrapper, "IsoDateTime", value)
    return wrapper


@dataclass(frozen=True)
class FixtureIds:
    conversation: str = deterministic_uuid("conversation")
    sender_actor: str = deterministic_uuid("sender-actor")
    receiver_actor: str = deterministic_uuid("receiver-actor")
    task: str = deterministic_uuid("task")
    order: str = deterministic_uuid("order")
    report: str = deterministic_uuid("report")
    submit_message: str = deterministic_uuid("message-submit-initialization")
    init_message: str = deterministic_uuid("message-object-initialization")
    order_message: str = deterministic_uuid("message-order")
    report_message: str = deterministic_uuid("message-report")


@dataclass(frozen=True)
class MessageSpec:
    file_name: str
    message_class: str
    message_id: str
    communicative_act: str
    from_system: str
    to_system: str
    sent_at: str
    in_reply_to: str | None


IDS = FixtureIds()
SPECS = [
    MessageSpec(
        file_name="01-submit-initialization.xml",
        message_class="submit_initialization",
        message_id=IDS.submit_message,
        communicative_act="Request",
        from_system="semantic-command-node",
        to_system="semantic-simulation-node",
        sent_at="2026-08-01T00:00:01Z",
        in_reply_to=None,
    ),
    MessageSpec(
        file_name="02-object-initialization.xml",
        message_class="object_initialization",
        message_id=IDS.init_message,
        communicative_act="Inform",
        from_system="semantic-simulation-node",
        to_system="semantic-command-node",
        sent_at="2026-08-01T00:00:02Z",
        in_reply_to=IDS.submit_message,
    ),
    MessageSpec(
        file_name="03-order.xml",
        message_class="order",
        message_id=IDS.order_message,
        communicative_act="Request",
        from_system="semantic-command-node",
        to_system="semantic-simulation-node",
        sent_at="2026-08-01T00:00:03Z",
        in_reply_to=IDS.init_message,
    ),
    MessageSpec(
        file_name="04-report.xml",
        message_class="report",
        message_id=IDS.report_message,
        communicative_act="Inform",
        from_system="semantic-simulation-node",
        to_system="semantic-command-node",
        sent_at="2026-08-01T00:00:04Z",
        in_reply_to=IDS.order_message,
    ),
]


def append_header(root: ET.Element, spec: MessageSpec) -> None:
    header = child(root, "C2SIMHeader")
    child(header, "CommunicativeActTypeCode", spec.communicative_act)
    child(header, "ConversationID", IDS.conversation)
    child(header, "FromSendingSystem", spec.from_system)
    if spec.in_reply_to:
        child(header, "InReplyToMessageID", spec.in_reply_to)
    child(header, "MessageID", spec.message_id)
    child(header, "Protocol", "C2SIM")
    child(header, "ProtocolVersion", "1.0.1")
    child(header, "SecurityClassificationCode", "Unclassified")
    append_datetime(header, "SendingTime", spec.sent_at)
    child(header, "ToReceivingSystem", spec.to_system)


def build_submit_initialization(spec: MessageSpec) -> ET.Element:
    root = element("Message")
    append_header(root, spec)
    body = child(root, "MessageBody")
    command = child(body, "SystemCommandBody")
    child(command, "SystemCommandTypeCode", "SubmitInitialization")
    return root


def build_object_initialization(spec: MessageSpec) -> ET.Element:
    root = element("Message")
    append_header(root, spec)
    body = child(root, "MessageBody")
    initialization = child(body, "ObjectInitializationBody")
    settings = child(initialization, "ScenarioSetting")
    append_datetime(settings, "DateTime", "2026-08-01T00:00:00Z")
    child(settings, "Version", "semantic-rehearsal-1")
    system_entities = child(initialization, "SystemEntityList")
    child(system_entities, "ActorReference", IDS.receiver_actor)
    child(system_entities, "SystemName", "semantic-simulation-node")
    return root


def build_order(spec: MessageSpec) -> ET.Element:
    root = element("Message")
    append_header(root, spec)
    body = child(root, "MessageBody")
    domain = child(body, "DomainMessageBody")
    order = child(domain, "OrderBody")
    child(order, "FromSender", IDS.sender_actor)
    child(order, "ToReceiver", IDS.receiver_actor)
    append_datetime(order, "IssuedTime", spec.sent_at)
    child(order, "OrderID", IDS.order)
    child(order, "TaskReference", IDS.task)
    return root


def build_report(spec: MessageSpec) -> ET.Element:
    root = element("Message")
    append_header(root, spec)
    body = child(root, "MessageBody")
    domain = child(body, "DomainMessageBody")
    report = child(domain, "ReportBody")
    child(report, "FromSender", IDS.receiver_actor)
    child(report, "ToReceiver", IDS.sender_actor)
    content = child(report, "ReportContent")
    status = child(content, "TaskStatus")
    observation = child(status, "TimeOfObservation")
    append_datetime(observation, "DateTime", spec.sent_at)
    child(status, "CurrentTask", IDS.task)
    child(status, "TaskStatusCode", "TASKCMPLT")
    child(report, "ReportID", IDS.report)
    child(report, "ReportingEntity", IDS.receiver_actor)
    return root


BUILDERS = {
    "submit_initialization": build_submit_initialization,
    "object_initialization": build_object_initialization,
    "order": build_order,
    "report": build_report,
}


def serialize(root: ET.Element) -> bytes:
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True, short_empty_elements=True)


def local_text(root: ET.Element, path: str) -> str | None:
    node = root.find(path, {"c": NS})
    return node.text if node is not None else None


def message_metadata(data: bytes) -> dict[str, Any]:
    root = ET.fromstring(data)
    if root.tag != q("Message"):
        raise SemanticError("root is not C2SIM Message")
    metadata: dict[str, Any] = {
        "messageId": local_text(root, "c:C2SIMHeader/c:MessageID"),
        "conversationId": local_text(root, "c:C2SIMHeader/c:ConversationID"),
        "communicativeAct": local_text(root, "c:C2SIMHeader/c:CommunicativeActTypeCode"),
        "fromSystem": local_text(root, "c:C2SIMHeader/c:FromSendingSystem"),
        "toSystem": local_text(root, "c:C2SIMHeader/c:ToReceivingSystem"),
        "inReplyToMessageId": local_text(root, "c:C2SIMHeader/c:InReplyToMessageID"),
        "sentAt": local_text(root, "c:C2SIMHeader/c:SendingTime/c:IsoDateTime"),
        "protocol": local_text(root, "c:C2SIMHeader/c:Protocol"),
        "protocolVersion": local_text(root, "c:C2SIMHeader/c:ProtocolVersion"),
        "securityClassification": local_text(root, "c:C2SIMHeader/c:SecurityClassificationCode"),
    }
    body = root.find("c:MessageBody", {"c": NS})
    if body is None or len(body) != 1:
        raise SemanticError("MessageBody must contain exactly one selected body")
    selected = body[0]
    if selected.tag == q("SystemCommandBody"):
        metadata["messageClass"] = "submit_initialization"
        metadata["systemCommandType"] = local_text(selected, "c:SystemCommandTypeCode")
    elif selected.tag == q("ObjectInitializationBody"):
        metadata["messageClass"] = "object_initialization"
        metadata["scenarioVersion"] = local_text(selected, "c:ScenarioSetting/c:Version")
        metadata["systemName"] = local_text(selected, "c:SystemEntityList/c:SystemName")
    elif selected.tag == q("DomainMessageBody") and len(selected) == 1:
        domain = selected[0]
        if domain.tag == q("OrderBody"):
            metadata["messageClass"] = "order"
            metadata["fromSender"] = local_text(domain, "c:FromSender")
            metadata["toReceiver"] = local_text(domain, "c:ToReceiver")
            metadata["orderId"] = local_text(domain, "c:OrderID")
            metadata["taskReference"] = local_text(domain, "c:TaskReference")
        elif domain.tag == q("ReportBody"):
            metadata["messageClass"] = "report"
            metadata["fromSender"] = local_text(domain, "c:FromSender")
            metadata["toReceiver"] = local_text(domain, "c:ToReceiver")
            metadata["reportId"] = local_text(domain, "c:ReportID")
            metadata["reportingEntity"] = local_text(domain, "c:ReportingEntity")
            metadata["currentTask"] = local_text(domain, "c:ReportContent/c:TaskStatus/c:CurrentTask")
            metadata["taskStatusCode"] = local_text(domain, "c:ReportContent/c:TaskStatus/c:TaskStatusCode")
        else:
            raise SemanticError(f"unsupported DomainMessageBody child {domain.tag}")
    else:
        raise SemanticError(f"unsupported MessageBody child {selected.tag}")
    return metadata


def verify_artifact_context(xsd_path: Path, transaction: dict[str, Any], catalog: dict[str, Any]) -> None:
    if transaction.get("schema") != "standards-mating-surface-artifact-transaction/1" or transaction.get("status") != "pass":
        raise SemanticError("artifact transaction is invalid")
    admission = transaction.get("admission")
    use = transaction.get("use")
    if not isinstance(admission, dict) or not isinstance(use, dict):
        raise SemanticError("artifact transaction is incomplete")
    observed = sha256_bytes(xsd_path.read_bytes())
    if admission.get("artifactSha256") != observed:
        raise SemanticError("XSD bytes differ from admitted artifact")
    if admission.get("standardId") != "siso-std-019-2020-c2sim":
        raise SemanticError("semantic compiler received another standard")
    if use.get("mode") not in {"test", "rehearsal"}:
        raise SemanticError("public reference artifact is not admitted for semantic rehearsal")
    if catalog.get("schema") != "standards-mating-surface-xsd11-catalog/1":
        raise SemanticError("XSD catalog is invalid")
    if (
        catalog.get("artifactAdmissionId") != admission.get("admissionId")
        or catalog.get("artifactUseId") != use.get("useId")
        or catalog.get("artifactSha256") != observed
    ):
        raise SemanticError("catalog does not belong to admitted artifact")


def validate_xml(schema: xmlschema.XMLSchema11, xml_path: Path) -> None:
    errors = list(schema.iter_errors(str(xml_path)))
    if errors:
        details = " | ".join(str(error) for error in errors[:5])
        raise SemanticError(f"{xml_path.name} failed XSD 1.1 validation: {details}")


def validate_conversation(receipts: list[dict[str, Any]]) -> None:
    if [row["messageClass"] for row in receipts] != EXPECTED_CLASSES:
        raise SemanticError("semantic conversation class order is invalid")
    conversation_ids = {row["conversationId"] for row in receipts}
    if conversation_ids != {IDS.conversation}:
        raise SemanticError("conversation identity is inconsistent")
    message_ids = [row["messageId"] for row in receipts]
    if len(set(message_ids)) != len(message_ids):
        raise SemanticError("message identities are not unique")
    seen: set[str] = set()
    for row in receipts:
        reply = row.get("inReplyToMessageId")
        if reply is not None and reply not in seen:
            raise SemanticError(f"message {row['messageId']} replies to an unknown or future message")
        seen.add(row["messageId"])
    if receipts[2].get("taskReference") != IDS.task:
        raise SemanticError("order does not bind the retained task")
    if receipts[3].get("currentTask") != IDS.task:
        raise SemanticError("report does not close the retained task")
    if receipts[3].get("taskStatusCode") != "TASKCMPLT":
        raise SemanticError("report does not close with TASKCMPLT")


def negative_checks(schema: xmlschema.XMLSchema11, valid_messages: list[bytes], receipts: list[dict[str, Any]]) -> dict[str, bool]:
    checks: dict[str, bool] = {}

    wrong_namespace = valid_messages[0].replace(NS.encode("utf-8"), b"urn:invented:c2sim", 1)
    checks["wrong_namespace_refused"] = not schema.is_valid(wrong_namespace)

    missing_message_id_root = ET.fromstring(valid_messages[0])
    header = missing_message_id_root.find(q("C2SIMHeader"))
    assert header is not None
    message_id = header.find(q("MessageID"))
    assert message_id is not None
    header.remove(message_id)
    checks["missing_message_id_refused"] = not schema.is_valid(serialize(missing_message_id_root))

    invalid_enum_root = ET.fromstring(valid_messages[0])
    classification = invalid_enum_root.find(f".//{q('SecurityClassificationCode')}")
    assert classification is not None
    classification.text = "InventedClassification"
    checks["invalid_enumeration_refused"] = not schema.is_valid(serialize(invalid_enum_root))

    duplicate = [dict(row) for row in receipts]
    duplicate[1]["messageId"] = duplicate[0]["messageId"]
    try:
        validate_conversation(duplicate)
        checks["duplicate_message_id_refused"] = False
    except SemanticError:
        checks["duplicate_message_id_refused"] = True

    broken_reply = [dict(row) for row in receipts]
    broken_reply[2]["inReplyToMessageId"] = deterministic_uuid("unknown-message")
    try:
        validate_conversation(broken_reply)
        checks["broken_reply_chain_refused"] = False
    except SemanticError:
        checks["broken_reply_chain_refused"] = True

    if not all(checks.values()):
        failed = sorted(key for key, value in checks.items() if not value)
        raise SemanticError(f"negative semantic checks failed: {failed}")
    return checks


def compile_conversation(
    xsd_path: Path,
    transaction_path: Path,
    catalog_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    verify_artifact_context(xsd_path, transaction, catalog)
    schema = xmlschema.XMLSchema11(
        str(xsd_path),
        validation="strict",
        allow="local",
        defuse="always",
        use_fallback=False,
    )
    if not schema.built:
        raise SemanticError("XMLSchema11 did not build the admitted schema")

    shutil.rmtree(output_dir, ignore_errors=True)
    output_dir.mkdir(parents=True, exist_ok=True)
    messages_dir = output_dir / "messages"
    messages_dir.mkdir(parents=True, exist_ok=True)
    receipts: list[dict[str, Any]] = []
    payloads: list[bytes] = []
    admission = transaction["admission"]
    use = transaction["use"]

    for spec in SPECS:
        payload = serialize(BUILDERS[spec.message_class](spec))
        path = messages_dir / spec.file_name
        path.write_bytes(payload)
        validate_xml(schema, path)
        metadata = message_metadata(payload)
        required_metadata = [
            "messageId", "conversationId", "communicativeAct", "fromSystem",
            "toSystem", "sentAt", "protocol", "protocolVersion",
            "securityClassification", "messageClass",
        ]
        missing_metadata = [key for key in required_metadata if metadata.get(key) in {None, ""}]
        if missing_metadata:
            raise SemanticError(f"generated metadata is incomplete for {spec.file_name}: {missing_metadata}")
        if metadata.get("messageClass") != spec.message_class or metadata.get("messageId") != spec.message_id:
            raise SemanticError(f"generated metadata differs for {spec.file_name}")
        body = {
            "artifactAdmissionId": admission["admissionId"],
            "artifactUseId": use["useId"],
            "artifactSha256": admission["artifactSha256"],
            "catalogId": catalog["catalogId"],
            "standardId": admission["standardId"],
            "standardRevision": admission["standardRevision"],
            "fileName": spec.file_name,
            "payloadSha256": sha256_bytes(payload),
            "payloadBytes": len(payload),
            **metadata,
            "validation": {
                "status": "pass",
                "validator": "xmlschema.XMLSchema11",
                "validatorVersion": xmlschema.__version__,
                "mode": "strict_local_only",
                "errorCount": 0,
            },
        }
        receipt = {
            "schema": "c2sim-semantic-message-receipt/1",
            "messageReceiptId": digest("c2simsemanticmessage1", body),
            **body,
            "claimBoundary": (
                "This receipt proves that one deterministic rehearsal message instance validates against the exact "
                "admitted public C2SIM reference artifact. It does not make the public snapshot operational, grant "
                "authority, or assert suitability for a fielded C2SIM coalition profile."
            ),
        }
        receipts.append(receipt)
        payloads.append(payload)
        (messages_dir / f"{spec.file_name}.receipt.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )

    validate_conversation(receipts)
    negatives = negative_checks(schema, payloads, receipts)
    conversation_body = {
        "artifactAdmissionId": admission["admissionId"],
        "artifactUseId": use["useId"],
        "catalogId": catalog["catalogId"],
        "conversationId": IDS.conversation,
        "messageReceiptIds": [row["messageReceiptId"] for row in receipts],
        "messageIds": [row["messageId"] for row in receipts],
        "messageClasses": [row["messageClass"] for row in receipts],
        "replyChain": [row.get("inReplyToMessageId") for row in receipts],
        "taskId": IDS.task,
        "orderId": IDS.order,
        "reportId": IDS.report,
        "negativeChecks": negatives,
    }
    conversation = {
        "schema": "c2sim-semantic-conversation/1",
        "semanticConversationId": digest("c2simsemanticconversation1", conversation_body),
        **conversation_body,
        "messages": receipts,
        "claimBoundary": (
            "This conversation is a deterministic, unclassified rehearsal fixture composed of schema-valid C2SIM "
            "messages. It is not an operational order, report, system command, or coalition profile."
        ),
    }
    (output_dir / "conversation.json").write_text(
        json.dumps(conversation, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary = {
        "status": "pass",
        "semanticConversationId": conversation["semanticConversationId"],
        "conversationId": IDS.conversation,
        "messages": len(receipts),
        "messageClasses": EXPECTED_CLASSES,
        "negativeChecks": negatives,
        "validatorVersion": xmlschema.__version__,
        "output": str(output_dir),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return conversation


def main(argv: list[str]) -> int:
    if len(argv) != 4:
        print(
            "usage: c2sim_semantic.py <schema.xsd> <artifact-transaction.json> <xsd11-catalog.json> <output-dir>",
            file=sys.stderr,
        )
        return 2
    compile_conversation(Path(argv[0]), Path(argv[1]), Path(argv[2]), Path(argv[3]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
