CREATE TABLE IF NOT EXISTS market_ticks (
  id BIGSERIAL PRIMARY KEY,
  ticker VARCHAR(16) NOT NULL,
  ts TIMESTAMPTZ NOT NULL,
  price NUMERIC(18,6) NOT NULL,
  bid NUMERIC(18,6),
  ask NUMERIC(18,6),
  volume BIGINT
);

CREATE TABLE IF NOT EXISTS bars_1m (
  id BIGSERIAL PRIMARY KEY,
  ticker VARCHAR(16) NOT NULL,
  ts TIMESTAMPTZ NOT NULL,
  open NUMERIC(18,6), high NUMERIC(18,6), low NUMERIC(18,6), close NUMERIC(18,6), volume BIGINT
);
CREATE TABLE IF NOT EXISTS bars_5m (LIKE bars_1m INCLUDING ALL);
CREATE TABLE IF NOT EXISTS bars_15m (LIKE bars_1m INCLUDING ALL);
CREATE TABLE IF NOT EXISTS bars_1h (LIKE bars_1m INCLUDING ALL);
CREATE TABLE IF NOT EXISTS bars_1d (LIKE bars_1m INCLUDING ALL);

CREATE TABLE IF NOT EXISTS watchlists (
  id BIGSERIAL PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  ticker VARCHAR(16) NOT NULL,
  position INT NOT NULL DEFAULT 0,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS indicators (
  id BIGSERIAL PRIMARY KEY,
  ticker VARCHAR(16) NOT NULL,
  timeframe VARCHAR(8) NOT NULL,
  ts TIMESTAMPTZ NOT NULL,
  values JSONB NOT NULL
);

CREATE TABLE IF NOT EXISTS feature_snapshots (
  id BIGSERIAL PRIMARY KEY,
  ticker VARCHAR(16) NOT NULL,
  ts TIMESTAMPTZ NOT NULL,
  features JSONB NOT NULL,
  regime VARCHAR(32)
);

CREATE TABLE IF NOT EXISTS signal_outputs (
  id BIGSERIAL PRIMARY KEY,
  ticker VARCHAR(16) NOT NULL,
  action VARCHAR(16) NOT NULL,
  confidence NUMERIC(8,4) NOT NULL,
  consensus_score NUMERIC(8,4),
  disagreement_score NUMERIC(8,4),
  reason_codes JSONB,
  explanation TEXT,
  execution_eligibility JSONB,
  model_version VARCHAR(64),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS mirofish_predictions (
  id BIGSERIAL PRIMARY KEY,
  ticker VARCHAR(16) NOT NULL,
  payload JSONB NOT NULL,
  directional_bias VARCHAR(16),
  confidence NUMERIC(8,4),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS swarm_tasks (
  id BIGSERIAL PRIMARY KEY,
  task_id VARCHAR(128) UNIQUE NOT NULL,
  ticker VARCHAR(16) NOT NULL,
  mode VARCHAR(16) NOT NULL,
  status VARCHAR(16) NOT NULL,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS swarm_agent_runs (
  id BIGSERIAL PRIMARY KEY,
  task_id VARCHAR(128) NOT NULL,
  agent_name VARCHAR(64) NOT NULL,
  recommendation VARCHAR(16),
  confidence NUMERIC(8,4),
  latency_ms INT,
  output JSONB
);

CREATE TABLE IF NOT EXISTS swarm_shared_memory (
  id BIGSERIAL PRIMARY KEY,
  namespace VARCHAR(64) NOT NULL,
  key VARCHAR(128) NOT NULL,
  value JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS swarm_consensus_outputs (
  id BIGSERIAL PRIMARY KEY,
  task_id VARCHAR(128) NOT NULL,
  ticker VARCHAR(16) NOT NULL,
  aggregated_recommendation VARCHAR(16),
  consensus_score NUMERIC(8,4),
  disagreement_score NUMERIC(8,4),
  explanation TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS execution_modes (
  id BIGSERIAL PRIMARY KEY,
  mode VARCHAR(16) NOT NULL,
  live_enabled BOOLEAN NOT NULL DEFAULT FALSE,
  changed_by VARCHAR(64),
  changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS broker_accounts (
  id BIGSERIAL PRIMARY KEY,
  provider VARCHAR(32) NOT NULL,
  environment VARCHAR(16) NOT NULL,
  account_ref VARCHAR(128),
  encrypted_credentials BYTEA,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS risk_policies (
  id BIGSERIAL PRIMARY KEY,
  profile_name VARCHAR(64) UNIQUE NOT NULL,
  hard_constraints JSONB NOT NULL,
  soft_constraints JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS capital_profiles (
  id BIGSERIAL PRIMARY KEY,
  profile_name VARCHAR(64) UNIQUE NOT NULL,
  starting_capital NUMERIC(18,2) NOT NULL,
  current_capital NUMERIC(18,2) NOT NULL,
  currency VARCHAR(8) DEFAULT 'USD'
);

CREATE TABLE IF NOT EXISTS position_sizing_rules (
  id BIGSERIAL PRIMARY KEY,
  setup_type VARCHAR(64) NOT NULL,
  regime VARCHAR(32),
  params JSONB NOT NULL,
  is_hard_ceiling BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE TABLE IF NOT EXISTS stop_loss_profiles (
  id BIGSERIAL PRIMARY KEY,
  setup_type VARCHAR(64) NOT NULL,
  params JSONB NOT NULL,
  hard_min_pct NUMERIC(8,4),
  hard_max_pct NUMERIC(8,4)
);

CREATE TABLE IF NOT EXISTS paper_orders (
  id BIGSERIAL PRIMARY KEY,
  broker_order_id VARCHAR(128),
  ticker VARCHAR(16) NOT NULL,
  side VARCHAR(8) NOT NULL,
  qty NUMERIC(18,6),
  order_type VARCHAR(16),
  status VARCHAR(32),
  rationale JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS paper_fills (
  id BIGSERIAL PRIMARY KEY,
  paper_order_id BIGINT REFERENCES paper_orders(id),
  fill_price NUMERIC(18,6),
  fill_qty NUMERIC(18,6),
  filled_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS live_orders (LIKE paper_orders INCLUDING ALL);
CREATE TABLE IF NOT EXISTS live_fills (LIKE paper_fills INCLUDING ALL);

CREATE TABLE IF NOT EXISTS trade_journal (
  id BIGSERIAL PRIMARY KEY,
  ticker VARCHAR(16) NOT NULL,
  mode VARCHAR(16) NOT NULL,
  recommendation JSONB,
  execution JSONB,
  outcome JSONB,
  tags JSONB,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS daily_model_evaluations (
  id BIGSERIAL PRIMARY KEY,
  eval_date DATE NOT NULL,
  metrics JSONB NOT NULL,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS agent_performance_stats (
  id BIGSERIAL PRIMARY KEY,
  agent_name VARCHAR(64) NOT NULL,
  setup_type VARCHAR(64),
  regime VARCHAR(32),
  reliability_score NUMERIC(8,4),
  stats JSONB,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS model_versions (
  id BIGSERIAL PRIMARY KEY,
  model_name VARCHAR(64) NOT NULL,
  version VARCHAR(32) NOT NULL,
  artifact_uri TEXT,
  metrics JSONB,
  is_active BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_configs (
  id BIGSERIAL PRIMARY KEY,
  user_id VARCHAR(64),
  name VARCHAR(128) NOT NULL,
  config JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGSERIAL PRIMARY KEY,
  event_type VARCHAR(64) NOT NULL,
  actor VARCHAR(64),
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
