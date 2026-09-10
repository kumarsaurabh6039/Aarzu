-- =========================================
-- AARZU DATABASE SCHEMA
-- Run this in Supabase SQL Editor
-- =========================================

create extension if not exists vector;
create extension if not exists pgcrypto;

-- =========================================
-- PROFILE (single user, but kept generic)
-- =========================================

create table if not exists profiles (
    id uuid primary key default gen_random_uuid(),
    name text,
    personality_preferences jsonb default '{}'::jsonb,
    goals jsonb default '[]'::jsonb,
    preferences jsonb default '{}'::jsonb,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- =========================================
-- MEMORY (the heart of Aarzu)
-- NOTE: vector(768) because we use Gemini's
-- text-embedding-004 model, NOT OpenAI's 1536-dim model.
-- =========================================

create table if not exists memories (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    content text not null,
    memory_type text not null default 'general',
    importance integer default 5 check (importance between 1 and 10),
    embedding vector(768),
    metadata jsonb default '{}'::jsonb,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

create index if not exists memories_user_id_idx on memories(user_id);

-- =========================================
-- CONVERSATIONS
-- speaker_name is null for the owner (Saurabh) and set to the
-- guest's name (or "Unknown guest") for anyone else chatting.
-- =========================================

create table if not exists conversations (
    id uuid primary key default gen_random_uuid(),
    user_id uuid not null,
    title text,
    speaker_name text,
    is_owner boolean not null default true,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- If you already ran this schema before, run these two lines once
-- to add the new columns without losing existing data:
-- alter table conversations add column if not exists speaker_name text;
-- alter table conversations add column if not exists is_owner boolean not null default true;

create index if not exists conversations_user_id_idx on conversations(user_id);

-- =========================================
-- MESSAGES
-- =========================================

create table if not exists messages (
    id uuid primary key default gen_random_uuid(),
    conversation_id uuid not null references conversations(id) on delete cascade,
    role text not null check (role in ('user', 'assistant', 'system')),
    content text not null,
    created_at timestamptz default now()
);

create index if not exists messages_conversation_id_idx on messages(conversation_id);

-- =========================================
-- VECTOR SEARCH FUNCTION
-- =========================================

create or replace function match_memories(
    query_embedding vector(768),
    match_user_id uuid,
    match_threshold float default 0.65,
    match_count int default 5
)
returns table (
    id uuid,
    content text,
    memory_type text,
    importance int,
    similarity float
)
language sql
stable
as $$
    select
        memories.id,
        memories.content,
        memories.memory_type,
        memories.importance,
        1 - (memories.embedding <=> query_embedding) as similarity
    from memories
    where memories.user_id = match_user_id
      and 1 - (memories.embedding <=> query_embedding) >= match_threshold
    order by memories.embedding <=> query_embedding
    limit match_count;
$$;

-- =========================================
-- SEED: create your single user profile
-- Copy the returned id — you'll use it as
-- your fixed USER_ID in the backend .env
-- =========================================

insert into profiles (name) values ('Saurabh') returning id;

-- =========================================
-- GUEST MESSAGE SEMANTIC SEARCH
-- Lets Saurabh ask things like "Rahul ne kya bola tha?"
-- and get a real semantic match, not just recency.
-- Safe to re-run: only adds things if missing.
-- =========================================

alter table messages
add column if not exists embedding vector(768);

create index if not exists messages_embedding_idx
on messages
using ivfflat (embedding vector_cosine_ops)
with (lists = 100);

create or replace function match_guest_messages(
    query_embedding vector(768),
    match_user_id uuid,
    match_threshold float default 0.55,
    match_count int default 8
)
returns table (
    id uuid,
    conversation_id uuid,
    speaker_name text,
    content text,
    created_at timestamptz,
    similarity float
)
language sql
stable
as $$
    select
        m.id,
        m.conversation_id,
        c.speaker_name,
        m.content,
        m.created_at,
        1 - (m.embedding <=> query_embedding) as similarity
    from messages m
    join conversations c
        on c.id = m.conversation_id
    where c.user_id = match_user_id
      and c.is_owner = false
      and m.role = 'user'
      and m.embedding is not null
      and 1 - (m.embedding <=> query_embedding) >= match_threshold
    order by m.embedding <=> query_embedding
    limit match_count;
$$;
