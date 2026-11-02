#!/usr/bin/env python3
"""The request board bot: `/claim` and `/unclaim` on request issues, the PR link, and the deadline.

    python3 .github/scripts/claimbot.py comment   # on issue_comment (reads GITHUB_EVENT_PATH)
    python3 .github/scripts/claimbot.py pr        # on pull_request_target (reads GITHUB_EVENT_PATH)
    python3 .github/scripts/claimbot.py sweep     # on schedule

A request issue moves needs-triage -> ready (a maintainer sets it) -> claimed (someone
comments /claim) -> in-review (a PR that says `Closes #n` is open) -> closed when that PR
merges. A claim has DEADLINE_DAYS to get a PR open; a draft PR counts. At REMIND_DAYS
with no PR the claimer gets one reminder, and at the deadline the request goes back to
`ready`. If the PR is closed without merging, the clock starts again from that moment.

The claim time is when `claimed` was last added, and the PRs are the ones GitHub links to
the issue, so the bot keeps no state of its own.

Comment text, PR titles and PR bodies are untrusted. The bot reads only a comment's first
line, matched against two fixed commands, and a PR's number; none of it reaches a shell
or a URL. The decisions are pure `decide_*` functions so they can be tested without GitHub.

Standard library only.
"""

from __future__ import annotations

import json
import os
import sys
import time
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
IN_REVIEW = "in-review"
UNCONFIRMED = {"needs-triage", "needs-info"}
MAINTAINERS = {"OWNER", "MEMBER", "COLLABORATOR"}
MAX_ACTIVE_CLAIMS = 3
DEADLINE_DAYS = 14
REMIND_DAYS = 10
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


