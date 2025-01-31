-- Create posts table
create table posts (
    uri text primary key,
    cid text not null,
    reply_parent text,
    reply_root text,
    indexed_at timestamp with time zone default timezone('utc'::text, now()) not null
);

-- Create subscription_states table
create table subscription_states (
    service text primary key,
    cursor bigint not null
);

-- Create indexes
create index posts_indexed_at_idx on posts(indexed_at desc);

-- Create users table
create table if not exists users (
    did text primary key,
    added_at timestamp with time zone default timezone('utc'::text, now()) not null,
    active boolean default true not null
);

-- Create indexes
create index if not exists users_added_at_idx on users(added_at desc);
create index if not exists users_active_idx on users(active);