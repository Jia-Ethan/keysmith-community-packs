"""Sidecar rules that are easy to get wrong."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import communitylib as cl  # noqa: E402

BASE = {"author": {"handle": "alice"}, "summary": {"en": "x"}}


def meta(**extra):
    return {**BASE, **extra}


class Request(unittest.TestCase):
    def test_absent_is_fine(self):
        cl.validate_meta(meta(), "alice.x", "t")

    def test_issue_and_requester(self):
        cl.validate_meta(meta(request={"issue": 12, "by": "Bob-Smith"}), "alice.x", "t")
        cl.validate_meta(meta(request={"issue": 12}), "alice.x", "t")

    def test_rejects_bad_shapes(self):
        for bad in ({}, {"by": "bob"}, {"issue": 0}, {"issue": "12"}, {"issue": True},
                    {"issue": 3, "by": "bad handle"}, {"issue": 3, "extra": 1}, [], "12"):
            with self.assertRaises(cl.CommunityError, msg=repr(bad)):
                cl.validate_meta(meta(request=bad), "alice.x", "t")


class Namespace(unittest.TestCase):
    def test_official_namespace_reserved(self):
        with self.assertRaises(cl.CommunityError):
            cl.validate_community_id("keysmith.anything")

    def test_handle_must_match(self):
        with self.assertRaises(cl.CommunityError):
            cl.validate_meta(meta(), "bob.x", "t")


if __name__ == "__main__":
    unittest.main()
