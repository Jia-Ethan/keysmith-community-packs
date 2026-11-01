#!/usr/bin/env python3
"""The request board bot: `/claim` and `/unclaim` on request issues, plus the stale sweep.

    python3 .github/scripts/claimbot.py comment   # on issue_comment (reads GITHUB_EVENT_PATH)
    python3 .github/scripts/claimbot.py sweep     # on schedule

A request issue moves needs-triage -> ready (a maintainer sets it) -> claimed (someone
comments /claim) -> closed by the PR that says `Closes #n`. A claim with no activity for
STALE_DAYS gets a reminder; if nothing happens for RELEASE_DAYS after that, it goes back
to `ready` for someone else.

Comment text is untrusted. It is read from the event file and only ever matched against
a fixed command set; it never reaches a shell or a URL. The decision logic is the set of
pure `decide_*` functions below so it can be tested without GitHub.

Standard library only.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

REQUEST = "request"
READY = "ready"
CLAIMED = "claimed"
STALE = "claim-stale"
MAINTAINERS = {"OWNER", "MEMBER", "COLLABORATOR"}
MAX_ACTIVE_CLAIMS = 3
STALE_DAYS = 14
RELEASE_DAYS = 7
GUIDE = "https://github.com/Jia-Ethan/keysmith-community-packs/blob/main/docs/requests.md"


@dataclass
class Plan:
    """What to do to one issue. Empty means do nothing."""

    add_labels: List[str] = field(default_factory=list)
    remove_labels: List[str] = field(default_factory=list)
    assign: List[str] = field(default_factory=list)
    unassign: List[str] = field(default_factory=list)
    comment: Optional[str] = None

    def empty(self) -> bool:
        return not (self.add_labels or self.remove_labels or self.assign or self.unassign or self.comment)


def parse_command(body: str) -> Optional[str]:
    """The command on the comment's first non-empty line, if it is exactly one we know."""
    for line in (body or "").splitlines():
        word = line.strip().lower()
        if not word:
            continue
        return word if word in ("/claim", "/unclaim") else None
    return None


