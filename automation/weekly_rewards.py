import os
import secrets
import string
import sys
from datetime import datetime, timedelta, timezone
import requests

SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
WHATSAPP_TOKEN = os.environ.get("WHATSAPP_TOKEN", "")
WHATSAPP_PHONE_NUMBER_ID = os.environ.get("WHATSAPP_PHONE_NUMBER_ID", "")
TEMPLATE_NAME = os.environ.get("WHATSAPP_TEMPLATE_NAME", "")
TEMPLATE_LANGUAGE = os.environ.get("WHATSAPP_TEMPLATE_LANGUAGE", "en")
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"
GRAPH_VERSION = os.environ.get("WHATSAPP_GRAPH_VERSION", "v22.0")
RUN_ID = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
}

def db_get(path, params=None):
    response = requests.get(f"{SUPABASE_URL}/rest/v1/{path}", headers=headers, params=params, timeout=30)
    response.raise_for_status()
    return response.json()

def db_post(path, payload, prefer="return=representation"):
    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={**headers, "Prefer": prefer},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    data = response.json() if response.text else None
    return data

def db_patch(path, payload, params):
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{path}",
        headers={**headers, "Prefer": "return=minimal"},
        params=params,
        json=payload,
        timeout=30,
    )
    response.raise_for_status()

def make_coupon():
    alphabet = string.ascii_uppercase + string.digits
    return "QR-" + "".join(secrets.choice(alphabet) for _ in range(8))

def send_whatsapp(phone, name, code, expiry):
    if not (WHATSAPP_TOKEN and WHATSAPP_PHONE_NUMBER_ID and TEMPLATE_NAME):
        raise RuntimeError("WhatsApp settings are missing.")
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/{WHATSAPP_PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": phone.replace("+", ""),
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {"code": TEMPLATE_LANGUAGE},
            "components": [{
                "type": "body",
                "parameters": [
                    {"type": "text", "text": name[:100]},
                    {"type": "text", "text": code},
                    {"type": "text", "text": expiry.strftime("%d %b %Y")}
                ]
            }]
        }
    }
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}", "Content-Type": "application/json"},
        json=payload,
        timeout=30,
    )
    response.raise_for_status()
    return response.json()

def main():
    customers = db_get("customers", {
        "select": "id,full_name,phone_e164,registered_at,last_rewarded_at",
        "marketing_consent": "eq.true",
        "opted_out_at": "is.null",
        "order": "registered_at.asc",
        "limit": "10000"
    })
    # One-time reward rule: anyone already rewarded is excluded.
    eligible = [c for c in customers if not c.get("last_rewarded_at")]
    count = len(eligible)
    winner_count = (count * 5) // 100
    if count > 0 and winner_count == 0:
        winner_count = 1

    print(f"Run {RUN_ID}: {count} eligible customer(s); planned winners: {winner_count}; DRY_RUN={DRY_RUN}")
    if winner_count == 0:
        print("No eligible customers. Nothing to do.")
        return

    # Shuffle securely and select the required number.
    secrets.SystemRandom().shuffle(eligible)
    winners = eligible[:winner_count]
    now = datetime.now(timezone.utc)
    expiry = now + timedelta(days=7)

    if DRY_RUN:
        print("DRY RUN: no coupons will be created and no messages will be sent.")
        for customer in winners:
            print(f"Would select customer ID {customer['id']} (phone masked: ***{customer['phone_e164'][-4:]})")
        return

    failures = 0
    for customer in winners:
        code = make_coupon()
        try:
            # Create the coupon before sending so every outgoing message refers to a real code.
            created = db_post("coupons", {
                "customer_id": customer["id"],
                "coupon_code": code,
                "discount_percent": 10,
                "issued_at": now.isoformat(),
                "expires_at": expiry.isoformat(),
                "message_status": "pending",
                "created_by_run": RUN_ID
            })
            coupon_id = created[0]["id"]
            try:
                send_whatsapp(customer["phone_e164"], customer["full_name"], code, expiry)
                db_patch("coupons", {"message_status": "sent"}, {"id": f"eq.{coupon_id}"})
                db_patch("customers", {"last_rewarded_at": now.isoformat()}, {"id": f"eq.{customer['id']}"})
                print(f"Sent reward to customer {customer['id']}; coupon {code}")
            except Exception as send_error:
                failures += 1
                # Keep coupon marked failed for manual review; don't mark customer rewarded.
                db_patch("coupons", {
                    "message_status": "failed",
                    "message_error": str(send_error)[:500]
                }, {"id": f"eq.{coupon_id}"})
                print(f"Message failed for customer {customer['id']}: {send_error}", file=sys.stderr)
        except Exception as error:
            failures += 1
            print(f"Could not process customer {customer['id']}: {error}", file=sys.stderr)

    if failures:
        raise SystemExit(f"{failures} winner(s) failed to process. Review coupons table before rerunning.")

if __name__ == "__main__":
    main()
