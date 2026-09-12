-- ============================================================
-- Enterprise Software Support & Resolution Intelligence System
-- Synthetic Seed Data
-- ============================================================

-- ============================================================
-- USERS
-- ============================================================

INSERT INTO users (
    id,
    email,
    password_hash,
    role,
    is_active
)
VALUES
(
    '10000000-0000-0000-0000-000000000001',
    'customer1@example.com',
    'YOUR_REAL_CUSTOMER1_HASH',
    'customer',
    TRUE
),
(
    '10000000-0000-0000-0000-000000000002',
    'customer2@example.com',
    'YOUR_REAL_CUSTOMER2_HASH',
    'customer',
    TRUE
),
(
    '10000000-0000-0000-0000-000000000003',
    'support@example.com',
    'YOUR_REAL_SUPPORT_HASH',
    'support_agent',
    TRUE
)
ON CONFLICT (email) DO NOTHING;


-- ============================================================
-- CUSTOMERS
-- ============================================================

INSERT INTO customers (
    id,
    customer_code,
    user_id,
    company_name,
    contact_name,
    region,
    industry,
    account_status,
    subscription_tier,
    sla_level,
    renewal_date
)
VALUES
(
    '20000000-0000-0000-0000-000000000001',
    'C1001',
    '10000000-0000-0000-0000-000000000001',
    'Acme Technologies',
    'Aarav Sharma',
    'Asia-Pacific',
    'Technology',
    'active',
    'Enterprise',
    'Priority',
    '2026-03-01'
),
(
    '20000000-0000-0000-0000-000000000002',
    'C1005',
    '10000000-0000-0000-0000-000000000002',
    'GlobalBank Systems',
    'Priya Nair',
    'Asia-Pacific',
    'Financial Services',
    'active',
    'Premium',
    'Enhanced',
    '2025-11-15'
)
ON CONFLICT (customer_code) DO NOTHING;


-- ============================================================
-- DOCUMENTS
-- ============================================================