def decide_comment(
    command: Optional[str],
    commenter: str,
    association: str,
    labels: List[str],
    assignees: List[str],
    active_claims: int,
    is_pr: bool,
    is_open: bool,
) -> Plan:
    """React to one comment on an issue."""
    plan = Plan()
    if is_pr or REQUEST not in labels:
        return plan
    # Any word from the person holding a stale claim counts as "still on it".
    if STALE in labels and commenter in assignees and command != "/unclaim":
        plan.remove_labels.append(STALE)
    if command is None or not is_open:
        return plan

    if command == "/claim":
        if commenter in assignees:
            plan.comment = f"@{commenter} 这个需求已经在你名下了。/ It's already yours."
            return plan
        if assignees:
            holder = ", ".join(f"@{a}" for a in assignees)
            plan.comment = (
                f"@{commenter} 这个需求 {holder} 正在做。想一起做可以在这里和 TA 商量；"
                f"如果 {STALE_DAYS} 天没进展，它会自动放回需求池。\n\n"
                f"{holder} is already on this. Coordinate here if you'd like to pair; "
                f"after {STALE_DAYS} days without activity it goes back to the pool."
            )
            return plan
        if READY not in labels:
            plan.comment = (
                f"@{commenter} 谢谢！这个需求还没确认好（还没有 `ready` 标签），维护者确认后就能领。\n\n"
                "Thanks! This request isn't confirmed yet (no `ready` label). "
                "You can claim it once a maintainer marks it ready."
            )
            return plan
        if active_claims >= MAX_ACTIVE_CLAIMS:
            plan.comment = (
                f"@{commenter} 你手上已经有 {active_claims} 个进行中的需求了（上限 {MAX_ACTIVE_CLAIMS}）。"
                "先完成或用 `/unclaim` 放掉一个再来领吧。\n\n"
                f"You already hold {active_claims} open claims (limit {MAX_ACTIVE_CLAIMS}). "
                "Finish one or `/unclaim` it first."
            )
            return plan
        plan.assign.append(commenter)
        plan.add_labels.append(CLAIMED)
        plan.remove_labels.append(READY)
        plan.comment = (
            f"🚩 @{commenter} 领走了这个需求，谢谢！\n\n"
            f"- 做好后开 PR，描述里写 `Closes #{{number}}`，合并时这个需求会自动关闭。\n"
            f"- 在包的边车里加上 `\"request\": {{\"issue\": {{number}}, \"by\": \"<提需求的人>\"}}`，"
            "画廊会同时署上点子和实现两个人。\n"
            f"- {STALE_DAYS} 天没动静会提醒一次；不想做了随时评论 `/unclaim`。\n\n"
            f"🚩 @{commenter} claimed this. Thank you!\n\n"
            "- Open a PR with `Closes #{number}` in its description; merging closes this request.\n"
            "- Add `\"request\": {\"issue\": {number}, \"by\": \"<requester>\"}` to your pack's sidecar "
            "so the gallery credits both the idea and the build.\n"
            f"- After {STALE_DAYS} quiet days you'll get a reminder; comment `/unclaim` any time to hand it back.\n\n"
            f"[流程说明 / How it works]({GUIDE})"
        )
        return plan

    # /unclaim: the holder lets go, or a maintainer releases it.
    if not assignees:
        return plan
    if commenter in assignees:
        released = [commenter]
    elif association in MAINTAINERS:
        released = list(assignees)
    else:
        plan.comment = f"@{commenter} 只有领取人或维护者能放掉这个需求。/ Only the claimer or a maintainer can release this."
        return plan
    plan.unassign.extend(released)
    if set(released) == set(assignees):
        plan.remove_labels.extend(l for l in (CLAIMED, STALE) if l in labels and l not in plan.remove_labels)
        plan.add_labels.append(READY)
        plan.comment = "这个需求放回需求池了，任何人都可以 `/claim`。/ Back in the pool — anyone can `/claim` it."
    return plan


def decide_sweep(labels: List[str], assignees: List[str], updated_at: datetime, now: datetime, has_open_pr: bool) -> Plan:
    """The daily look at one claimed request."""
    plan = Plan()
    if REQUEST not in labels or CLAIMED not in labels or not assignees:
        return plan
    if has_open_pr:
        # A PR is the progress. Clear any reminder and leave it alone.
        if STALE in labels:
            plan.remove_labels.append(STALE)
        return plan
    quiet = now - updated_at
    who = " ".join(f"@{a}" for a in assignees)
    if STALE not in labels:
        if quiet >= timedelta(days=STALE_DAYS):
            plan.add_labels.append(STALE)
            plan.comment = (
                f"{who} 这个需求 {STALE_DAYS} 天没动静了，还在做吗？回复一句就行；"
                f"{RELEASE_DAYS} 天内没回应会放回需求池。不做了也没关系，评论 `/unclaim` 即可。\n\n"
                f"{who} no activity here for {STALE_DAYS} days — still on it? Any reply keeps it yours; "
                f"otherwise it goes back to the pool in {RELEASE_DAYS} days. `/unclaim` is fine too."
            )
        return plan
    if quiet >= timedelta(days=RELEASE_DAYS):
        plan.unassign.extend(assignees)
        plan.remove_labels.extend([CLAIMED, STALE])
        plan.add_labels.append(READY)
        plan.comment = (
            f"{who} 一直没回应，这个需求先放回需求池了，谢谢你！想继续做随时再 `/claim`。\n\n"
            f"No reply, so this is back in the pool. Thanks, {who} — `/claim` again any time."
        )
    return plan


# --- GitHub API (thin) -------------------------------------------------------


