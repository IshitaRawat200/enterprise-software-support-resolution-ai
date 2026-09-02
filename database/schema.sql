-- ============================================================
-- Enterprise Software Support & Resolution Intelligence System
-- PostgreSQL + pgvector schema
-- ============================================================

-- ------------------------------------------------------------
-- Extensions
-- ------------------------------------------------------------

CREATE EXTENSION IF NOT EXISTS vector;

-- ------------------------------------------------------------
-- ENUM TYPES
-- ------------------------------------------------------------

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_type WHERE typname = 'user_role'
    ) THEN
        CREATE TYPE user_role AS ENUM (
            'customer',
            'support_agent'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type WHERE typname = 'ticket_status'
    ) THEN
        CREATE TYPE ticket_status AS ENUM (
            'open',
            'in_progress',
            'resolved',
            'closed'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type WHERE typname = 'ticket_severity'
    ) THEN
        CREATE TYPE ticket_severity AS ENUM (
            'low',
            'medium',
            'high',
            'critical'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type WHERE typname = 'message_sender'
    ) THEN
        CREATE TYPE message_sender AS ENUM (
            'customer',
            'ai',
            'support_agent'
        );
    END IF;

    IF NOT EXISTS (
        SELECT 1 FROM pg_type WHERE typname = 'escalation_status'
    ) THEN
        CREATE TYPE escalation_status AS ENUM (
            'open',
            'in_progress',
            'resolved'
        );
    END IF;
END
$$;

-- ------------------------------------------------------------
-- USERS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,

    role user_role NOT NULL,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- CUSTOMERS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    customer_code VARCHAR(50) NOT NULL UNIQUE,

    user_id UUID UNIQUE,

    company_name VARCHAR(255) NOT NULL,
    contact_name VARCHAR(255),

    region VARCHAR(100),
    industry VARCHAR(100),

    account_status VARCHAR(50) NOT NULL DEFAULT 'active',

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_customers_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- SUBSCRIPTIONS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    customer_id UUID NOT NULL,

    plan_name VARCHAR(100) NOT NULL,

    status VARCHAR(50) NOT NULL DEFAULT 'active',

    start_date DATE,
    end_date DATE,

    seats INTEGER,

    is_premium BOOLEAN NOT NULL DEFAULT FALSE,

    entitlements JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_subscriptions_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(id)
        ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- SUPPORT TICKETS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS support_tickets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    ticket_number VARCHAR(30) NOT NULL UNIQUE,

    customer_id UUID NOT NULL,

    subject VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,

    status ticket_status NOT NULL DEFAULT 'open',

    intent VARCHAR(100),
    route VARCHAR(50),

    severity ticket_severity NOT NULL DEFAULT 'low',

    confidence NUMERIC(5,4),

    escalation_required BOOLEAN NOT NULL DEFAULT FALSE,
    escalation_reason TEXT,

    ai_investigation_summary TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    CONSTRAINT fk_support_tickets_customer
        FOREIGN KEY (customer_id)
        REFERENCES customers(id)
        ON DELETE CASCADE,

    CONSTRAINT chk_ticket_confidence
        CHECK (
            confidence IS NULL
            OR (
                confidence >= 0
                AND confidence <= 1
            )
        )
);

-- ------------------------------------------------------------
-- TICKET MESSAGES
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS ticket_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    ticket_id UUID NOT NULL,

    sender_type message_sender NOT NULL,

    sender_user_id UUID,

    message TEXT NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_ticket_messages_ticket
        FOREIGN KEY (ticket_id)
        REFERENCES support_tickets(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_ticket_messages_sender
        FOREIGN KEY (sender_user_id)
        REFERENCES users(id)
        ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- INCIDENT LOGS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS incident_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    incident_code VARCHAR(100) NOT NULL UNIQUE,

    title VARCHAR(500) NOT NULL,
    description TEXT NOT NULL,

    service_name VARCHAR(255),

    severity ticket_severity NOT NULL,

    status VARCHAR(50) NOT NULL,

    affected_customers_count INTEGER DEFAULT 0,

    affects_production BOOLEAN NOT NULL DEFAULT FALSE,

    unresolved_critical_alert BOOLEAN NOT NULL DEFAULT FALSE,

    security_related BOOLEAN NOT NULL DEFAULT FALSE,

    data_loss_reported BOOLEAN NOT NULL DEFAULT FALSE,

    started_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- KNOWLEDGE ARTICLES
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS knowledge_articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    article_code VARCHAR(100) NOT NULL UNIQUE,

    title VARCHAR(500) NOT NULL,

    description TEXT,

    product_name VARCHAR(255),
    product_version VARCHAR(100),

    source_url TEXT,

    version VARCHAR(100),

    published_at TIMESTAMPTZ,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- ------------------------------------------------------------
-- DOCUMENTS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    knowledge_article_id UUID,

    document_name VARCHAR(500) NOT NULL,

    document_type VARCHAR(100),

    source_url TEXT,

    product_name VARCHAR(255),
    product_version VARCHAR(100),

    version VARCHAR(100),

    content_hash VARCHAR(128),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_documents_article
        FOREIGN KEY (knowledge_article_id)
        REFERENCES knowledge_articles(id)
        ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- DOCUMENT CHUNKS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    document_id UUID NOT NULL,

    chunk_index INTEGER NOT NULL,

    content TEXT NOT NULL,

    token_count INTEGER,

    embedding vector(1536),

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_document_chunks_document
        FOREIGN KEY (document_id)
        REFERENCES documents(id)
        ON DELETE CASCADE,

    CONSTRAINT uq_document_chunk
        UNIQUE (document_id, chunk_index)
);

