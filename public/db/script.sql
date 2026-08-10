-- Create users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL,
    name TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Create chat_sessions table
CREATE TABLE chat_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    title TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Create chat_messages table
CREATE TABLE chat_messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id UUID NOT NULL,
    content TEXT,
    role TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id)
);

-- Add indexes to improve query performance
CREATE INDEX idx_chat_sessions_user_id ON chat_sessions(user_id);
CREATE INDEX idx_chat_messages_session_id ON chat_messages(session_id);

-- Add unique constraint to prevent duplicate emails
ALTER TABLE users ADD CONSTRAINT unique_email UNIQUE (email);

-- Enable pgvector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- Create analysis_learnings table
CREATE TABLE analysis_learnings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL,
    indicator TEXT NOT NULL,
    value_range TEXT,
    condition TEXT,
    outcome TEXT NOT NULL,
    patient_demographics JSONB,
    confidence FLOAT DEFAULT 0.6,
    usage_count INTEGER DEFAULT 1,
    is_archived BOOLEAN DEFAULT FALSE,
    embedding vector(384),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- Indexes for analysis_learnings
CREATE INDEX idx_analysis_learnings_user_id 
    ON analysis_learnings(user_id);
CREATE INDEX idx_analysis_learnings_indicator 
    ON analysis_learnings(indicator);
CREATE INDEX idx_analysis_learnings_condition 
    ON analysis_learnings(condition);
CREATE INDEX idx_analysis_learnings_archived 
    ON analysis_learnings(is_archived);

-- HNSW index for similarity search
CREATE INDEX idx_analysis_learnings_embedding ON analysis_learnings USING hnsw (embedding vector_cosine_ops);

-- RPC for semantic similarity search
CREATE OR REPLACE FUNCTION match_analysis_learnings(
    query_embedding vector(384),
    match_user_id UUID,
    match_threshold float,
    match_count int
)
RETURNS TABLE (
    id UUID,
    indicator TEXT,
    condition TEXT,
    outcome TEXT,
    confidence FLOAT,
    usage_count INTEGER,
    similarity float
)
LANGUAGE sql STABLE
AS $$
    SELECT
        id,
        indicator,
        condition,
        outcome,
        confidence,
        usage_count,
        1 - (analysis_learnings.embedding <=> query_embedding) AS similarity
    FROM analysis_learnings
    WHERE user_id = match_user_id
      AND is_archived = false
      AND 1 - (analysis_learnings.embedding <=> query_embedding) > match_threshold
    ORDER BY (analysis_learnings.embedding <=> query_embedding) ASC, confidence DESC, usage_count DESC
    LIMIT match_count;
$$;