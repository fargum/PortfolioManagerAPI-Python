-- Additional table required by AsyncPostgresSaver for LangGraph checkpoint storage
-- Run this in your PostgreSQL database

CREATE TABLE IF NOT EXISTS public.checkpoint_blobs (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    channel TEXT NOT NULL,
    version TEXT NOT NULL,
    type TEXT NOT NULL,
    blob BYTEA,
    PRIMARY KEY (thread_id, checkpoint_ns, channel, version)
);

-- Grant permissions to your service account
GRANT ALL ON TABLE public.checkpoint_blobs TO "PortfolioAccount";

-- Verify all checkpoint tables exist
SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'checkpoint%';
