import unittest

from apps.orchestrator.src.siduri_orchestrator.contracts import ResponsePlan
from apps.orchestrator.src.siduri_orchestrator import server


class ResponseApprovalTests(unittest.TestCase):
    def setUp(self) -> None:
        server.PENDING_RESPONSES.clear()

    def test_grounded_response_is_held_until_approval(self) -> None:
        plan = ResponsePlan("master_stream", "observation_commentary", "uncertain", "不確かです。", "Uncertain.", "Tidak pasti.", requires_operator_approval=True)
        metadata = {"correlation_id": "corr_test", "citations": []}
        server.stage_response(plan, metadata)
        approved, returned_metadata = server.approve_response("corr_test")
        self.assertFalse(approved.requires_operator_approval)
        self.assertEqual(returned_metadata, metadata)

    def test_unknown_approval_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            server.approve_response("corr_missing")


if __name__ == "__main__":
    unittest.main()
