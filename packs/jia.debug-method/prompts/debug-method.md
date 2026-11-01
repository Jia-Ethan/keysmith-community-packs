Help me debug this methodically. Do not guess at a fix and do not change code
until we understand the failure.

Work in this order, and tell me which step you're on:

1. **Restate the bug** as observed vs. expected, with the exact error and the
   smallest input that triggers it. If I haven't given you that, ask for it.
2. **Form hypotheses** — two or three concrete, falsifiable guesses about the
   cause, most likely first. For each, say what you'd expect to see if it were
   true.
3. **Find the cheapest test** that tells one hypothesis apart from the others —
   a log line, a value to print, a case to run. Prefer a read over a write.
4. **Read the result with me** and rule hypotheses in or out. Narrow the search
   by half each round; don't widen it.
5. Only once the cause is proven, propose the smallest fix, and name the test
   that would have caught it.

If the evidence contradicts your best guess, say so and back up. Stay with the
one failing case until it is explained.
