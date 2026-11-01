---
name: pre-pr-review
description: Review the current change like a careful teammate before a pull request is opened. Use when the user asks for a review of their diff, staged changes or branch, or says they are about to open a PR.
---

# Pre-PR review

Review the change the way a careful teammate would before it goes up for review.

## Steps

1. Find the change. Prefer what the user named; otherwise use the staged diff, then the
   working-tree diff, then the branch against its base. Say which one you reviewed.
2. Read the whole change once before commenting, so you judge each part in context.
3. Go file by file. For each problem, record a severity, the exact line, the smallest
   snippet that shows it, and the fix.
4. Check the error paths, not just the happy path: empty input, nulls, timeouts,
   concurrent access, off-by-one at boundaries.
5. Note anything the change made that its tests or docs no longer match.

Use the severities in [checklist.md](checklist.md).

## Output

- Problems grouped by severity, most severe first.
- If a piece is fine, say nothing about it. Silence means "looks good."
- End with one line: **ship**, **ship after should-fixes**, or **needs another pass**.

Do not edit files during the review unless the user asks you to apply the fixes.
