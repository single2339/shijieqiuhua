-- Reference DDL (PostgreSQL-flavored); adjust types for your lakehouse engine.
-- Partitioning and retention policies are environment-specific.

CREATE TABLE IF NOT EXISTS bronze_raw_document (
  raw_document_id UUID PRIMARY KEY,
  job_id UUID NOT NULL,
  channel TEXT NOT NULL CHECK (channel IN ('web', 'social', 'api', 'app')),
  mime_type TEXT NOT NULL,
  encoding TEXT DEFAULT 'utf-8',
  body_ref TEXT,
  body_inline TEXT,
  headers_summary JSONB,
  captured_at TIMESTAMPTZ NOT NULL,
  ingested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  collector_id TEXT NOT NULL,
  collector_version TEXT NOT NULL,
  source_url TEXT,
  source_system TEXT NOT NULL,
  content_sha256 CHAR(64) NOT NULL,
  classification TEXT,
  extensions JSONB,
  tenant_id TEXT NOT NULL,
  partition_date DATE GENERATED ALWAYS AS ((timezone('UTC', captured_at))::date) STORED,
  CONSTRAINT bronze_body_chk CHECK (body_ref IS NOT NULL OR body_inline IS NOT NULL)
);

CREATE TABLE IF NOT EXISTS silver_document (
  silver_document_id UUID PRIMARY KEY,
  canonical_text TEXT NOT NULL,
  language TEXT,
  published_at TIMESTAMPTZ,
  title TEXT,
  raw_document_ids UUID[] NOT NULL,
  dedupe_fingerprint TEXT,
  pii_flags TEXT[],
  tenant_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS silver_entity (
  entity_id UUID PRIMARY KEY,
  entity_type TEXT NOT NULL,
  canonical_name TEXT NOT NULL,
  aliases TEXT[],
  external_ids JSONB,
  confidence DOUBLE PRECISION,
  merged_from UUID[],
  tenant_id TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS silver_event (
  event_id UUID PRIMARY KEY,
  event_type TEXT NOT NULL,
  event_time TIMESTAMPTZ NOT NULL,
  location_entity_id UUID REFERENCES silver_entity (entity_id),
  participant_entity_ids UUID[],
  source_silver_document_ids UUID[] NOT NULL,
  tenant_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold_claim (
  claim_id UUID PRIMARY KEY,
  statement TEXT NOT NULL,
  silver_document_id UUID NOT NULL REFERENCES silver_document (silver_document_id),
  evidence_span JSONB,
  verification_status TEXT NOT NULL,
  confidence DOUBLE PRECISION,
  supporting_silver_document_ids UUID[],
  tenant_id TEXT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS gold_economic_indicator_snapshot (
  snapshot_id UUID PRIMARY KEY,
  indicator_key TEXT NOT NULL,
  observed_at TIMESTAMPTZ NOT NULL,
  value NUMERIC NOT NULL,
  unit TEXT,
  entity_refs UUID[],
  source_silver_document_ids UUID[],
  tenant_id TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_bronze_captured ON bronze_raw_document (partition_date, source_system);
CREATE INDEX IF NOT EXISTS idx_silver_dedupe ON silver_document (tenant_id, dedupe_fingerprint);
CREATE INDEX IF NOT EXISTS idx_gold_claim_doc ON gold_claim (silver_document_id);
