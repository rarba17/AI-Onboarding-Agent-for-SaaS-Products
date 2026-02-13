-- AI Onboarding Agent — Database Schema
-- Auto-executed on first docker compose up

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Companies table (multi-tenant)
CREATE TABLE companies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    tone_settings JSONB DEFAULT '{"voice": "friendly", "formality": "casual", "emoji": true}'::jsonb,
    escalation_threshold INTEGER DEFAULT 3,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- API keys for SDK authentication
CREATE TABLE api_keys (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    key_hash TEXT NOT NULL,
    label TEXT DEFAULT 'default',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_api_keys_hash ON api_keys(key_hash);

-- Admin users (dashboard access)
CREATE TABLE admin_users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    full_name TEXT,
    role TEXT DEFAULT 'admin' CHECK (role IN ('admin', 'csm', 'viewer')),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_admin_users_email ON admin_users(email);

-- End users being onboarded
CREATE TABLE users (
    user_id TEXT NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    signup_date TIMESTAMPTZ DEFAULT NOW(),
    metadata JSONB DEFAULT '{}'::jsonb,
    PRIMARY KEY (user_id, company_id)
);

-- Sessions
CREATE TABLE sessions (
    session_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    start_time TIMESTAMPTZ DEFAULT NOW(),
    last_seen_time TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE
);
CREATE INDEX idx_sessions_user ON sessions(user_id, company_id);
CREATE INDEX idx_sessions_active ON sessions(is_active) WHERE is_active = TRUE;

-- Events
CREATE TABLE events (
    event_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    session_id TEXT REFERENCES sessions(session_id),
    event_type TEXT NOT NULL,
    target_element TEXT,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    properties JSONB DEFAULT '{}'::jsonb
);
CREATE INDEX idx_events_user ON events(user_id, company_id);
CREATE INDEX idx_events_session ON events(session_id);
CREATE INDEX idx_events_timestamp ON events(timestamp);

-- Nudges log
CREATE TABLE nudges (
    nudge_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    session_id TEXT REFERENCES sessions(session_id),
    stuck_point TEXT,
    nudge_type TEXT CHECK (nudge_type IN ('tooltip', 'in_app_chat', 'email_draft')),
    content TEXT NOT NULL,
    diagnosis JSONB DEFAULT '{}'::jsonb,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    status TEXT DEFAULT 'sent' CHECK (status IN ('sent', 'delivered', 'clicked', 'dismissed'))
);
CREATE INDEX idx_nudges_user ON nudges(user_id, company_id);
CREATE INDEX idx_nudges_session ON nudges(session_id);

-- Success baselines
CREATE TABLE baselines (
    baseline_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT DEFAULT 'Default Baseline',
    event_sequence JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_baselines_company ON baselines(company_id);

-- Escalation queue
CREATE TABLE escalations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id TEXT NOT NULL,
    company_id UUID NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    stuck_point TEXT,
    inferred_reason TEXT,
    nudge_log JSONB DEFAULT '[]'::jsonb,
    status TEXT DEFAULT 'open' CHECK (status IN ('open', 'in_progress', 'resolved', 'dismissed')),
    assigned_to UUID REFERENCES admin_users(id),
    deep_link TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    resolved_at TIMESTAMPTZ
);
CREATE INDEX idx_escalations_company ON escalations(company_id);
CREATE INDEX idx_escalations_status ON escalations(status);

-- Updated_at trigger
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_companies_updated_at
    BEFORE UPDATE ON companies
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_baselines_updated_at
    BEFORE UPDATE ON baselines
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
