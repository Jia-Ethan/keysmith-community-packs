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
        self.assertIn(f"{cb.DEADLINE_DAYS} 天内开 PR", plan.comment)
        self.assertIn(f"within {cb.DEADLINE_DAYS} days", plan.comment)

    def test_not_while_a_pr_is_in_review(self):
        plan = comment("/claim", labels=("request", "in-review"))
        self.assertEqual(plan.assign, [])
        self.assertIn("waiting for review", plan.comment)

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


class CommentsDoNotTouchTheClock(unittest.TestCase):
    def test_a_plain_reply_is_ignored(self):
        # The deadline is about a PR, so talking does not move it.
        self.assertTrue(comment(None, labels=("request", "claimed", "claim-stale"), assignees=("alice",)).empty())


def pr(number=7, state="OPEN", draft=False, closed=None):
    return cb.LinkedPR(number, f"https://github.com/o/r/pull/{number}", state, draft, closed)


class Sweep(unittest.TestCase):
    def sweep(self, days=0, labels=("request", "claimed"), assignees=("alice",), prs=()):
        claimed_at = NOW - timedelta(days=days)
        return cb.decide_sweep(list(labels), list(assignees), claimed_at, list(prs), NOW)

    def test_fresh_claim_left_alone(self):
        self.assertTrue(self.sweep(cb.REMIND_DAYS - 1).empty())

    def test_one_reminder_before_the_deadline(self):
        plan = self.sweep(cb.REMIND_DAYS)
        self.assertEqual(plan.add_labels, ["claim-stale"])
        self.assertIn("@alice", plan.comment)
        self.assertIn((NOW + timedelta(days=cb.DEADLINE_DAYS - cb.REMIND_DAYS)).strftime("%Y-%m-%d"), plan.comment)
        self.assertIn("Closes #{number}", plan.comment)
        # Reminded already: nothing more until the deadline.
        self.assertTrue(self.sweep(cb.DEADLINE_DAYS - 1, labels=("request", "claimed", "claim-stale")).empty())

    def test_released_at_the_deadline(self):
        for labels in (("request", "claimed", "claim-stale"), ("request", "claimed")):
            plan = self.sweep(cb.DEADLINE_DAYS, labels=labels)
            self.assertEqual(plan.unassign, ["alice"])
            self.assertEqual(plan.add_labels, ["ready"])
            self.assertIn("claimed", plan.remove_labels)
            self.assertNotIn("in-review", plan.remove_labels)

    def test_a_draft_pr_stops_the_clock_and_asks_for_review(self):
        plan = self.sweep(60, labels=("request", "claimed", "claim-stale"), prs=[pr(draft=True)])
        self.assertEqual(plan.add_labels, ["in-review"])
        self.assertEqual(plan.remove_labels, ["claim-stale"])
        self.assertEqual(plan.unassign, [])
        self.assertIn("[#7](https://github.com/o/r/pull/7) (draft)", plan.comment)

    def test_in_review_marked_once(self):
        self.assertTrue(self.sweep(60, labels=("request", "claimed", "in-review"), prs=[pr()]).empty())

    def test_a_pr_without_a_claim_still_goes_to_review(self):
        plan = cb.decide_sweep(["request", "ready"], [], None, [pr()], NOW)
        self.assertEqual(plan.add_labels, ["in-review"])
        self.assertEqual(plan.remove_labels, ["ready"])
        # Closed unmerged with nobody holding it: back to the pool.
        plan = cb.decide_sweep(["request", "in-review"], [], None, [pr(state="CLOSED", closed=NOW)], NOW)
        self.assertEqual(plan.remove_labels, ["in-review"])
        self.assertEqual(plan.add_labels, ["ready"])
        self.assertIsNone(plan.comment)
        # ...but a request nobody confirmed does not become claimable that way.
        plan = cb.decide_sweep(["request", "needs-triage", "in-review"], [], None, [pr(state="CLOSED", closed=NOW)], NOW)
        self.assertEqual(plan.remove_labels, ["in-review"])
        self.assertEqual(plan.add_labels, [])

    def test_closed_unmerged_pr_restarts_the_clock(self):
        closed = NOW - timedelta(days=1)
        plan = self.sweep(30, labels=("request", "claimed", "in-review"), prs=[pr(state="CLOSED", closed=closed)])
        self.assertEqual(plan.remove_labels, ["in-review"])
        self.assertEqual(plan.unassign, [])
        self.assertIn("still yours", plan.comment)
        # Counted from the close, not the claim.
        later = closed + timedelta(days=cb.DEADLINE_DAYS)
        plan = cb.decide_sweep(["request", "claimed"], ["alice"], NOW - timedelta(days=30), [pr(state="CLOSED", closed=closed)], later)
        self.assertEqual(plan.add_labels, ["ready"])
        self.assertTrue(
            cb.decide_sweep(["request", "claimed"], ["alice"], NOW - timedelta(days=30), [pr(state="CLOSED", closed=closed)], later - timedelta(days=5)).empty()
        )

    def test_review_ending_restarts_the_clock(self):
        # The PR stopped linking here (its "Closes #n" was removed) a month after the claim.
        plan = self.sweep(40, labels=("request", "claimed", "in-review"))
        self.assertEqual(plan.remove_labels, ["in-review"])
        self.assertEqual(plan.unassign, [])
        self.assertIn("still yours", plan.comment)
        # Next sweeps count from when the label came off, not from the claim.
        ended = NOW
        f = dict(labels=["request", "claimed"], assignees=["alice"], claimed_at=NOW - timedelta(days=40), prs=[], review_ended_at=ended)
        self.assertTrue(cb.decide_sweep(now=ended + timedelta(days=cb.REMIND_DAYS - 1), **f).empty())
        self.assertEqual(cb.decide_sweep(now=ended + timedelta(days=cb.REMIND_DAYS), **f).add_labels, ["claim-stale"])
        self.assertEqual(cb.decide_sweep(now=ended + timedelta(days=cb.DEADLINE_DAYS), **f).add_labels, ["ready"])

    def test_merged_pr_never_releases(self):
        plan = self.sweep(60, labels=("request", "claimed", "in-review"), prs=[pr(state="MERGED", closed=NOW)])
        self.assertEqual(plan.remove_labels, ["in-review"])
        self.assertIsNone(plan.comment)
        self.assertEqual(plan.unassign, [])

    def test_unclaimed_request_left_alone(self):
        self.assertTrue(cb.decide_sweep(["request", "ready"], [], None, [], NOW).empty())
        self.assertTrue(cb.decide_sweep(["bug"], ["alice"], NOW - timedelta(days=60), [pr()], NOW).empty())


