-- ============================================================
-- AUTONOMOUS ORG - SUPABASE SCHEMA
-- Run this in your Supabase SQL Editor (one paste, one click)
-- ============================================================

create extension if not exists "uuid-ossp";

-- ── AGENTS ─────────────────────────────────────────────────
-- Every agent is a row. Add new agents by inserting a row.
-- No code changes needed.
create table if not exists agents (
    id uuid default uuid_generate_v4() primary key,
    name text not null unique,
    role text not null,
    emoji text default '🤖',
    color text default '#6366f1',
    system_prompt text not null,
    tools jsonb default '[]',
    reports_to uuid references agents(id),
    active boolean default true,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- ── TASKS ──────────────────────────────────────────────────
-- The org's work queue. Agents assign tasks to each other.
create table if not exists tasks (
    id uuid default uuid_generate_v4() primary key,
    assigned_to uuid references agents(id),
    assigned_by uuid references agents(id),
    parent_task_id uuid references tasks(id),
    description text not null,
    context text,
    priority integer default 5,
    status text default 'pending'
        check (status in ('pending','in_progress','complete','failed','cancelled')),
    output text,
    retry_count integer default 0,
    last_error text,
    started_at timestamptz,
    completed_at timestamptz,
    created_at timestamptz default now()
);

-- ── MEMORY ─────────────────────────────────────────────────
-- Org-wide persistent memory. Never forgotten.
create table if not exists memory (
    id uuid default uuid_generate_v4() primary key,
    key text not null unique,
    value text not null,
    category text default 'general',
    updated_by uuid references agents(id),
    updated_at timestamptz default now()
);

-- ── DECISIONS ──────────────────────────────────────────────
-- Log of every decision made. Full audit trail.
create table if not exists decisions (
    id uuid default uuid_generate_v4() primary key,
    made_by uuid references agents(id),
    description text not null,
    reasoning text,
    task_id uuid references tasks(id),
    approved_by_human boolean default false,
    needs_approval boolean default false,
    created_at timestamptz default now()
);

-- ── CONVERSATIONS ───────────────────────────────────────────
-- Full chat history between founder and any agent.
create table if not exists conversations (
    id uuid default uuid_generate_v4() primary key,
    session_id text,
    role text check (role in ('user','assistant','system')),
    agent_id uuid references agents(id),
    content text not null,
    created_at timestamptz default now()
);

-- ── PRODUCTS ───────────────────────────────────────────────
-- SaaS products being built/maintained.
create table if not exists products (
    id uuid default uuid_generate_v4() primary key,
    name text not null,
    status text default 'ideation'
        check (status in ('ideation','planning','building','testing','live','paused')),
    description text,
    target_user text,
    repo_url text,
    live_url text,
    mrr numeric default 0,
    user_count integer default 0,
    stripe_product_id text,
    created_at timestamptz default now(),
    updated_at timestamptz default now()
);

-- ── INTEGRATIONS ───────────────────────────────────────────
-- Every tool the org has connected to itself.
create table if not exists integrations (
    id uuid default uuid_generate_v4() primary key,
    name text not null unique,
    type text not null,
    status text default 'active'
        check (status in ('active','inactive','error')),
    config jsonb default '{}',
    added_by uuid references agents(id),
    notes text,
    created_at timestamptz default now()
);

-- ── ERROR LOG ──────────────────────────────────────────────
-- Self-healing audit trail.
create table if not exists error_log (
    id uuid default uuid_generate_v4() primary key,
    task_id uuid references tasks(id),
    agent_id uuid references agents(id),
    error text not null,
    attempt integer default 1,
    resolved boolean default false,
    resolution text,
    timestamp timestamptz default now()
);

-- ── METRICS ────────────────────────────────────────────────
-- Daily org health snapshot.
create table if not exists metrics (
    id uuid default uuid_generate_v4() primary key,
    date date default current_date,
    mrr numeric default 0,
    new_signups integer default 0,
    churn integer default 0,
    support_tickets integer default 0,
    tasks_completed integer default 0,
    tasks_failed integer default 0,
    recorded_at timestamptz default now()
);

-- ── ROW LEVEL SECURITY ─────────────────────────────────────
alter table agents enable row level security;
alter table tasks enable row level security;
alter table memory enable row level security;
alter table decisions enable row level security;
alter table conversations enable row level security;
alter table products enable row level security;
alter table integrations enable row level security;
alter table error_log enable row level security;
alter table metrics enable row level security;

-- Allow full access via service role key (used by orchestrator)
create policy "service_all" on agents for all using (true);
create policy "service_all" on tasks for all using (true);
create policy "service_all" on memory for all using (true);
create policy "service_all" on decisions for all using (true);
create policy "service_all" on conversations for all using (true);
create policy "service_all" on products for all using (true);
create policy "service_all" on integrations for all using (true);
create policy "service_all" on error_log for all using (true);
create policy "service_all" on metrics for all using (true);

-- ── INDEXES ────────────────────────────────────────────────
create index if not exists idx_tasks_status on tasks(status);
create index if not exists idx_tasks_assigned_to on tasks(assigned_to);
create index if not exists idx_tasks_created_at on tasks(created_at);
create index if not exists idx_conversations_session on conversations(session_id);
create index if not exists idx_memory_key on memory(key);
create index if not exists idx_memory_category on memory(category);
