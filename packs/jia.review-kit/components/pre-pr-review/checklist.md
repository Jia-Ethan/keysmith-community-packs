# Severities

- **blocker**: a bug, a security hole, data loss, or a broken contract. Say what input
  triggers it and what goes wrong.
- **should-fix**: a correctness risk, a missing edge case, or a test gap.
- **nit**: style, naming or wording. Keep these few and label them clearly.

# Before you call it done

- Every blocker names the input that triggers it.
- Every finding has a proposed fix; if you can write the corrected line, write it.
- Nothing is reported twice under different names.
