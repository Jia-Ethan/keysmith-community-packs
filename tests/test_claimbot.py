"""The request board's decisions, without GitHub.

    python3 -m unittest discover -s tests
"""

import sys
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".github" / "scripts"))
import claimbot as cb  # noqa: E402

NOW = datetime(2026, 11, 1, tzinfo=timezone.utc)


def comment(command, who="alice", assoc="NONE", labels=("request", "ready"), assignees=(), active=0, is_pr=False, is_open=True):
    return cb.decide_comment(command, who, assoc, list(labels), list(assignees), active, is_pr, is_open)


class ParseCommand(unittest.TestCase):
    def test_first_line_only(self):
        self.assertEqual(cb.parse_command("/claim"), "/claim")
        self.assertEqual(cb.parse_command("\n  /CLAIM  \nI'll do it"), "/claim")
        self.assertEqual(cb.parse_command("/unclaim"), "/unclaim")

    def test_not_a_command(self):
        for body in ("", "   ", "I will /claim this", "/claim this one", "/claimed", "> /claim", None):
            self.assertIsNone(cb.parse_command(body), body)


class Claim(unittest.TestCase):
    def test_claims_a_ready_request(self):
        plan = comment("/claim")
        self.assertEqual(plan.assign, ["alice"])
        self.assertEqual(plan.add_labels, ["claimed"])
        self.assertEqual(plan.remove_labels, ["ready"])
        self.assertIn("Closes #{number}", plan.comment)

    def test_not_ready_yet(self):
        plan = comment("/claim", labels=("request", "needs-triage"))
        self.assertEqual(plan.assign, [])
        self.assertIn("ready", plan.comment)

    def test_someone_else_holds_it(self):
        plan = comment("/claim", labels=("request", "claimed"), assignees=("bob",))
        self.assertEqual(plan.assign, [])
        self.assertIn("@bob", plan.comment)

    def test_already_yours(self):
        plan = comment("/claim", labels=("request", "claimed"), assignees=("alice",))
        self.assertEqual(plan.assign, [])
        self.assertIn("already yours", plan.comment)

    def test_claim_limit(self):
        plan = comment("/claim", active=cb.MAX_ACTIVE_CLAIMS)
        self.assertEqual(plan.assign, [])
        self.assertIn("limit", plan.comment)

    def test_ignored_off_the_board(self):
        self.assertTrue(comment("/claim", labels=("bug",)).empty())
        self.assertTrue(comment("/claim", is_pr=True).empty())
        self.assertTrue(comment("/claim", is_open=False).empty())
        self.assertTrue(comment(None).empty())


class Unclaim(unittest.TestCase):
    def test_holder_lets_go(self):
        plan = comment("/unclaim", labels=("request", "claimed", "claim-stale"), assignees=("alice",))
        self.assertEqual(plan.unassign, ["alice"])
        self.assertEqual(plan.add_labels, ["ready"])
        self.assertEqual(sorted(plan.remove_labels), ["claim-stale", "claimed"])

    def test_maintainer_releases(self):
        plan = comment("/unclaim", who="owner", assoc="OWNER", labels=("request", "claimed"), assignees=("bob",))
        self.assertEqual(plan.unassign, ["bob"])
        self.assertEqual(plan.add_labels, ["ready"])

    def test_stranger_cannot(self):
        plan = comment("/unclaim", who="mallory", labels=("request", "claimed"), assignees=("bob",))
        self.assertEqual(plan.unassign, [])
        self.assertIn("Only the claimer", plan.comment)

    def test_one_of_two_leaves_it_claimed(self):
        plan = comment("/unclaim", labels=("request", "claimed"), assignees=("alice", "bob"))
        self.assertEqual(plan.unassign, ["alice"])
        self.assertEqual(plan.add_labels, [])
        self.assertIsNone(plan.comment)


class StaleReply(unittest.TestCase):
    def test_any_word_from_the_holder_clears_the_reminder(self):
        plan = comment(None, labels=("request", "claimed", "claim-stale"), assignees=("alice",))
        self.assertEqual(plan.remove_labels, ["claim-stale"])
        self.assertIsNone(plan.comment)

    def test_someone_else_does_not(self):
        plan = comment(None, who="bob", labels=("request", "claimed", "claim-stale"), assignees=("alice",))
        self.assertTrue(plan.empty())


class Sweep(unittest.TestCase):
    def sweep(self, days, labels=("request", "claimed"), assignees=("alice",), pr=False):
        return cb.decide_sweep(list(labels), list(assignees), NOW - timedelta(days=days), NOW, pr)

    def test_fresh_claim_left_alone(self):
        self.assertTrue(self.sweep(cb.STALE_DAYS - 1).empty())

    def test_reminder_after_quiet_spell(self):
        plan = self.sweep(cb.STALE_DAYS)
        self.assertEqual(plan.add_labels, ["claim-stale"])
        self.assertIn("@alice", plan.comment)

    def test_open_pr_counts_as_progress(self):
        self.assertTrue(self.sweep(60, pr=True).empty())
        plan = self.sweep(60, labels=("request", "claimed", "claim-stale"), pr=True)
        self.assertEqual(plan.remove_labels, ["claim-stale"])

    def test_released_after_reminder_goes_unanswered(self):
        plan = self.sweep(cb.RELEASE_DAYS, labels=("request", "claimed", "claim-stale"))
        self.assertEqual(plan.unassign, ["alice"])
        self.assertEqual(plan.add_labels, ["ready"])

    def test_reminder_window_not_over(self):
        self.assertTrue(self.sweep(cb.RELEASE_DAYS - 1, labels=("request", "claimed", "claim-stale")).empty())


if __name__ == "__main__":
    unittest.main()
