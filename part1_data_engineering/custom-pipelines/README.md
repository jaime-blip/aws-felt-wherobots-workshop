# Custom Pipelines

Agent-generated pipeline variations live here — one subdirectory per
variation (e.g. `lightning-hazard/`, `agriculture-scoring/`).

## When a new notebook goes here vs. editing the reference

The reference notebooks one level up (`bronze-to-silver.ipynb`,
`silver-to-gold.ipynb`) are parameterizable. Tweaks to the **config cell** — AOI bbox, scoring
weights, temporal windows, or swapping to a different industry already
in `INDUSTRY_FACTORS` — are made **in the reference notebook** and
re-run. Don't create a new notebook for those.

A new notebook belongs here only when the analysis itself changes:

- A new hazard source (lightning, air quality, earthquake)
- A new industry that isn't already in `INDUSTRY_FACTORS`
- New derived metrics or a different scoring structure
- Any change the config cell can't express

## Rules

Pipelines here follow every rule in
[`../skills/wherobots-pipeline/SKILL.md`](../skills/wherobots-pipeline/SKILL.md) —
Wherobots idioms, layer contracts, quantile tiers, deferred flood
joins, the lot. Start from a copy of the reference notebook you're
diverging from so the participant can diff against the baseline.