INSERT INTO documents (
    id,
    document_name,
    document_type,
    source_url,
    product_name,
    product_version,
    version,
    content_hash,
    metadata
)
VALUES
(
    '50000000-0000-0000-0000-000000000001',
    'API Key Rotation Guide',
    'documentation',
    'https://example.com/docs/api-key-rotation',
    'Enterprise API Platform',
    'v3',
    '3.0',
    'demo-hash-api-key',
    '{"topic": "authentication", "status": "active"}'
),
(
    '50000000-0000-0000-0000-000000000002',
    'Troubleshooting API 404 Errors',
    'troubleshooting',
    'https://example.com/docs/api-404',
    'Enterprise API Platform',
    'v3',
    '3.0',
    'demo-hash-api-404',
    '{"topic": "integration", "status": "active"}'
),
(
    '50000000-0000-0000-0000-000000000003',
    'API Security Incident Response',
    'security',
    'https://example.com/docs/security-incident',
    'Enterprise API Platform',
    'v3',
    '3.0',
    'demo-hash-security',
    '{"topic": "security", "status": "active"}'
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- DOCUMENT CHUNKS
-- ============================================================

INSERT INTO document_chunks (
    id,
    document_id,
    chunk_index,
    content,
    token_count,
    metadata
)
VALUES
(
    '60000000-0000-0000-0000-000000000001',
    '50000000-0000-0000-0000-000000000001',
    0,
    'To rotate an API key, open the API credentials page, create a new key, update dependent applications, verify the new key, and revoke the old key after validation.',
    42,
    '{"section": "rotation_steps", "keywords": ["API key", "rotate", "credentials"]}'
),
(
    '60000000-0000-0000-0000-000000000002',
    '50000000-0000-0000-0000-000000000002',
    0,
    'For HTTP 404 errors, verify the endpoint path, API version, account entitlement, and resource identifier. Confirm that the endpoint is enabled for the customer subscription.',
    44,
    '{"section": "404_troubleshooting", "keywords": ["404", "endpoint", "API version"]}'
),
(
    '60000000-0000-0000-0000-000000000003',
    '50000000-0000-0000-0000-000000000003',
    0,
    'When a deployed API security vulnerability is suspected, preserve evidence, assess production exposure, identify affected customers, and escalate the case for human security review.',
    39,
    '{"section": "incident_response", "keywords": ["security", "vulnerability", "production"]}'
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- INCIDENT LOGS
-- ============================================================

INSERT INTO incident_logs (
    id,
    incident_code,
    title,
    description,
    service_name,
    severity,
    status,
    affected_customers_count,
    affects_production,
    unresolved_critical_alert,
    security_related,
    data_loss_reported,
    started_at,
    metadata
)
VALUES
(
    '70000000-0000-0000-0000-000000000001',
    'INC-2026-001',
    'API Gateway Production Outage',
    'Multiple customers are unable to access production API endpoints.',
    'API Gateway',
    'critical',
    'investigating',
    127,
    TRUE,
    TRUE,
    FALSE,
    FALSE,
    '2026-08-25T10:00:00Z',
    '{"region": "global", "premium_customers_affected": true}'
),
(
    '70000000-0000-0000-0000-000000000002',
    'INC-2026-002',
    'API Security Alert',
    'Potential unauthorized exposure of a deployed API endpoint.',
    'Authentication Service',
    'critical',
    'investigating',
    12,
    TRUE,
    TRUE,
    TRUE,
    FALSE,
    '2026-08-26T09:30:00Z',
    '{"security_team_notified": true}'
)
ON CONFLICT (incident_code) DO NOTHING;


-- ============================================================
-- SUPPORT TICKETS
-- ============================================================

INSERT INTO support_tickets (
    id,
    ticket_number,
    customer_id,
    subject,
    description,
    status,
    intent,
    route,
    severity,
    confidence,
    escalation_required,
    escalation_reason,
    ai_investigation_summary
)
VALUES
(
    '80000000-0000-0000-0000-000000000001',
    'TK-1001',
    '20000000-0000-0000-0000-000000000001',
    'API key rotation',
    'How do I rotate my API key?',
    'resolved',
    'usage',
    'rag',
    'low',
    0.96,
    FALSE,
    NULL,
    'Documentation retrieval provided the documented API key rotation procedure.'
),
(
    '80000000-0000-0000-0000-000000000002',
    'TK-1005',
    '20000000-0000-0000-0000-000000000002',
    'Premium customer API integration failure',
    'Our premium customer API integration is failing. Is it a known issue?',
    'in_progress',
    'integration',
    'hybrid',
    'high',
    0.82,
    FALSE,
    NULL,
    'Documentation was combined with premium subscription validation and current incident checks.'
),
(
    '80000000-0000-0000-0000-000000000003',
    'TK-1008',
    '20000000-0000-0000-0000-000000000002',
    'Production API outage',
    'Production API is down and multiple customers are affected.',
    'open',
    'incident',
    'incident',
    'critical',
    0.61,
    TRUE,
    'Critical production incident with unresolved critical alert and multiple affected customers.',
    'Incident logs show a production outage affecting multiple customers. Human escalation is required.'
)
ON CONFLICT (ticket_number) DO NOTHING;


-- ============================================================
-- TICKET MESSAGES
-- ============================================================

INSERT INTO ticket_messages (
    id,
    ticket_id,
    sender_type,
    sender_user_id,
    message
)
VALUES
(
    '81000000-0000-0000-0000-000000000001',
    '80000000-0000-0000-0000-000000000001',
    'customer',
    '10000000-0000-0000-0000-000000000001',
    'How do I rotate my API key?'
),
(
    '81000000-0000-0000-0000-000000000002',
    '80000000-0000-0000-0000-000000000001',
    'ai',
    NULL,
    'Open the API credentials page, create a new key, update dependent applications, verify the new key, and revoke the old key after validation.'
),
(
    '81000000-0000-0000-0000-000000000003',
    '80000000-0000-0000-0000-000000000003',
    'customer',
    '10000000-0000-0000-0000-000000000002',
    'Production API is down and multiple customers are affected.'
),
(
    '81000000-0000-0000-0000-000000000004',
    '80000000-0000-0000-0000-000000000003',
    'ai',
    NULL,
    'This appears to be a critical production incident. The case has been escalated to human support for investigation.'
)
ON CONFLICT DO NOTHING;


-- ============================================================
-- KNOWLEDGE ARTICLE USAGE (NIIT STRUCTURED REGISTRY)
-- ============================================================

INSERT INTO knowledge_article_usage (
    article_title,
    product_version,
    category,
    last_updated,
    known_issue_flag,
    internal_confidence_score
)
VALUES
(
    'API Authentication Troubleshooting',
    'v3.2',
    'API',
    '2025-02-10',
    FALSE,
    0.94
),
(
    'Resolving High Latency in EU Region',
    'v3.0',
    'Performance',
    '2025-01-25',
    TRUE,
    0.88
),
(
    'Handling Security Alert Notifications',
    'v3.2',
    'Security',
    '2025-02-15',
    FALSE,
    0.97
);


-- ============================================================
-- ESCALATION
-- ============================================================

INSERT INTO escalations (
    id,
    ticket_id,
    status,
    reason,
    severity,
    confidence,
    handoff_package,
    investigation_summary
)
VALUES
(
    '83000000-0000-0000-0000-000000000001',
    '80000000-0000-0000-0000-000000000003',
    'open',
    'Critical production outage affecting multiple customers.',
    'critical',
    0.61,
    '{
        "ticket_number": "TK-1008",
        "customer_code": "C1005",
        "severity": "critical",
        "confidence": 0.61,
        "incident_code": "INC-2026-001",
        "reason": "Production outage with unresolved critical alert"
    }',
    'Production API outage detected. Incident logs indicate a critical unresolved alert affecting multiple customers.'
)
ON CONFLICT (ticket_id) DO NOTHING;