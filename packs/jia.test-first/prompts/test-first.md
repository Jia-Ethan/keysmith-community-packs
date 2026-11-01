Before writing the implementation, write the tests. Treat the task description
as the spec and turn it into cases.

Do this:
1. List the behaviours the code must have, as a short checklist — the normal
   case, the boundaries, the error cases, and anything the spec implies but
   doesn't state. Flag anything ambiguous and ask rather than assume.
2. Write the tests against that checklist, using the project's existing test
   framework and style (look at a neighbouring test file first). One behaviour
   per test; name each test for the behaviour it pins.
3. Cover the edges that bite: empty, zero, one, many, too many; null and
   missing; duplicate; wrong type; the boundary and the value just past it.
4. Keep each test readable as a spec — arrange, act, assert — with no logic in
   the test itself.

Only after we agree on the tests, write the implementation that makes them
pass. If a test is hard to write, say what that tells us about the design.
