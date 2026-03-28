-- Migration 007: Real-time metrics and carrier performance scoring
-- Date: 2026-03-28
-- Purpose: Track computed business metrics and carrier reliability scores

-- Cached metrics per user (recomputed after each reconciliation)
CREATE TABLE IF NOT EXISTS user_metrics (
  user_id UUID REFERENCES users(id) ON DELETE CASCADE PRIMARY KEY,
  policy_retention_rate NUMERIC(5,2),
  commission_recovery_rate NUMERIC(5,2),
  avg_days_to_payment NUMERIC(5,1),
  discrepancy_rate NUMERIC(5,2),
  book_growth_rate NUMERIC(5,2),
  total_policies INTEGER DEFAULT 0,
  total_premium NUMERIC(12,2) DEFAULT 0,
  total_expected_commission NUMERIC(12,2) DEFAULT 0,
  total_received_commission NUMERIC(12,2) DEFAULT 0,
  total_outstanding NUMERIC(12,2) DEFAULT 0,
  computed_at TIMESTAMPTZ DEFAULT now()
);

-- Carrier performance scores per user
CREATE TABLE IF NOT EXISTS carrier_scores (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  carrier_name TEXT NOT NULL,
  accuracy_score NUMERIC(5,2),
  timeliness_score NUMERIC(5,2),
  dispute_rate NUMERIC(5,2),
  overall_score NUMERIC(5,2),
  statement_count INTEGER DEFAULT 0,
  total_commission NUMERIC(12,2) DEFAULT 0,
  computed_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, carrier_name)
);

-- Weekly metric snapshots for trend charts
CREATE TABLE IF NOT EXISTS metric_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  snapshot_date DATE NOT NULL,
  policy_retention_rate NUMERIC(5,2),
  commission_recovery_rate NUMERIC(5,2),
  total_policies INTEGER,
  total_premium NUMERIC(12,2),
  total_outstanding NUMERIC(12,2),
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, snapshot_date)
);

-- Alerts for proactive notifications
CREATE TABLE IF NOT EXISTS alerts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  alert_type TEXT NOT NULL,
  title TEXT NOT NULL,
  body TEXT,
  severity TEXT DEFAULT 'info',
  is_read BOOLEAN DEFAULT false,
  action_url TEXT,
  created_at TIMESTAMPTZ DEFAULT now()
);

-- Enable RLS
ALTER TABLE user_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE carrier_scores ENABLE ROW LEVEL SECURITY;
ALTER TABLE metric_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;

-- Users see own data
CREATE POLICY "Users view own metrics" ON user_metrics FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users view own carrier scores" ON carrier_scores FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users view own snapshots" ON metric_snapshots FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users view own alerts" ON alerts FOR SELECT USING (user_id = auth.uid());
CREATE POLICY "Users update own alerts" ON alerts FOR UPDATE USING (user_id = auth.uid());

-- Service role full access
CREATE POLICY "Service manage metrics" ON user_metrics FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service manage carrier scores" ON carrier_scores FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service manage snapshots" ON metric_snapshots FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Service manage alerts" ON alerts FOR ALL USING (true) WITH CHECK (true);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_carrier_scores_user ON carrier_scores (user_id);
CREATE INDEX IF NOT EXISTS idx_metric_snapshots_user ON metric_snapshots (user_id, snapshot_date DESC);
CREATE INDEX IF NOT EXISTS idx_alerts_user_unread ON alerts (user_id, is_read, created_at DESC);
