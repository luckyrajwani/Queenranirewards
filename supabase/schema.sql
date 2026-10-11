-- Run this in Supabase SQL Editor.
create extension if not exists pgcrypto;

create table if not exists public.customers (
  id uuid primary key default gen_random_uuid(),
  full_name text not null check (char_length(full_name) between 1 and 100),
  phone_e164 text not null unique,
  marketing_consent boolean not null default false,
  consented_at timestamptz,
  registered_at timestamptz not null default now(),
  opted_out_at timestamptz,
  last_rewarded_at timestamptz
);

create table if not exists public.coupons (
  id uuid primary key default gen_random_uuid(),
  customer_id uuid not null references public.customers(id) on delete cascade,
  coupon_code text not null unique,
  discount_percent integer not null default 10 check (discount_percent = 10),
  issued_at timestamptz not null default now(),
  expires_at timestamptz not null,
  redeemed_at timestamptz,
  redemption_channel text not null default 'physical_store' check (redemption_channel = 'physical_store'),
  message_status text not null default 'pending' check (message_status in ('pending','sent','failed')),
  message_error text,
  created_by_run text
);

create index if not exists customers_eligible_idx
  on public.customers (registered_at)
  where marketing_consent = true and opted_out_at is null;

create index if not exists coupons_customer_idx on public.coupons(customer_id);
create index if not exists coupons_code_idx on public.coupons(coupon_code);

-- No browser-side access to customer or coupon records.
alter table public.customers enable row level security;
alter table public.coupons enable row level security;

revoke all on public.customers from anon, authenticated;
revoke all on public.coupons from anon, authenticated;

-- The registration Edge Function and weekly automation use the service role key server-side.
-- Never expose that key in the website.
