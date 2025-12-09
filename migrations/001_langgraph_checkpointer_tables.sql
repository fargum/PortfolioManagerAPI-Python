-- LangGraph PostgresSaver Checkpointer Tables
-- These tables are used by LangGraph's PostgresSaver to store conversation state and memory
-- Run this migration manually against your PostgreSQL database

-- Create checkpoints table for storing conversation state
CREATE TABLE IF NOT EXISTS app.checkpoints (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    parent_checkpoint_id TEXT,
    type TEXT,
    checkpoint JSONB NOT NULL,
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
);

-- Create checkpoint_writes table for pending writes
CREATE TABLE IF NOT EXISTS app.checkpoint_writes (
    thread_id TEXT NOT NULL,
    checkpoint_ns TEXT NOT NULL DEFAULT '',
    checkpoint_id TEXT NOT NULL,
    task_id TEXT NOT NULL,
    idx INTEGER NOT NULL,
    channel TEXT NOT NULL,
    type TEXT,
    value JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id, task_id, idx)
);

-- Add indexes for performance
CREATE INDEX IF NOT EXISTS idx_checkpoints_thread_id 
    ON app.checkpoints(thread_id);

CREATE INDEX IF NOT EXISTS idx_checkpoints_created_at 
    ON app.checkpoints(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_thread_id 
    ON app.checkpoint_writes(thread_id);

CREATE INDEX IF NOT EXISTS idx_checkpoint_writes_checkpoint_id 
    ON app.checkpoint_writes(checkpoint_id);

-- Add comments for documentation
COMMENT ON TABLE app.checkpoints IS 'LangGraph conversation state checkpoints for agent memory persistence';
COMMENT ON TABLE app.checkpoint_writes IS 'LangGraph pending checkpoint writes for agent state management';
COMMENT ON COLUMN app.checkpoints.thread_id IS 'Unique thread identifier in format: account_{account_id}_thread_{thread_id}';
COMMENT ON COLUMN app.checkpoints.checkpoint IS 'JSONB blob containing full conversation state including messages';
COMMENT ON COLUMN app.checkpoints.metadata IS 'Additional metadata about the checkpoint';
