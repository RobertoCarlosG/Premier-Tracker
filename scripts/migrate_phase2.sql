-- Migración Fase 2: equipos vinculados + snapshots.
-- Idempotente: seguro ejecutar más de una vez.
-- Ejecutar: psql $DATABASE_URL -f scripts/migrate_phase2.sql
--           o pegar en Supabase SQL Editor.

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ─────────────────────────────────────────
-- EQUIPOS VINCULADOS
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS saved_teams (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    -- Identificadores en Henrik API
    team_id       VARCHAR(255) NOT NULL,
    team_name     VARCHAR(255) NOT NULL,
    team_tag      VARCHAR(50)  NOT NULL,
    region        VARCHAR(20)  NOT NULL,   -- NA | EU | AP | KR | LATAM | BR
    division      VARCHAR(100),
    conference    VARCHAR(100),
    -- Metadata
    linked_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    is_primary    BOOLEAN      NOT NULL DEFAULT TRUE,
    UNIQUE (user_id, team_id)
);

CREATE INDEX IF NOT EXISTS idx_saved_teams_user   ON saved_teams(user_id);
CREATE INDEX IF NOT EXISTS idx_saved_teams_team   ON saved_teams(team_id);
CREATE INDEX IF NOT EXISTS idx_saved_teams_region ON saved_teams(region);


-- ─────────────────────────────────────────
-- SNAPSHOTS DE EQUIPO
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS team_snapshots (
    id            UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id       VARCHAR(255) NOT NULL,
    region        VARCHAR(20)  NOT NULL,
    -- Datos del snapshot
    rank_position INTEGER,
    division      VARCHAR(100),
    conference    VARCHAR(100),
    wins          INTEGER,
    losses        INTEGER,
    points        INTEGER,
    -- Metadata
    snapshot_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    source        VARCHAR(20)  NOT NULL DEFAULT 'cron'  -- cron | manual | onboarding
);

CREATE INDEX IF NOT EXISTS idx_ts_team_id  ON team_snapshots(team_id);
CREATE INDEX IF NOT EXISTS idx_ts_snapshot ON team_snapshots(team_id, snapshot_at DESC);
CREATE INDEX IF NOT EXISTS idx_ts_region   ON team_snapshots(region, snapshot_at DESC);


-- ─────────────────────────────────────────
-- SNAPSHOTS DE JUGADORES
-- ─────────────────────────────────────────

CREATE TABLE IF NOT EXISTS player_snapshots (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    team_id     VARCHAR(255) NOT NULL,
    puuid       VARCHAR(255) NOT NULL,
    player_name VARCHAR(255),
    player_tag  VARCHAR(50),
    region      VARCHAR(20)  NOT NULL,
    -- MMR
    mmr_current INTEGER,
    rank_tier   VARCHAR(50),
    rr_current  INTEGER,
    -- Metadata
    snapshot_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_ps_team_id  ON player_snapshots(team_id);
CREATE INDEX IF NOT EXISTS idx_ps_puuid    ON player_snapshots(puuid, snapshot_at DESC);
CREATE INDEX IF NOT EXISTS idx_ps_snapshot ON player_snapshots(team_id, snapshot_at DESC);
