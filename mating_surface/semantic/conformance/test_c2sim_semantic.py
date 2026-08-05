from __future__ import annotations

import unittest
from copy import deepcopy

from mating_surface.semantic import c2sim_semantic as semantic


class SemanticFixtureTests(unittest.TestCase):
    def receipts(self):
        rows = []
        for spec in semantic.SPECS:
            payload = semantic.serialize(semantic.BUILDERS[spec.message_class](spec))
            metadata = semantic.message_metadata(payload)
            rows.append(
                {
                    "messageReceiptId": f"receipt-{spec.message_class}",
                    **metadata,
                }
            )
        return rows

    def test_generates_deterministic_standards_native_message_sequence(self):
        first = [
            semantic.serialize(semantic.BUILDERS[spec.message_class](spec))
            for spec in semantic.SPECS
        ]
        second = [
            semantic.serialize(semantic.BUILDERS[spec.message_class](spec))
            for spec in semantic.SPECS
        ]
        self.assertEqual(first, second)
        self.assertEqual(
            [semantic.message_metadata(row)["messageClass"] for row in first],
            semantic.EXPECTED_CLASSES,
        )
        for payload in first:
            text = payload.decode("utf-8")
            self.assertIn(semantic.NS, text)
            self.assertNotIn("AXM", text)
            self.assertNotIn("Polybolos", text)
            self.assertNotIn("dandelion", text.lower())

    def test_conversation_closes_reply_and_task_lineage(self):
        rows = self.receipts()
        semantic.validate_conversation(rows)
        self.assertEqual(rows[2]["taskReference"], semantic.IDS.task)
        self.assertEqual(rows[3]["currentTask"], semantic.IDS.task)
        self.assertEqual(rows[3]["taskStatusCode"], "TASKCMPLT")

    def test_duplicate_message_identity_is_refused(self):
        rows = self.receipts()
        rows[1]["messageId"] = rows[0]["messageId"]
        with self.assertRaisesRegex(semantic.SemanticError, "not unique"):
            semantic.validate_conversation(rows)

    def test_future_or_unknown_reply_is_refused(self):
        rows = self.receipts()
        rows[2]["inReplyToMessageId"] = semantic.deterministic_uuid("unknown-message")
        with self.assertRaisesRegex(semantic.SemanticError, "unknown or future"):
            semantic.validate_conversation(rows)

    def test_wrong_task_status_does_not_close_the_conversation(self):
        rows = self.receipts()
        changed = deepcopy(rows)
        changed[3]["taskStatusCode"] = "TASKINPRG"
        with self.assertRaisesRegex(semantic.SemanticError, "TASKCMPLT"):
            semantic.validate_conversation(changed)


if __name__ == "__main__":
    unittest.main()
