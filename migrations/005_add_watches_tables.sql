-- Watch Evaluation System Tables
-- Adds watches, watch_runs, and alerts tables to support persistent investment monitoring briefs.
-- Run this migration manually against your PostgreSQL database.

-- app.watches: stores persistent monitoring instructions
CREATE TABLE IF NOT EXISTS app.watches (
    id          UUID PRIMARY KEY,
    account_id  INTEGER NOT NULL REFERENCES app.accounts(id),
    name        VARCHAR NOT NULL,
    description VARCHAR,
    scope_type  VARCHAR(50) NOT NULL,   -- WatchScopeType: portfolio|holding|theme|market
    scope_ref   VARCHAR,                -- e.g. portfolio_id, holding_id, ticker
    watch_type  VARCHAR(50) NOT NULL,   -- WatchType: portfolio_health|holding_news|unusual_move|...
    cadence     VARCHAR(20) NOT NULL,   -- WatchCadence: manual|morning|afternoon|daily|twice_daily|weekly|monthly
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMP WITH TIME ZONE,
    last_run_at TIMESTAMP WITH TIME ZONE,
    last_alert_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_watches_account_id ON app.watches(account_id);
CREATE INDEX IF NOT EXISTS ix_watches_is_active   ON app.watches(is_active);
CREATE INDEX IF NOT EXISTS ix_watches_cadence      ON app.watches(cadence);

-- app.watch_runs: records each individual evaluation run of a watch
CREATE TABLE IF NOT EXISTS app.watch_runs (
    id             UUID PRIMARY KEY,
    watch_id       UUID NOT NULL REFERENCES app.watches(id),
    started_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    completed_at   TIMESTAMP WITH TIME ZONE,
    status         VARCHAR(20) NOT NULL,  -- WatchRunStatus: started|completed|failed|suppressed
    summary        TEXT,
    raw_result_json JSON,
    error_message  TEXT
);

CREATE INDEX IF NOT EXISTS ix_watch_runs_watch_id ON app.watch_runs(watch_id);

-- app.alerts: actionable alerts produced by watch runs
CREATE TABLE IF NOT EXISTS app.alerts (
    id                UUID PRIMARY KEY,
    watch_id          UUID NOT NULL REFERENCES app.watches(id),
    watch_run_id      UUID REFERENCES app.watch_runs(id),
    severity          VARCHAR(10) NOT NULL,  -- AlertSeverity: info|low|medium|high
    title             VARCHAR NOT NULL,
    message           TEXT NOT NULL,
    evidence_json     JSON,
    sent_at           TIMESTAMP WITH TIME ZONE,
    suppressed_reason VARCHAR,
    created_at        TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_alerts_watch_id     ON app.alerts(watch_id);
CREATE INDEX IF NOT EXISTS ix_alerts_watch_run_id ON app.alerts(watch_run_id);

COMMENT ON TABLE app.watches IS 'Persistent investment monitoring briefs evaluated on a schedule';
COMMENT ON TABLE app.watch_runs IS 'Individual evaluation runs of a watch';
COMMENT ON TABLE app.alerts IS 'Actionable alerts produced by watch evaluations';