-- ------------------------------------------------------------
-- CONVERSATION HISTORY
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS conversation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    session_id UUID NOT NULL,

    user_id UUID NOT NULL,

    ticket_id UUID,

    role VARCHAR(50) NOT NULL,

    content TEXT NOT NULL,

    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_conversation_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_conversation_ticket
        FOREIGN KEY (ticket_id)
        REFERENCES support_tickets(id)
        ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- AGENT STATE
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS agent_state (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    session_id UUID NOT NULL UNIQUE,

    user_id UUID NOT NULL,

    ticket_id UUID,

    state JSONB NOT NULL DEFAULT '{}'::jsonb,

    checkpoint_id VARCHAR(255),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_agent_state_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_agent_state_ticket
        FOREIGN KEY (ticket_id)
        REFERENCES support_tickets(id)
        ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- MEMORY FACTS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS memory_facts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    user_id UUID NOT NULL,

    fact_key VARCHAR(255) NOT NULL,
    fact_value TEXT NOT NULL,

    source VARCHAR(100),

    confidence NUMERIC(5,4),

    expires_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_memory_facts_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE CASCADE,

    CONSTRAINT chk_memory_confidence
        CHECK (
            confidence IS NULL
            OR (
                confidence >= 0
                AND confidence <= 1
            )
        )
);

-- ------------------------------------------------------------
-- ESCALATIONS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS escalations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    ticket_id UUID NOT NULL UNIQUE,

    status escalation_status NOT NULL DEFAULT 'open',

    reason TEXT NOT NULL,

    severity ticket_severity NOT NULL,

    confidence NUMERIC(5,4),

    handoff_package JSONB NOT NULL DEFAULT '{}'::jsonb,

    investigation_summary TEXT,

    support_agent_id UUID,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    resolved_at TIMESTAMPTZ,

    CONSTRAINT fk_escalations_ticket
        FOREIGN KEY (ticket_id)
        REFERENCES support_tickets(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_escalations_support_agent
        FOREIGN KEY (support_agent_id)
        REFERENCES users(id)
        ON DELETE SET NULL,

    CONSTRAINT chk_escalation_confidence
        CHECK (
            confidence IS NULL
            OR (
                confidence >= 0
                AND confidence <= 1
            )
        )
);

-- ------------------------------------------------------------
-- AUDIT EVENTS
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    request_id UUID NOT NULL,

    user_id UUID,

    session_id UUID,

    ticket_id UUID,

    event_type VARCHAR(100) NOT NULL,

    actor VARCHAR(100),

    action VARCHAR(255),

    details JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_audit_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_audit_ticket
        FOREIGN KEY (ticket_id)
        REFERENCES support_tickets(id)
        ON DELETE SET NULL
);

-- ------------------------------------------------------------
-- KNOWLEDGE ARTICLE USAGE
-- NIIT SPECIFICATION TABLE
-- ------------------------------------------------------------

CREATE TABLE IF NOT EXISTS knowlege_article_usage (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    article_id UUID NOT NULL,

    user_id UUID,

    ticket_id UUID,

    query TEXT,

    usage_type VARCHAR(100),

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_article_usage_article
        FOREIGN KEY (article_id)
        REFERENCES knowledge_articles(id)
        ON DELETE CASCADE,

    CONSTRAINT fk_article_usage_user
        FOREIGN KEY (user_id)
        REFERENCES users(id)
        ON DELETE SET NULL,

    CONSTRAINT fk_article_usage_ticket
        FOREIGN KEY (ticket_id)
        REFERENCES support_tickets(id)
        ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_article_usage_article
    ON knowlege_article_usage(article_id);

CREATE INDEX IF NOT EXISTS idx_article_usage_user
    ON knowlege_article_usage(user_id);

CREATE INDEX IF NOT EXISTS idx_article_usage_ticket
    ON knowlege_article_usage(ticket_id);

-- ------------------------------------------------------------
-- INDEXES
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_customers_customer_code
    ON customers(customer_code);

CREATE INDEX IF NOT EXISTS idx_subscriptions_customer
    ON subscriptions(customer_id);

CREATE INDEX IF NOT EXISTS idx_support_tickets_customer
    ON support_tickets(customer_id);

CREATE INDEX IF NOT EXISTS idx_support_tickets_status
    ON support_tickets(status);

CREATE INDEX IF NOT EXISTS idx_support_tickets_severity
    ON support_tickets(severity);

CREATE INDEX IF NOT EXISTS idx_ticket_messages_ticket
    ON ticket_messages(ticket_id);

CREATE INDEX IF NOT EXISTS idx_incident_logs_severity
    ON incident_logs(severity);

CREATE INDEX IF NOT EXISTS idx_incident_logs_status
    ON incident_logs(status);

CREATE INDEX IF NOT EXISTS idx_documents_product_version
    ON documents(product_name, product_version);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document
    ON document_chunks(document_id);

CREATE INDEX IF NOT EXISTS idx_conversation_session
    ON conversation_history(session_id);

CREATE INDEX IF NOT EXISTS idx_conversation_user
    ON conversation_history(user_id);

CREATE INDEX IF NOT EXISTS idx_audit_request
    ON audit_events(request_id);

CREATE INDEX IF NOT EXISTS idx_audit_ticket
    ON audit_events(ticket_id);

-- ------------------------------------------------------------
-- VECTOR INDEX
-- ------------------------------------------------------------

CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding
ON document_chunks
USING hnsw (embedding vector_cosine_ops);