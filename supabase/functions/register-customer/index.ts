import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

function json(data: unknown, status = 200) {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });
}

function normalizePhone(raw: string): string | null {
  // Accept common Indian formats; store normalized E.164-like +91 number.
  let digits = raw.replace(/\D/g, "");
  if (digits.startsWith("0091")) digits = digits.slice(2);
  if (digits.length === 10) digits = "91" + digits;
  if (digits.length === 12 && digits.startsWith("91") && digits[2] >= "6" && digits[2] <= "9") {
    return "+" + digits;
  }
  return null;
}

Deno.serve(async (req) => {
  if (req.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (req.method !== "POST") return json({ error: "Method not allowed." }, 405);

  try {
    const body = await req.json();
    const fullName = String(body.full_name ?? "").trim();
    const phone = normalizePhone(String(body.phone ?? ""));
    const consent = body.marketing_consent === true;

    if (fullName.length < 2 || fullName.length > 100) {
      return json({ error: "Please enter a name between 2 and 100 characters." }, 400);
    }
    if (!phone) return json({ error: "Enter a valid Indian mobile number, including +91 if needed." }, 400);
    if (!consent) return json({ error: "Please opt in to promotional WhatsApp messages to register for rewards." }, 400);

    const url = Deno.env.get("SUPABASE_URL");
    const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
    if (!url || !serviceKey) return json({ error: "Registration service is not configured." }, 500);

    const supabase = createClient(url, serviceKey, { auth: { persistSession: false } });

    const { data: existing, error: lookupError } = await supabase
      .from("customers").select("id, opted_out_at").eq("phone_e164", phone).maybeSingle();
    if (lookupError) throw lookupError;

    if (existing) {
      if (existing.opted_out_at) {
        const { error } = await supabase.from("customers").update({
          full_name: fullName,
          marketing_consent: true,
          consented_at: new Date().toISOString(),
          opted_out_at: null
        }).eq("id", existing.id);
        if (error) throw error;
      } else {
        return json({ error: "This mobile number is already registered." }, 409);
      }
    } else {
      const { error } = await supabase.from("customers").insert({
        full_name: fullName,
        phone_e164: phone,
        marketing_consent: true,
        consented_at: new Date().toISOString()
      });
      if (error) {
        if (error.code === "23505") return json({ error: "This mobile number is already registered." }, 409);
        throw error;
      }
    }

    return json({ ok: true });
  } catch (error) {
    console.error("Registration error:", error);
    return json({ error: "Could not complete registration. Please try again later." }, 500);
  }
});
