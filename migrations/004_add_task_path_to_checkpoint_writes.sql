-- Add task_path column to checkpoint_writes table for AsyncPostgresSaver
-- This column is required by langgraph-checkpoint-postgres 2.0.8+

ALTER TABLE public.checkpoint_writes 
ADD COLUMN IF NOT EXISTS task_path TEXT;

-- Grant permissions
GRANT ALL ON TABLE public.checkpoint_writes TO "PortfolioAccount";
