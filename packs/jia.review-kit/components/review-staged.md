---
description: Review the staged change before you commit or open a PR
argument-hint: "[path or focus]"
---

Review the change that is staged for commit. If nothing is staged, review the
working-tree diff instead and say so.

Focus: $ARGUMENTS

Read the whole change first, then go file by file. For each problem give a severity
(blocker, should-fix or nit), the exact line, the smallest snippet that shows it, and
the fix. Check error paths as well as the happy path. Say nothing about parts that are
fine.

End with one line: ship, ship after should-fixes, or needs another pass.
