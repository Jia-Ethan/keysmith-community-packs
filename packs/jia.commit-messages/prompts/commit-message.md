Write a commit message for the staged changes. Read the diff first; describe
what actually changed, not what you guessed the task was.

Format:
- A subject line in the imperative mood, under 60 characters, no trailing
  period: "Fix stale cache after rename", not "Fixed" or "Fixes".
- A blank line, then a body that wraps at 72 characters, only if the change
  needs it. Explain the why and the user-visible effect, not a restatement of
  the diff.
- If the repo uses Conventional Commits (feat:, fix:, chore: ...), match that
  style; otherwise don't invent a prefix.

Keep it honest: one logical change per message. If the diff does two unrelated
things, say so and suggest splitting it. Don't credit tools or add trailers
unless the repo's existing history does.
