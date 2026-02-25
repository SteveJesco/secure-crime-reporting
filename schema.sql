-- ================================================================
-- SECURE CRIME REPORTING SYSTEM — DATABASE SCHEMA
-- Run this entire file in pgAdmin Query Tool on your crime_db
-- ================================================================

-- Officers (police)
CREATE TABLE IF NOT EXISTS officers (
    id            SERIAL PRIMARY KEY,
    officer_id    VARCHAR(20) UNIQUE NOT NULL,  -- e.g. "OFC-001"
    name          VARCHAR(150) NOT NULL,
    rank          VARCHAR(60)  DEFAULT 'Constable',
    department    VARCHAR(100),
    station       VARCHAR(100),
    badge_number  VARCHAR(50),
    password_hash TEXT NOT NULL,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Citizens (public users — auto-registered by national ID)
CREATE TABLE IF NOT EXISTS citizens (
    id           SERIAL PRIMARY KEY,
    national_id  VARCHAR(50) UNIQUE NOT NULL,
    display_name VARCHAR(150),
    phone        VARCHAR(30),
    email        VARCHAR(200),
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Crime Reports (from citizens)
CREATE TABLE IF NOT EXISTS reports (
    id                  SERIAL PRIMARY KEY,
    reference_number    VARCHAR(20) UNIQUE NOT NULL,
    citizen_id          INT REFERENCES citizens(id) ON DELETE SET NULL,
    is_anonymous        BOOLEAN NOT NULL DEFAULT FALSE,
    crime_type          VARCHAR(100) NOT NULL DEFAULT 'Other',
    description         TEXT NOT NULL,
    location            VARCHAR(300),
    county              VARCHAR(100) DEFAULT '',
    sub_county          VARCHAR(100) DEFAULT '',
    incident_date       DATE,
    incident_time       VARCHAR(20) DEFAULT '',
    suspect_info        TEXT DEFAULT '',
    witness_info        TEXT DEFAULT '',
    status              VARCHAR(30)  NOT NULL DEFAULT 'pending',
    -- pending | under_review | resolved | dismissed
    priority            VARCHAR(20)  NOT NULL DEFAULT 'medium',
    -- low | medium | high | critical
    officer_notes       TEXT DEFAULT '',
    case_number         VARCHAR(50) DEFAULT '',
    assigned_officer_id INT REFERENCES officers(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Report Updates / Officer Activity Log
CREATE TABLE IF NOT EXISTS report_updates (
    id                SERIAL PRIMARY KEY,
    report_id         INT NOT NULL REFERENCES reports(id) ON DELETE CASCADE,
    officer_id        INT REFERENCES officers(id) ON DELETE SET NULL,
    note              TEXT,
    status_changed_to VARCHAR(30),
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- SOS Alerts
CREATE TABLE IF NOT EXISTS sos_alerts (
    id          SERIAL PRIMARY KEY,
    citizen_id  INT REFERENCES citizens(id) ON DELETE SET NULL,
    latitude    NUMERIC(10, 7),
    longitude   NUMERIC(10, 7),
    address     VARCHAR(300),
    message     TEXT,
    status      VARCHAR(20) NOT NULL DEFAULT 'active',  -- active | resolved
    resolved_by INT REFERENCES officers(id) ON DELETE SET NULL,
    resolved_at TIMESTAMPTZ,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Safety Tips
CREATE TABLE IF NOT EXISTS safety_tips (
    id          SERIAL PRIMARY KEY,
    category    VARCHAR(80) NOT NULL,
    title       VARCHAR(200) NOT NULL,
    content     TEXT NOT NULL,
    icon        VARCHAR(50) DEFAULT 'bi-shield-check',
    sort_order  INT DEFAULT 0,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ================================================================
-- INDEXES for performance
-- ================================================================
CREATE INDEX IF NOT EXISTS idx_reports_citizen   ON reports(citizen_id);
CREATE INDEX IF NOT EXISTS idx_reports_status    ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_created   ON reports(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_reports_assigned  ON reports(assigned_officer_id);
CREATE INDEX IF NOT EXISTS idx_sos_status        ON sos_alerts(status);
