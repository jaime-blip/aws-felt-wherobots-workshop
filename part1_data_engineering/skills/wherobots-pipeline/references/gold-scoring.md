# Gold scoring — per-industry source metrics and quantile tiers

Detailed reference for designing the Gold layer. Load this when generating
`silver-to-gold.ipynb` or when a participant asks for a non-default scoring
configuration (new industry, different weights, different source columns).

The core 5-step framework and the "use `percent_rank()` not fixed thresholds"
rule live in the main `SKILL.md`. This file is the supporting material:
the full per-industry metrics table, code examples, and design checklist.

---

## Per-industry source metrics

**Problem**: If all industries normalize the same 3 columns and only change
the weights, the rank ordering barely shifts — all industries end up with
nearly identical tier distributions on the map. Participants see four
"different" scoring views that visually look the same.

**Solution**: Each industry uses different raw source columns for its hazard
factors. Same 3 factor slots (`wildfire_factor`, `flood_factor`,
`severe_weather_factor`), but each industry picks the column that best
captures the aspect of the hazard that matters for its decision.

Map each industry to the *aspect* of each hazard that drives its decision:

| Aspect | Example Column | Best For |
|--------|----------------|----------|
| Average risk | `burn_prob_mean` | Insurance (claim frequency), CapMarkets (portfolio risk) |
| Worst-case risk | `burn_prob_max` | CRE (go/no-go screening) |
| Intensity | `flame_length_mean` | Energy (ignition risk) |
| Duration | `flood_duration_days` | Insurance (sustained claims exposure) |
| Peak severity | `flood_max_wtr_class` | CRE (deal-breaker threshold) |
| Frequency | `flood_event_count` | CapMarkets, Energy (recurrence) |
| Broad area count | `event_count_25km` | Insurance (wide-area exposure) |
| Local intensity | `event_count_5km` | Energy (at-the-asset impacts) |
| Proximity | inverse distance to nearest event | CRE (nearby = deal-breaker) |
| Peak event severity | `max_hail_sevprob` | CapMarkets (supply chain disruption) |

Store the mapping in an `INDUSTRY_FACTORS` dict in the config cell:

```python
INDUSTRY_FACTORS = {
    "insurance": {
        "wildfire_factor":       "burn_prob_mean",
        "flood_factor":          "flood_duration_days",
        "severe_weather_factor": "event_count_25km",
    },
    "commercial_real_estate": {
        "wildfire_factor":       "burn_prob_max",
        "flood_factor":          "flood_max_wtr_class",
        "severe_weather_factor": "nearest_event_dist_m",  # will be inverted in normalization
    },
    "capital_markets": {
        "wildfire_factor":       "burn_prob_mean",
        "flood_factor":          "flood_event_count",
        "severe_weather_factor": "max_hail_sevprob",
    },
    "energy_utilities": {
        "wildfire_factor":       "flame_length_mean",
        "flood_factor":          "flood_event_count",
        "severe_weather_factor": "event_count_5km",
    },
}
```

Use a helper function to map each industry's `norm_*` columns into the
three factor slots, compute the weighted composite, and assign the tier:

```python
def add_industry_factors(df, industry, weights):
    factors = INDUSTRY_FACTORS[industry]
    return (
        df
        .withColumn("wildfire_factor",       F.col(f"norm_{factors['wildfire_factor']}"))
        .withColumn("flood_factor",          F.col(f"norm_{factors['flood_factor']}"))
        .withColumn("severe_weather_factor", F.col(f"norm_{factors['severe_weather_factor']}"))
        .withColumn("risk_score",
            F.col("wildfire_factor")       * F.lit(weights["wildfire"]) +
            F.col("flood_factor")          * F.lit(weights["flood"]) +
            F.col("severe_weather_factor") * F.lit(weights["severe_weather"])
        )
    )
```

---

## Quantile-based risk tiers

**Do NOT use fixed score thresholds.** With right-skewed hazard data, fixed
thresholds like `Critical ≥ 0.80` produce extreme imbalance (e.g. 882K "low"
and 65 "critical" out of 358K buildings), making maps useless.

Use `percent_rank()` over `risk_score` to cut tiers by percentile:

```python
RISK_PERCENTILES = {
    "critical": 0.95,   # top 5%
    "high":     0.80,   # 80th–95th percentile
    "elevated": 0.50,   # 50th–80th percentile
    "moderate": 0.20,   # 20th–50th percentile
    "low":      0.00,   # bottom 20%
}

def classify_risk_tier(score_col: str) -> F.Column:
    pct = F.percent_rank().over(Window.orderBy(F.col(score_col).asc()))
    return (
        F.when(pct >= RISK_PERCENTILES["critical"], F.lit("critical"))
         .when(pct >= RISK_PERCENTILES["high"],     F.lit("high"))
         .when(pct >= RISK_PERCENTILES["elevated"], F.lit("elevated"))
         .when(pct >= RISK_PERCENTILES["moderate"], F.lit("moderate"))
         .otherwise(F.lit("low"))
    )
```

This guarantees a visually balanced map (~5/15/30/30/20 split) regardless
of score skew. Combined with per-industry source metrics above, each
industry gets genuinely different tier assignments despite using the same
percentile cuts.

---

## Score explanation JSON

Every Gold row carries a `score_explanation` STRING column with the factor
breakdown — component values, weights, AND the source column names that
fed them. Downstream consumers (Felt tooltips, analyst queries) can then
tell exactly which raw column drove each factor, not just its normalized
value:

```python
def build_score_explanation(industry, weights):
    factors = INDUSTRY_FACTORS[industry]
    return F.to_json(
        F.struct(
            F.round(F.col("wildfire_factor"), 4).alias("wildfire"),
            F.round(F.col("flood_factor"), 4).alias("flood"),
            F.round(F.col("severe_weather_factor"), 4).alias("severe_weather"),
            F.round(F.col("risk_score"), 4).alias("composite"),
            F.lit(weights["wildfire"]).alias("weight_wildfire"),
            F.lit(weights["flood"]).alias("weight_flood"),
            F.lit(weights["severe_weather"]).alias("weight_severe_weather"),
            F.lit(factors["wildfire_factor"]).alias("source_wildfire"),
            F.lit(factors["flood_factor"]).alias("source_flood"),
            F.lit(factors["severe_weather_factor"]).alias("source_severe_weather"),
        )
    )
```

---

## Designing factors for a new industry

When a participant asks for a new industry (e.g. "agriculture", "logistics",
"retail"), walk through this checklist before generating code:

1. **Identify the primary decision** the industry makes about an asset
   (underwrite, acquire, divest, harden, insure, lease, move).
2. For each hazard, ask: *which aspect drives that decision?* (severity?
   duration? proximity? frequency? worst-case?)
3. **Choose the raw column** that best captures that aspect — pick from
   the `asset_enriched` schema; don't invent new columns.
4. **Rank hazards by impact** for this industry → assign weights. Most
   impactful hazard gets 0.35–0.50, the rest distribute so all three sum
   to exactly 1.0.
5. Select 2–4 **derived metrics** specific to the industry (e.g. insurance
   → `estimated_loss_band`, CRE → `acquisition_screen_flag`).
6. **Document rationale** (in the generated notebook's markdown), propose
   to user, wait for confirmation before writing the write cell.