class Facts(unittest.TestCase):
    def test_reads_the_latest_claim_and_linked_prs(self):
        node = {
            "number": 12,
            "state": "OPEN",
            "labels": {"nodes": [{"name": "request"}, {"name": "claimed"}]},
            "assignees": {"nodes": [{"login": "alice"}]},
            "timelineItems": {
                "nodes": [
                    {"__typename": "LabeledEvent", "createdAt": "2026-10-01T00:00:00Z", "label": {"name": "claimed"}},
                    {"__typename": "UnlabeledEvent", "createdAt": "2026-10-05T00:00:00Z", "label": {"name": "ready"}},
                    {"__typename": "UnlabeledEvent", "createdAt": "2026-10-28T00:00:00Z", "label": {"name": "in-review"}},
                    {"__typename": "UnlabeledEvent", "createdAt": "2026-10-29T00:00:00Z", "label": {"name": "claimed"}},
                    {"__typename": "LabeledEvent", "createdAt": "2026-10-20T08:30:00Z", "label": {"name": "claimed"}},
                    {},
                ]
            },
            "closedByPullRequestsReferences": {
                "nodes": [
                    {"number": 3, "url": "https://x/3", "state": "CLOSED", "isDraft": False, "closedAt": "2026-10-25T00:00:00Z"},
                    {"number": 4, "url": "https://x/4", "state": "OPEN", "isDraft": True, "closedAt": None},
                ]
            },
        }
        f = cb.facts(node)
        self.assertEqual(f["labels"], ["request", "claimed"])
        self.assertEqual(f["assignees"], ["alice"])
        self.assertEqual(f["claimed_at"], datetime(2026, 10, 20, 8, 30, tzinfo=timezone.utc))
        self.assertEqual(f["review_ended_at"], datetime(2026, 10, 28, tzinfo=timezone.utc))
        self.assertEqual([(p.number, p.state, p.draft) for p in f["prs"]], [(3, "CLOSED", False), (4, "OPEN", True)])
        self.assertEqual(f["prs"][0].closed_at, datetime(2026, 10, 25, tzinfo=timezone.utc))

    def test_never_claimed(self):
        f = cb.facts({"labels": {"nodes": [{"name": "request"}]}, "assignees": {"nodes": []}, "timelineItems": {"nodes": []}})
        self.assertIsNone(f["claimed_at"])
        self.assertEqual(f["prs"], [])


if __name__ == "__main__":
    unittest.main()
