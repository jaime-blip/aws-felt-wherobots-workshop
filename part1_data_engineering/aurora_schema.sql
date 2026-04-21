-- =============================================================================
-- Aurora PostgreSQL (PostGIS) — Workshop Schema
--
-- These DDL statements create the Workshop tables in Aurora for serving to Felt
-- dashboards and downstream consumers. Run once against your Aurora cluster.
--
-- Prerequisites:
--   CREATE EXTENSION IF NOT EXISTS postgis;
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS workshop;

-- ── Scoring Configuration ────────────────────────────────────────────────────
-- Stores per-industry factor weights so dashboards can reference the methodology.

CREATE TABLE workshop.scoring_config (
    config_id            TEXT PRIMARY KEY,
    industry             TEXT NOT NULL,
    factor_name          TEXT NOT NULL,
    weight               DOUBLE PRECISION NOT NULL,
    normalization_method TEXT NOT NULL DEFAULT 'min_max',
    normalization_params JSONB,
    description          TEXT,
    version              INTEGER NOT NULL DEFAULT 1,
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(industry, factor_name, version)
);

-- ── Insurance Exposure ───────────────────────────────────────────────────────

CREATE TABLE workshop.insurance_exposure (
    asset_id              TEXT PRIMARY KEY,
    geometry              GEOMETRY(Polygon, 4326) NOT NULL,
    building_class        TEXT,
    wildfire_factor       DOUBLE PRECISION,
    flood_factor          DOUBLE PRECISION,
    severe_weather_factor DOUBLE PRECISION,
    risk_score            DOUBLE PRECISION NOT NULL,
    risk_tier             TEXT NOT NULL,
    exposure_delta        DOUBLE PRECISION,
    triage_priority       INTEGER,
    relative_risk_band    TEXT,
    score_explanation     JSONB,
    weather_window_start  DATE,
    weather_window_end    DATE,
    computed_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_insurance_exposure_geom ON workshop.insurance_exposure USING GIST(geometry);
CREATE INDEX idx_insurance_exposure_risk ON workshop.insurance_exposure(risk_tier);

-- ── Commercial Real Estate Risk ──────────────────────────────────────────────

CREATE TABLE workshop.cre_risk (
    asset_id                  TEXT PRIMARY KEY,
    geometry                  GEOMETRY(Polygon, 4326) NOT NULL,
    building_class            TEXT,
    wildfire_factor           DOUBLE PRECISION,
    flood_factor              DOUBLE PRECISION,
    severe_weather_factor     DOUBLE PRECISION,
    risk_score                DOUBLE PRECISION NOT NULL,
    risk_tier                 TEXT NOT NULL,
    acquisition_screen_flag   BOOLEAN DEFAULT FALSE,
    exposure_magnitude_index  DOUBLE PRECISION,
    hazard_proximity_m        DOUBLE PRECISION,
    score_explanation         JSONB,
    computed_at               TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_cre_risk_geom   ON workshop.cre_risk USING GIST(geometry);
CREATE INDEX idx_cre_risk_screen ON workshop.cre_risk(acquisition_screen_flag);

-- ── Capital Markets Signals ──────────────────────────────────────────────────

CREATE TABLE workshop.capital_markets_signals (
    asset_id                   TEXT PRIMARY KEY,
    geometry                   GEOMETRY(Polygon, 4326) NOT NULL,
    building_class             TEXT,
    wildfire_factor            DOUBLE PRECISION,
    flood_factor               DOUBLE PRECISION,
    severe_weather_factor      DOUBLE PRECISION,
    risk_score                 DOUBLE PRECISION NOT NULL,
    disruption_signal          DOUBLE PRECISION,
    supply_chain_vulnerability DOUBLE PRECISION,
    event_density_signal       DOUBLE PRECISION,
    score_explanation          JSONB,
    weather_window_start       DATE,
    weather_window_end         DATE,
    computed_at                TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_capital_markets_geom ON workshop.capital_markets_signals USING GIST(geometry);

-- ── Energy & Utilities Asset Risk ────────────────────────────────────────────
-- NOTE: Scores building footprints as a proxy for energy-adjacent assets.
-- Does not contain actual utility infrastructure (substations, lines, pipelines).

CREATE TABLE workshop.energy_asset_risk (
    asset_id                 TEXT PRIMARY KEY,
    geometry                 GEOMETRY(Polygon, 4326) NOT NULL,
    building_class           TEXT,
    wildfire_factor          DOUBLE PRECISION,
    flood_factor             DOUBLE PRECISION,
    severe_weather_factor    DOUBLE PRECISION,
    risk_score               DOUBLE PRECISION NOT NULL,
    risk_tier                TEXT NOT NULL,
    outage_probability       DOUBLE PRECISION,
    wildfire_ignition_risk   DOUBLE PRECISION,
    weather_impact_frequency DOUBLE PRECISION,
    score_explanation        JSONB,
    computed_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_energy_asset_geom ON workshop.energy_asset_risk USING GIST(geometry);
