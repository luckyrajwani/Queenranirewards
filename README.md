# Queen Rani — Customer Rewards Starter

A small, low-cost starter for Queen Rani's informational boutique website:
- Customer registration with promotional WhatsApp opt-in
- Supabase database
- Weekly selection of 5% of eligible registered customers
- Unique coupon per winner, valid for 7 days
- WhatsApp Cloud API template messages
- In-store-only redemption tracked in Supabase

## Architecture

- Website: Cloudflare Pages (free tier)
- Database and registration API: Supabase (free tier, subject to limits)
- Weekly automation: GitHub Actions (free tier for public repos; private repo usage is subject to GitHub limits)
- Messaging: WhatsApp Business Platform Cloud API (Meta business setup, approved template, and message charges/policies may apply)

This is a starter project, not a fully audited production system. Configure secrets carefully and test with your own number before launch.

## 1. Create Supabase project

1. Create a project at https://supabase.com
2. Open SQL Editor and run `supabase/schema.sql`.
3. In Project Settings → API, copy:
   - Project URL
   - `service_role` key (keep secret; never put it in website code)
4. Deploy the registration Edge Function:
   - Install Supabase CLI: https://supabase.com/docs/guides/cli
   - `supabase login`
   - `supabase link --project-ref YOUR_PROJECT_REF`
   - `supabase secrets set SUPABASE_URL=https://YOUR_PROJECT.supabase.co SUPABASE_SERVICE_ROLE_KEY=YOUR_SERVICE_ROLE_KEY`
   - `supabase functions deploy register-customer`
5. Copy the deployed function URL, normally:
   `https://YOUR_PROJECT_REF.supabase.co/functions/v1/register-customer`

## 2. Configure website

Edit `public/config.js` and set `REGISTRATION_FUNCTION_URL` to your deployed function URL.
Do not put the Supabase service-role key or WhatsApp token in this file.

Deploy the `public` folder to Cloudflare Pages:
1. Create a GitHub repository and upload the files.
2. In Cloudflare Pages, connect the repository.
3. Set build command to blank / none and output directory to `public`.
   Alternatively, upload the static files directly if your Cloudflare Pages setup supports Direct Upload.

## 3. Set up WhatsApp messaging

1. Set up Meta WhatsApp Business Platform / Cloud API.
2. Get the Phone Number ID and a permanent/long-lived access token as appropriate for your business setup.
3. Create and get approval for a WhatsApp template in the language you need. Example template body:
   `Congratulations {{1}}! You have received 10% off your next purchase at Queen Rani. Use coupon {{2}} before {{3}}. Valid for in-store purchases only. Terms apply.`
4. Keep the template name and language code exactly as approved by Meta.

## 4. Configure weekly automation

The script `automation/weekly_rewards.py` uses Supabase REST API and WhatsApp Cloud API.

Add these GitHub repository Actions secrets:
- `SUPABASE_URL` — e.g. `https://YOUR_PROJECT.supabase.co`
- `SUPABASE_SERVICE_ROLE_KEY` — service role key (secret)
- `WHATSAPP_TOKEN` — WhatsApp Cloud API access token (secret)
- `WHATSAPP_PHONE_NUMBER_ID` — Meta phone number ID
- `WHATSAPP_TEMPLATE_NAME` — approved template name
- `WHATSAPP_TEMPLATE_LANGUAGE` — approved language code, e.g. `en`
- `DRY_RUN` — set to `true` for a test run; set to `false` only after testing

The workflow runs every Monday at 04:00 UTC (09:30 AM India time). You can also run it manually from the GitHub Actions tab.

Important: set `DRY_RUN=true` first. Dry-run logs a sample plan and does not create coupons or send messages. After a successful test, set it to `false`.

The job chooses `floor(5% of eligible customers)` with a minimum of one winner when at least one eligible customer exists. A customer is eligible if they opted into WhatsApp marketing and have not already received a reward. This "no repeat winners" rule is conservative; you can change it later if you want repeat winners after a cooldown.

## 5. Redeeming coupons in-store

The `coupons` table contains the coupon code, customer, expiry and redemption status.
In Supabase Table Editor, search for the code and set `redeemed_at` to the current timestamp after validating the code and expiry. Do not let customers edit this table.

For production, add a small staff-only redemption screen backed by a server-side function and staff authentication. Do not expose service-role keys in a browser.

## Data/privacy checklist

- Collect only information you need.
- Ask for explicit consent before sending promotional WhatsApp messages.
- Include an opt-out method in messages and maintain an opt-out process.
- Use a Meta-approved template for business-initiated WhatsApp messages.
- Restrict access to customer records and never publish service-role keys.
- Publish a simple privacy notice and terms for the promotion.
- State any minimum purchase, exclusions, and redemption conditions before launch.

## Local preview

Open `public/index.html` in a browser. Registration will work only after the Edge Function URL is configured and deployed.
