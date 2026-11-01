"""Sidecar rules that are easy to get wrong."""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import communitylib as cl  # noqa: E402
import packlib  # noqa: E402

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


class HarnessPacks(unittest.TestCase):
    """Cross-pack rules for harness packs, on copies of the shipped demo pack."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def copy_demo(self, new_id, rename=None):
        """Copy jia.review-kit to <new_id>, optionally renaming one component's name."""
        source = ROOT / "packs" / "jia.review-kit"
        target = self.tmp / new_id
        shutil.copytree(source, target)
        manifest = json.loads((target / "pack.json").read_text(encoding="utf-8"))
        manifest["id"] = new_id
        for component in manifest["components"]:
            if rename and component["id"] in rename:
                component["name"] = rename[component["id"]]
                for entry in component["files"]:
                    path = target / entry["path"]
                    path.write_text(
                        path.read_text(encoding="utf-8").replace(f"name: {component['id']}", f"name: {component['name']}"),
                        encoding="utf-8",
                    )
                    entry["sha256"] = packlib.sha256_hex(path.read_bytes())
        (target / "pack.json").write_bytes(packlib.canonical_json(manifest))
        handle = new_id.split(".")[0]
        sidecar = json.loads((ROOT / "packs" / "jia.review-kit.meta.json").read_text(encoding="utf-8"))
        sidecar["author"] = {"handle": handle}
        (self.tmp / f"{new_id}.meta.json").write_text(json.dumps(sidecar), encoding="utf-8")
        return target

    def test_the_demo_pack_is_valid_and_indexed(self):
        loaded = cl.load_community_pack(ROOT / "packs" / "jia.review-kit")
        self.assertEqual(loaded["manifest"]["kind"], "harness")
        self.copy_demo("alice.kit")
        index = cl.build_community_index(self.tmp, "https://example.invalid", "2026-01-01T00:00:00Z")
        entry = index["packs"][0]
        self.assertEqual(entry["tier"], 1)
        self.assertEqual([c["type"] for c in entry["components"]], ["skill", "command", "agent"])
        self.assertNotIn("items", entry)
        self.assertNotIn("files", entry["components"][0])

    def test_two_packs_cannot_install_the_same_name(self):
        self.copy_demo("alice.kit")
        self.copy_demo("bob.kit")
        with self.assertRaises(cl.CommunityError) as caught:
            cl.validate_all(self.tmp)
        self.assertIn("already used by alice.kit", str(caught.exception))

    def test_a_command_and_a_skill_share_the_slash_namespace(self):
        self.copy_demo("alice.kit")
        self.copy_demo(
            "bob.kit",
            rename={"pre-pr-review": "bob-review", "review-staged": "pre-pr-review", "diff-reviewer": "bob-reviewer"},
        )
        with self.assertRaises(cl.CommunityError) as caught:
            cl.validate_all(self.tmp)
        self.assertIn("/pre-pr-review", str(caught.exception))

    def test_distinct_names_are_fine(self):
        self.copy_demo("alice.kit")
        self.copy_demo(
            "bob.kit",
            rename={"pre-pr-review": "bob-review", "review-staged": "bob-staged", "diff-reviewer": "bob-reviewer"},
        )
        self.assertEqual(len(cl.validate_all(self.tmp)), 2)

    def test_an_agent_may_share_a_name_with_a_skill(self):
        # Subagents and slash commands live in different namespaces.
        self.copy_demo("alice.kit")
        self.copy_demo(
            "bob.kit",
            rename={"pre-pr-review": "bob-review", "review-staged": "bob-staged", "diff-reviewer": "pre-pr-review"},
        )
        self.assertEqual(len(cl.validate_all(self.tmp)), 2)


if __name__ == "__main__":
    unittest.main()