class GitHub:
    def __init__(self, token: str, repo: str) -> None:
        self.token = token
        self.repo = repo

    def call(self, method: str, path: str, body: Optional[dict] = None) -> object:
        url = path if path.startswith("https://") else f"https://api.github.com{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Authorization", f"Bearer {self.token}")
        req.add_header("Accept", "application/vnd.github+json")
        req.add_header("X-GitHub-Api-Version", "2022-11-28")
        if data is not None:
            req.add_header("Content-Type", "application/json")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                raw = resp.read()
        except urllib.error.HTTPError as error:
            # Removing a label that is already gone is not a failure.
            if error.code == 404 and method == "DELETE":
                return None
            raise
        return json.loads(raw) if raw else None

    def apply(self, number: int, plan: Plan) -> None:
        base = f"/repos/{self.repo}/issues/{number}"
        for label in plan.remove_labels:
            self.call("DELETE", f"{base}/labels/{urllib.parse.quote(label)}")
        if plan.add_labels:
            self.call("POST", f"{base}/labels", {"labels": plan.add_labels})
        if plan.unassign:
            self.call("DELETE", f"{base}/assignees", {"assignees": plan.unassign})
        if plan.assign:
            self.call("POST", f"{base}/assignees", {"assignees": plan.assign})
        if plan.comment:
            self.call("POST", f"{base}/comments", {"body": plan.comment.replace("{number}", str(number))})

    def active_claims(self, login: str) -> int:
        q = f"repo:{self.repo} is:issue is:open label:{CLAIMED} assignee:{login}"
        result = self.call("GET", "/search/issues?" + urllib.parse.urlencode({"q": q, "per_page": 1}))
        return int(result["total_count"])  # type: ignore[index]

    def claimed_issues(self) -> List[dict]:
        q = urllib.parse.urlencode({"labels": f"{REQUEST},{CLAIMED}", "state": "open", "per_page": 100})
        return self.call("GET", f"/repos/{self.repo}/issues?{q}")  # type: ignore[return-value]

    def has_open_pr(self, number: int) -> bool:
        events = self.call("GET", f"/repos/{self.repo}/issues/{number}/timeline?per_page=100")
        for event in events or []:  # type: ignore[union-attr]
            source = (event.get("source") or {}).get("issue") or {}
            if event.get("event") == "cross-referenced" and source.get("pull_request") and source.get("state") == "open":
                return True
        return False


def _names(items: List[dict], key: str) -> List[str]:
    return [item[key] for item in items or []]


def _time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def run_comment(gh: GitHub, event: Dict) -> None:
    issue, comment = event["issue"], event["comment"]
    commenter = comment["user"]["login"]
    if comment["user"].get("type") == "Bot":
        return
    command = parse_command(comment.get("body", ""))
    labels = _names(issue.get("labels", []), "name")
    assignees = _names(issue.get("assignees", []), "login")
    active = gh.active_claims(commenter) if command == "/claim" and READY in labels and not assignees else 0
    plan = decide_comment(
        command,
        commenter,
        comment.get("author_association", "NONE"),
        labels,
        assignees,
        active,
        is_pr="pull_request" in issue,
        is_open=issue.get("state") == "open",
    )
    if not plan.empty():
        gh.apply(issue["number"], plan)
        print(f"#{issue['number']}: {plan}")


def run_sweep(gh: GitHub, now: datetime) -> None:
    for issue in gh.claimed_issues():
        if "pull_request" in issue:
            continue
        plan = decide_sweep(
            _names(issue.get("labels", []), "name"),
            _names(issue.get("assignees", []), "login"),
            _time(issue["updated_at"]),
            now,
            gh.has_open_pr(issue["number"]),
        )
        if not plan.empty():
            gh.apply(issue["number"], plan)
            print(f"#{issue['number']}: {plan}")


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("comment", "sweep"):
        print(__doc__, file=sys.stderr)
        return 2
    gh = GitHub(os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPOSITORY"])
    if sys.argv[1] == "comment":
        with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as handle:
            run_comment(gh, json.load(handle))
    else:
        run_sweep(gh, datetime.now(timezone.utc))
    return 0


if __name__ == "__main__":
    sys.exit(main())
