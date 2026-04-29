# GitHub Copilot — Workshop Context

Read the root [`CLAUDE.md`](../CLAUDE.md) for project orientation, the
three participant modes (Explore / Run Reference / Generate Custom), and
pointers to the authoritative skill rules.

Before any data-engineering work in `part1_data_engineering/`, read
[`part1_data_engineering/skills/wherobots-pipeline/SKILL.md`](../part1_data_engineering/skills/wherobots-pipeline/SKILL.md) —
it has the non-obvious Wherobots idioms (auto-reproject, `RS_ZonalStats`
signatures, `use_sphere=TRUE`, deferred flood joins, quantile tiers,
protected files) that will bite if missed.

Participants have near-zero geospatial background. Teach as you go:
name data before using it, show scale (rows / runtime) before large
operations, present options with tradeoffs where the skill allows
multiple valid answers.