@dataclass
class LinkedPR:
    """A pull request GitHub links to the issue (`Closes #n`, or the Development box)."""

    number: int
    url: str
    state: str  # OPEN, CLOSED or MERGED
    draft: bool = False
    closed_at: Optional[datetime] = None


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
    if is_pr or REQUEST not in labels or command is None or not is_open:
        return plan

    if command == "/claim":
        if commenter in assignees:
            plan.comment = f"@{commenter} 这个需求已经在你名下了。/ It's already yours."
            return plan
        if assignees:
            holder = ", ".join(f"@{a}" for a in assignees)
            plan.comment = (
                f"@{commenter} 这个需求 {holder} 正在做。想一起做可以在这里和 TA 商量；"
                f"领取后 {DEADLINE_DAYS} 天还没有 PR 的话，它会自动放回需求池。\n\n"
                f"{holder} is already on this. Coordinate here if you'd like to pair; "
                f"if there's no PR {DEADLINE_DAYS} days after the claim, it goes back to the pool."
            )
            return plan
        if IN_REVIEW in labels:
            plan.comment = (
                f"@{commenter} 这个需求已经有 PR 在等审核了，先看看那个 PR，能帮上忙的话在那里评论。\n\n"
                "This request already has a PR waiting for review. Have a look there and help out if you can."
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
            f"- **{DEADLINE_DAYS} 天内开 PR**，草稿 PR 也算。PR 描述里写 `Closes #{{number}}`，"
            "这样它会挂到这个需求上，合并时需求自动关闭。\n"
            f"- 第 {REMIND_DAYS} 天还没有 PR 会提醒一次；到第 {DEADLINE_DAYS} 天还没有，需求会放回需求池。"
            "不想做了随时评论 `/unclaim`。\n"
            f"- 在包的边车里加上 `\"request\": {{\"issue\": {{number}}, \"by\": \"<提需求的人>\"}}`，"
            "画廊会同时署上点子和实现两个人。\n\n"
            f"🚩 @{commenter} claimed this. Thank you!\n\n"
            f"- **Open a PR within {DEADLINE_DAYS} days**; a draft counts. Put `Closes #{{number}}` in its "
            "description so it links here and closes this request when it merges.\n"
            f"- With no PR by day {REMIND_DAYS} you'll get one reminder; by day {DEADLINE_DAYS} the request "
            "goes back to the pool. Comment `/unclaim` any time to hand it back.\n"
            "- Add `\"request\": {\"issue\": {number}, \"by\": \"<requester>\"}` to your pack's sidecar "
            "so the gallery credits both the idea and the build.\n\n"
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


def _pr_list(prs: List[LinkedPR]) -> str:
    return ", ".join(f"[#{p.number}]({p.url})" + (" (draft)" if p.draft else "") for p in prs)


def decide_sweep(
    labels: List[str],
    assignees: List[str],
    claimed_at: Optional[datetime],
    prs: List[LinkedPR],
    now: datetime,
    review_ended_at: Optional[datetime] = None,
) -> Plan:
    """Bring one open request in line with its PRs and its claim deadline."""
    plan = Plan()
    if REQUEST not in labels:
        return plan
    open_prs = [p for p in prs if p.state == "OPEN"]
    claimed = CLAIMED in labels and bool(assignees)
    who = " ".join(f"@{a}" for a in assignees)

    if open_prs:
        # A PR is what the claim was waiting for. Mark it for review, once.
        if STALE in labels:
            plan.remove_labels.append(STALE)
        if IN_REVIEW not in labels:
            plan.add_labels.append(IN_REVIEW)
            if READY in labels:
                plan.remove_labels.append(READY)
            plan.comment = (
                f"🔍 PR {_pr_list(open_prs)} 已经挂到这个需求上，等维护者审核。合并后这个需求会自动关闭。\n\n"
                f"🔍 PR {_pr_list(open_prs)} is linked here and waiting for review. "
                "This request closes when it merges."
            )
        return plan

    merged = any(p.state == "MERGED" for p in prs)
    if IN_REVIEW in labels:
        plan.remove_labels.append(IN_REVIEW)
        if not claimed and not merged:
            # Nobody holds it, so it goes back to the pool, unless a maintainer never
            # confirmed it in the first place.
            if not set(labels) & UNCONFIRMED:
                plan.add_labels.append(READY)
        elif claimed and not merged:
            plan.comment = (
                f"{who} 挂在这里的 PR 已经关掉或不再关联这个需求，没有合并。需求还在你名下，"
                f"{DEADLINE_DAYS} 天内再开一个 PR 就行；不做了评论 `/unclaim`。\n\n"
                f"{who} the linked PR was closed without merging, or no longer links here. The request "
                f"is still yours: open another PR within {DEADLINE_DAYS} days, or `/unclaim` it."
            )
        # The clock restarts now; the next sweep counts it from this label change.
        return plan
    if not claimed or claimed_at is None or merged:
        return plan

    # The clock starts at the claim, and again whenever a review ended without a merge.
    restarts = [p.closed_at for p in prs if p.state == "CLOSED" and p.closed_at]
    start = max([claimed_at] + restarts + ([review_ended_at] if review_ended_at else []))
    due = start + timedelta(days=DEADLINE_DAYS)
    if now >= due:
        plan.unassign.extend(assignees)
        plan.remove_labels.extend(l for l in (CLAIMED, STALE) if l in labels)
        plan.add_labels.append(READY)
        plan.comment = (
            f"{who} {DEADLINE_DAYS} 天里没有等到 PR，这个需求先放回需求池了，谢谢你！"
            "想继续做随时再 `/claim`。\n\n"
            f"No PR within {DEADLINE_DAYS} days, so this is back in the pool. Thanks, {who}. "
            "`/claim` it again any time."
        )
    elif now >= start + timedelta(days=REMIND_DAYS) and STALE not in labels:
        day = due.strftime("%Y-%m-%d")
        plan.add_labels.append(STALE)
        plan.comment = (
            f"{who} 还没看到这个需求的 PR。{day} 之前开一个就行，草稿 PR 也算，"
            f"描述里写 `Closes #{{number}}`；到时还没有，需求会放回需求池。不做了也没关系，评论 `/unclaim` 即可。\n\n"
            f"{who} no PR here yet. Open one before {day} (a draft counts) with `Closes #{{number}}` "
            "in its description; otherwise the request goes back to the pool. `/unclaim` is fine too."
        )
    return plan


def facts(node: Dict) -> Dict:
    """The decide_sweep inputs from one issue as the GraphQL query below returns it."""
    claimed_at = review_ended_at = None
    for event in (node.get("timelineItems") or {}).get("nodes") or []:
        name = ((event or {}).get("label") or {}).get("name")
        kind = (event or {}).get("__typename")
        if not event or not name or "createdAt" not in event:
            continue
        at = _time(event["createdAt"])
        if name == CLAIMED and kind == "LabeledEvent":
            claimed_at = at if claimed_at is None or at > claimed_at else claimed_at
        elif name == IN_REVIEW and kind == "UnlabeledEvent":
            review_ended_at = at if review_ended_at is None or at > review_ended_at else review_ended_at
    prs = [
        LinkedPR(
            number=int(p["number"]),
            url=str(p["url"]),
            state=str(p["state"]),
            draft=bool(p.get("isDraft")),
            closed_at=_time(p["closedAt"]) if p.get("closedAt") else None,
        )
        for p in (node.get("closedByPullRequestsReferences") or {}).get("nodes") or []
        if p
    ]
    return {
        "labels": [l["name"] for l in (node.get("labels") or {}).get("nodes") or []],
        "assignees": [a["login"] for a in (node.get("assignees") or {}).get("nodes") or []],
        "claimed_at": claimed_at,
        "review_ended_at": review_ended_at,
        "prs": prs,
    }


# --- GitHub API (thin) -------------------------------------------------------

ISSUE_FIELDS = """
fragment Req on Issue {
  number
  state
  labels(first: 30) { nodes { name } }
  assignees(first: 10) { nodes { login } }
  timelineItems(itemTypes: [LABELED_EVENT, UNLABELED_EVENT], last: 100) {
    nodes {
      __typename
      ... on LabeledEvent { createdAt label { name } }
      ... on UnlabeledEvent { createdAt label { name } }
    }
  }
  closedByPullRequestsReferences(includeClosedPrs: true, first: 20) { nodes { number url state isDraft closedAt } }
}
"""
OPEN_REQUESTS = ISSUE_FIELDS + """
query($owner: String!, $name: String!, $cursor: String) {
  repository(owner: $owner, name: $name) {
    issues(states: OPEN, labels: ["request"], first: 50, after: $cursor) {
      pageInfo { hasNextPage endCursor }
      nodes { ...Req }
    }
  }
}
"""
ONE_ISSUE = ISSUE_FIELDS + """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) { issue(number: $number) { ...Req } }
}
"""
PR_ISSUES = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) { closingIssuesReferences(first: 20) { nodes { number repository { nameWithOwner } } } }
  }
}
"""


class GitHub:
    def __init__(self, token: str, repo: str) -> None:
        self.token = token
        self.repo = repo
        self.owner, self.name = repo.split("/", 1)

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

    def graphql(self, query: str, **variables: object) -> Dict:
        result = self.call("POST", "/graphql", {"query": query, "variables": {"owner": self.owner, "name": self.name, **variables}})
        if not isinstance(result, dict) or result.get("errors") or "data" not in result:
            raise RuntimeError(f"GraphQL error: {result.get('errors') if isinstance(result, dict) else result}")
        return result["data"]

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
        # A claim waiting for review doesn't count: the builder's part is done.
        q = f"repo:{self.repo} is:issue is:open label:{CLAIMED} -label:{IN_REVIEW} assignee:{login}"
        result = self.call("GET", "/search/issues?" + urllib.parse.urlencode({"q": q, "per_page": 1}))
        return int(result["total_count"])  # type: ignore[index]

    def open_requests(self) -> List[Dict]:
        nodes: List[Dict] = []
        cursor = None
        while True:
            page = self.graphql(OPEN_REQUESTS, cursor=cursor)["repository"]["issues"]
            nodes.extend(n for n in page["nodes"] if n)
            if not page["pageInfo"]["hasNextPage"]:
                return nodes
            cursor = page["pageInfo"]["endCursor"]

    def issue(self, number: int) -> Optional[Dict]:
        return self.graphql(ONE_ISSUE, number=number)["repository"]["issue"]

    def issues_closed_by(self, pr: int) -> List[int]:
        found = self.graphql(PR_ISSUES, number=pr)["repository"]["pullRequest"] or {}
        refs = (found.get("closingIssuesReferences") or {}).get("nodes") or []
        return [int(r["number"]) for r in refs if r and r["repository"]["nameWithOwner"].lower() == self.repo.lower()]


def _time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def _names(items: List[dict], key: str) -> List[str]:
    return [item[key] for item in items or []]


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


def settle(gh: GitHub, node: Dict, now: datetime) -> None:
    if node.get("state") != "OPEN":
        return
    plan = decide_sweep(now=now, **facts(node))
    if not plan.empty():
        gh.apply(int(node["number"]), plan)
        print(f"#{node['number']}: {plan}")


def run_pr(gh: GitHub, event: Dict, now: datetime) -> None:
    """A PR opened, changed or closed: settle the requests it links to right away
    instead of waiting for the daily sweep."""
    number = int(event["pull_request"]["number"])
    issues = gh.issues_closed_by(number)
    if not issues and event.get("action") != "closed":
        # GitHub links `Closes #n` as the PR is saved; give it a moment, then look once more.
        time.sleep(15)
        issues = gh.issues_closed_by(number)
    for issue in issues:
        node = gh.issue(issue)
        if node:
            settle(gh, node, now)


def run_sweep(gh: GitHub, now: datetime) -> None:
    for node in gh.open_requests():
        settle(gh, node, now)


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in ("comment", "pr", "sweep"):
        print(__doc__, file=sys.stderr)
        return 2
    gh = GitHub(os.environ["GITHUB_TOKEN"], os.environ["GITHUB_REPOSITORY"])
    now = datetime.now(timezone.utc)
    if sys.argv[1] == "sweep":
        run_sweep(gh, now)
        return 0
    with open(os.environ["GITHUB_EVENT_PATH"], encoding="utf-8") as handle:
        event = json.load(handle)
    if sys.argv[1] == "comment":
        run_comment(gh, event)
    else:
        run_pr(gh, event, now)
    return 0


if __name__ == "__main__":
    sys.exit(main())
