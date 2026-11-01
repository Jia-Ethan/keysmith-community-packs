Review the current diff the way a careful teammate would before you open a pull
request. Read the whole change first, then go file by file.

For each issue you find, give it a severity and keep it concrete:
- **blocker** — a bug, a security hole, data loss, or a broken contract. Say what
  input triggers it and what goes wrong.
- **should-fix** — a correctness risk, a missing edge case, or a test gap.
- **nit** — style, naming, or wording. Keep these few and clearly labelled.

Rules for the review:
- Point at an exact line and quote the smallest snippet that shows the problem.
- Propose the fix, don't just name the smell. If you can write the corrected
  line, write it.
- Check error paths, not just the happy path: empty input, nulls, timeouts,
  concurrent access, off-by-one at boundaries.
- Note anything the diff changed that its tests or docs no longer match.
- If a piece is fine, say nothing about it. Silence means "looks good."

End with a one-line verdict: ship / ship after should-fixes / needs another pass.
