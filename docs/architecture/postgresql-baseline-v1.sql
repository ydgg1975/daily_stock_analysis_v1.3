-- WolfyStock PostgreSQL baseline v1
-- Design-phase artifact only.
-- This file is not wired into runtime and does not perform migration.
-- Historical OHLCV / benchmark bodies remain in Parquet or NAS.
-- See also:
--   - docs/architecture/postgresql-baseline-design.md
--   - docs/architecture/postgresql-baseline-plan.md

create table if not exists app_users (
    id text primary key,
    username text not null unique,
    display_name text,
    role text not null check (role in ('user', 'admin')),
    is_active boolean not null default true,
    password_hash text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists app_user_sessions (
    session_id text primary key,
    user_id text not null references app_users(id),
    created_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    expires_at timestamptz not null,
    revoked_at timestamptz
);

create index if not exists idx_app_user_sessions_user_expiry
    on app_user_sessions (user_id, expires_at desc);

create table if not exists guest_sessions (
    session_id text primary key,
    session_kind text not null default 'anonymous_preview',
    status text not null default 'active' check (status in ('active', 'expired', 'revoked')),
    started_at timestamptz not null default now(),
    last_seen_at timestamptz not null default now(),
    expires_at timestamptz not null,
    origin_json jsonb not null default '{}'::jsonb,
    transient_state_json jsonb not null default '{}'::jsonb
);

create table if not exists user_preferences (
    user_id text primary key references app_users(id),
    ui_locale text,
    report_language text,
    market_color_convention text,
    ui_preferences_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists notification_targets (
    id bigserial primary key,
    user_id text not null references app_users(id),
    channel_type text not null check (channel_type in ('email', 'discord', 'telegram', 'webhook', 'wechat', 'feishu')),
    target_value text not null,
    target_secret_json jsonb not null default '{}'::jsonb,
    is_default boolean not null default false,
    is_enabled boolean not null default true,
    delivery_metadata_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (user_id, channel_type, target_value)
);

create index if not exists idx_notification_targets_user_channel
    on notification_targets (user_id, channel_type, is_enabled);

create table if not exists analysis_sessions (
    id bigserial primary key,
    owner_user_id text references app_users(id),
    guest_session_id text references guest_sessions(session_id),
    session_kind text not null default 'analysis' check (session_kind in ('analysis', 'guest_preview', 'assistant_workspace')),
    source_channel text,
    current_symbol text,
    current_query text,
    status text not null default 'active' check (status in ('active', 'archived', 'expired')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    expires_at timestamptz,
    check (num_nonnulls(owner_user_id, guest_session_id) = 1)
);

create index if not exists idx_analysis_sessions_user_updated
    on analysis_sessions (owner_user_id, updated_at desc);

create table if not exists analysis_records (
    id bigserial primary key,
    analysis_session_id bigint not null references analysis_sessions(id),
    sequence_no integer not null,
    legacy_analysis_history_id bigint unique,
    query_id text,
    canonical_symbol text not null,
    display_name text,
    report_type text not null,
    preview_scope text not null default 'user' check (preview_scope in ('user', 'guest')),
    sentiment_score integer,
    operation_advice text,
    trend_prediction text,
    summary_text text,
    report_payload jsonb not null default '{}'::jsonb,
    context_snapshot jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (analysis_session_id, sequence_no)
);

create index if not exists idx_analysis_records_symbol_created
    on analysis_records (canonical_symbol, created_at desc);

create table if not exists chat_sessions (
    id bigserial primary key,
    session_key text not null unique,
    owner_user_id text references app_users(id),
    guest_session_id text references guest_sessions(session_id),
    linked_analysis_session_id bigint references analysis_sessions(id),
    title text,
    status text not null default 'active' check (status in ('active', 'archived', 'expired')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    expires_at timestamptz,
    check (num_nonnulls(owner_user_id, guest_session_id) = 1)
);

create index if not exists idx_chat_sessions_user_updated
    on chat_sessions (owner_user_id, updated_at desc);

create table if not exists chat_messages (
    id bigserial primary key,
    chat_session_id bigint not null references chat_sessions(id),
    message_index integer not null,
    role text not null check (role in ('system', 'user', 'assistant', 'tool')),
    content_text text,
    content_json jsonb not null default '{}'::jsonb,
    token_usage_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (chat_session_id, message_index)
);

create index if not exists idx_chat_messages_session_created
    on chat_messages (chat_session_id, created_at asc);

create table if not exists scanner_runs (
    id bigserial primary key,
    owner_user_id text references app_users(id),
    scope text not null check (scope in ('user', 'system')),
    market text not null,
    profile_key text not null,
    universe_name text not null,
    trigger_mode text not null check (trigger_mode in ('manual', 'scheduled', 'cli', 'api', 'scheduler')),
    request_source text,
    status text not null,
    headline text,
    shortlist_size integer not null default 0,
    universe_size integer not null default 0,
    preselected_size integer not null default 0,
    evaluated_size integer not null default 0,
    source_summary text,
    summary_json jsonb not null default '{}'::jsonb,
    diagnostics_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    completed_at timestamptz,
    check (
        (scope = 'system' and owner_user_id is null)
        or (scope = 'user' and owner_user_id is not null)
    )
);

create index if not exists idx_scanner_runs_scope_created
    on scanner_runs (scope, market, profile_key, created_at desc);

create table if not exists scanner_candidates (
    id bigserial primary key,
    scanner_run_id bigint not null references scanner_runs(id),
    canonical_symbol text not null,
    display_name text,
    rank integer not null,
    score numeric(18, 6) not null,
    quality_hint text,
    reason_summary text,
    candidate_payload jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (scanner_run_id, rank),
    unique (scanner_run_id, canonical_symbol)
);

create index if not exists idx_scanner_candidates_symbol_created
    on scanner_candidates (canonical_symbol, created_at desc);

create table if not exists watchlists (
    id bigserial primary key,
    owner_user_id text references app_users(id),
    scope text not null check (scope in ('user', 'system')),
    market text not null,
    profile_key text not null,
    watchlist_date date not null,
    source_scanner_run_id bigint references scanner_runs(id),
    status text not null default 'active' check (status in ('active', 'archived', 'empty', 'failed')),
    headline text,
    notification_status text,
    notification_summary jsonb not null default '{}'::jsonb,
    comparison_summary jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (
        (scope = 'system' and owner_user_id is null)
        or (scope = 'user' and owner_user_id is not null)
    )
);

create index if not exists idx_watchlists_scope_date
    on watchlists (scope, market, profile_key, watchlist_date desc);

create table if not exists watchlist_items (
    id bigserial primary key,
    watchlist_id bigint not null references watchlists(id),
    source_scanner_candidate_id bigint references scanner_candidates(id),
    canonical_symbol text not null,
    display_name text,
    rank integer not null,
    score numeric(18, 6),
    selection_reason text,
    watch_context jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (watchlist_id, rank),
    unique (watchlist_id, canonical_symbol)
);

create table if not exists backtest_runs (
    id bigserial primary key,
    owner_user_id text not null references app_users(id),
    run_type text not null check (run_type in ('analysis_eval', 'rule_deterministic')),
    linked_analysis_session_id bigint references analysis_sessions(id),
    linked_analysis_record_id bigint references analysis_records(id),
    canonical_symbol text,
    strategy_family text,
    strategy_hash text,
    status text not null,
    request_payload jsonb not null default '{}'::jsonb,
    metrics_json jsonb not null default '{}'::jsonb,
    parsed_strategy_json jsonb not null default '{}'::jsonb,
    started_at timestamptz not null default now(),
    completed_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_backtest_runs_user_created
    on backtest_runs (owner_user_id, created_at desc);

create table if not exists backtest_artifacts (
    id bigserial primary key,
    backtest_run_id bigint not null references backtest_runs(id),
    artifact_kind text not null check (
        artifact_kind in (
            'summary',
            'evaluation_rows',
            'trade_events',
            'audit_rows',
            'execution_trace',
            'comparison',
            'equity_curve',
            'export_index'
        )
    ),
    storage_mode text not null default 'inline_json' check (storage_mode in ('inline_json', 'external_file_ref')),
    payload_json jsonb not null default '{}'::jsonb,
    file_ref_uri text,
    content_hash text,
    created_at timestamptz not null default now(),
    unique (backtest_run_id, artifact_kind)
);

create table if not exists portfolio_accounts (
    id bigserial primary key,
    owner_user_id text not null references app_users(id),
    name text not null,
    broker_label text,
    market text not null,
    base_currency text not null,
    is_active boolean not null default true,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_portfolio_accounts_user_active
    on portfolio_accounts (owner_user_id, is_active);

create table if not exists broker_connections (
    id bigserial primary key,
    owner_user_id text not null references app_users(id),
    portfolio_account_id bigint not null references portfolio_accounts(id),
    broker_type text not null,
    broker_name text,
    connection_name text not null,
    broker_account_ref text,
    import_mode text not null,
    status text not null,
    last_imported_at timestamptz,
    last_import_source text,
    last_import_fingerprint text,
    sync_metadata jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (owner_user_id, broker_type, broker_account_ref)
);

create table if not exists portfolio_ledger (
    id bigserial primary key,
    owner_user_id text not null references app_users(id),
    portfolio_account_id bigint not null references portfolio_accounts(id),
    entry_type text not null check (entry_type in ('trade', 'cash', 'corporate_action', 'adjustment')),
    event_time timestamptz not null,
    canonical_symbol text,
    market text,
    currency text,
    direction text,
    quantity numeric(24, 8),
    price numeric(24, 8),
    amount numeric(24, 8),
    fee numeric(24, 8),
    tax numeric(24, 8),
    corporate_action_type text,
    external_ref text,
    dedup_hash text,
    note text,
    payload_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (portfolio_account_id, external_ref),
    unique (portfolio_account_id, dedup_hash)
);

create index if not exists idx_portfolio_ledger_account_event
    on portfolio_ledger (portfolio_account_id, event_time asc);

create table if not exists portfolio_positions (
    id bigserial primary key,
    owner_user_id text not null references app_users(id),
    portfolio_account_id bigint not null references portfolio_accounts(id),
    source_kind text not null check (source_kind in ('replayed_ledger', 'broker_sync_overlay')),
    cost_method text not null,
    canonical_symbol text not null,
    market text not null,
    currency text not null,
    quantity numeric(24, 8) not null default 0,
    avg_cost numeric(24, 8) not null default 0,
    total_cost numeric(24, 8) not null default 0,
    last_price numeric(24, 8),
    market_value_base numeric(24, 8),
    unrealized_pnl_base numeric(24, 8),
    valuation_currency text,
    as_of_time timestamptz not null,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (portfolio_account_id, source_kind, cost_method, canonical_symbol, market, currency)
);

create table if not exists portfolio_sync_states (
    id bigserial primary key,
    owner_user_id text not null references app_users(id),
    broker_connection_id bigint not null references broker_connections(id),
    portfolio_account_id bigint not null references portfolio_accounts(id),
    broker_type text not null,
    broker_account_ref text,
    sync_source text not null,
    sync_status text not null,
    snapshot_date date not null,
    synced_at timestamptz not null,
    base_currency text not null,
    total_cash numeric(24, 8) not null default 0,
    total_market_value numeric(24, 8) not null default 0,
    total_equity numeric(24, 8) not null default 0,
    realized_pnl numeric(24, 8) not null default 0,
    unrealized_pnl numeric(24, 8) not null default 0,
    fx_stale boolean not null default false,
    payload_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (broker_connection_id)
);

create table if not exists portfolio_sync_positions (
    id bigserial primary key,
    portfolio_sync_state_id bigint not null references portfolio_sync_states(id) on delete cascade,
    owner_user_id text not null references app_users(id),
    portfolio_account_id bigint not null references portfolio_accounts(id),
    broker_position_ref text,
    canonical_symbol text not null,
    market text not null,
    currency text not null,
    quantity numeric(24, 8) not null default 0,
    avg_cost numeric(24, 8) not null default 0,
    last_price numeric(24, 8) not null default 0,
    market_value_base numeric(24, 8) not null default 0,
    unrealized_pnl_base numeric(24, 8) not null default 0,
    valuation_currency text,
    payload_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (portfolio_sync_state_id, canonical_symbol, market, currency)
);

create table if not exists portfolio_sync_cash_balances (
    id bigserial primary key,
    portfolio_sync_state_id bigint not null references portfolio_sync_states(id) on delete cascade,
    owner_user_id text not null references app_users(id),
    portfolio_account_id bigint not null references portfolio_accounts(id),
    currency text not null,
    amount numeric(24, 8) not null default 0,
    amount_base numeric(24, 8) not null default 0,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    unique (portfolio_sync_state_id, currency)
);

create table if not exists provider_configs (
    id bigserial primary key,
    provider_key text not null unique,
    config_scope text not null default 'system' check (config_scope in ('system')),
    auth_mode text not null,
    is_enabled boolean not null default true,
    config_json jsonb not null default '{}'::jsonb,
    secret_json jsonb not null default '{}'::jsonb,
    rotation_version integer not null default 1,
    updated_by_user_id text references app_users(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists system_configs (
    id bigserial primary key,
    config_key text not null unique,
    config_scope text not null default 'system' check (config_scope in ('system')),
    value_type text not null,
    value_json jsonb not null default '{}'::jsonb,
    updated_by_user_id text references app_users(id),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists execution_sessions (
    id bigserial primary key,
    session_id text not null unique,
    owner_user_id text references app_users(id),
    actor_user_id text references app_users(id),
    actor_role text,
    session_kind text not null check (session_kind in ('user_activity', 'admin_action', 'system_task')),
    subsystem text not null,
    action_name text,
    task_id text,
    query_id text,
    linked_analysis_record_id bigint references analysis_records(id),
    canonical_symbol text,
    display_name text,
    overall_status text not null,
    truth_level text,
    destructive boolean not null default false,
    summary_json jsonb not null default '{}'::jsonb,
    started_at timestamptz not null default now(),
    ended_at timestamptz,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_execution_sessions_started
    on execution_sessions (started_at desc, subsystem, overall_status);

create index if not exists idx_execution_sessions_owner_started
    on execution_sessions (owner_user_id, started_at desc);

create table if not exists execution_events (
    id bigserial primary key,
    execution_session_id bigint not null references execution_sessions(id) on delete cascade,
    occurred_at timestamptz not null default now(),
    phase text not null,
    step text,
    target text,
    status text not null,
    truth_level text,
    message text,
    error_code text,
    detail_json jsonb not null default '{}'::jsonb
);

create index if not exists idx_execution_events_session_time
    on execution_events (execution_session_id, occurred_at asc);

create index if not exists idx_execution_events_phase_status
    on execution_events (phase, status, occurred_at desc);

create table if not exists admin_logs (
    id bigserial primary key,
    actor_user_id text references app_users(id),
    actor_role text,
    subsystem text not null,
    category text,
    event_type text not null,
    target_type text,
    target_id text,
    scope text not null default 'system' check (scope in ('system')),
    severity text not null default 'info',
    outcome text,
    message text,
    detail_json jsonb not null default '{}'::jsonb,
    related_session_key text,
    occurred_at timestamptz not null default now()
);

create index if not exists idx_admin_logs_occurred
    on admin_logs (occurred_at desc, subsystem, event_type);

create table if not exists system_actions (
    id bigserial primary key,
    action_key text not null,
    actor_user_id text references app_users(id),
    scope text not null default 'system' check (scope in ('system')),
    destructive boolean not null default false,
    status text not null,
    request_json jsonb not null default '{}'::jsonb,
    result_json jsonb not null default '{}'::jsonb,
    admin_log_id bigint references admin_logs(id),
    created_at timestamptz not null default now(),
    completed_at timestamptz
);

create index if not exists idx_system_actions_created
    on system_actions (created_at desc, action_key, status);

create table if not exists symbol_master (
    id bigserial primary key,
    canonical_symbol text not null unique,
    display_symbol text,
    market text not null,
    exchange_code text,
    asset_type text not null,
    display_name text,
    currency text,
    lot_size numeric(24, 8),
    is_active boolean not null default true,
    search_aliases jsonb not null default '[]'::jsonb,
    source text,
    source_payload_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create index if not exists idx_symbol_master_market_active
    on symbol_master (market, is_active, canonical_symbol);

create table if not exists market_data_manifests (
    id bigserial primary key,
    manifest_key text not null unique,
    dataset_family text not null,
    market text not null,
    asset_scope text,
    storage_backend text not null check (storage_backend in ('parquet_local', 'parquet_nas', 'hybrid')),
    root_uri text not null,
    file_format text not null default 'parquet',
    partition_strategy text,
    symbol_namespace text,
    description text,
    config_json jsonb not null default '{}'::jsonb,
    active_version_id bigint,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists market_dataset_versions (
    id bigserial primary key,
    manifest_id bigint not null references market_data_manifests(id),
    version_label text not null,
    version_hash text not null,
    source_kind text,
    generated_at timestamptz,
    as_of_date date,
    coverage_start date,
    coverage_end date,
    symbol_count integer,
    row_count bigint,
    partition_count integer,
    file_inventory_json jsonb not null default '{}'::jsonb,
    content_stats_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (manifest_id, version_label),
    unique (manifest_id, version_hash)
);

alter table market_data_manifests
    add constraint fk_market_data_manifests_active_version
    foreign key (active_version_id) references market_dataset_versions(id);

create table if not exists market_data_usage_refs (
    id bigserial primary key,
    entity_type text not null check (
        entity_type in (
            'analysis_record',
            'scanner_run',
            'watchlist',
            'backtest_run',
            'portfolio_sync_state'
        )
    ),
    entity_id bigint not null,
    usage_role text not null check (
        usage_role in (
            'primary_bars',
            'benchmark_bars',
            'universe_snapshot',
            'symbol_master_snapshot'
        )
    ),
    manifest_id bigint not null references market_data_manifests(id),
    dataset_version_id bigint not null references market_dataset_versions(id),
    detail_json jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now(),
    unique (entity_type, entity_id, usage_role, dataset_version_id)
);
