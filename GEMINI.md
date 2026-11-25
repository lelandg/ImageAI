@AGENTS.md

# GEMINI.md — Gemini / agy specifics

All rules for this repository are in AGENTS.md. Gemini CLI loads them through
the import above; agy loads AGENTS.md directly and ignores that line.

- A code review the maintainer asks for in an interactive session is saved to
  `Docs/GeminiCodeReview_YYYYMMDD.md`. A review-council run (read-only,
  `--mode plan --sandbox`) writes nothing in the repository; its answer goes
  to the result file the caller names.
