# Tampa Food Phone

A private phone agent for browsing restaurant menus and preparing a cart for family review.
Twilio handles phone/SMS, LiveKit handles voice, and menus are read from `data/menus.json`.

**It does not place orders or handle payment credentials.** Delivery to `33609` is preferred;
pickup is the fallback. A family member verifies availability, fees, address, and final total.

## Setup

Requires Python 3.10–3.14, [`uv`](https://docs.astral.sh/uv/), and the LiveKit CLI.

```sh
brew install livekit-cli
uv sync
cp .env.example .env.local
lk cloud auth
```

Configure `.env.local`:

```dotenv
LIVEKIT_URL=wss://YOUR_PROJECT.livekit.cloud
LIVEKIT_API_KEY=...
LIVEKIT_API_SECRET=...

ALLOWED_CALLER_NUMBERS=+1XXXXXXXXXX
CALLER_NAME=Dad
DELIVERY_ZIP=33609
FULFILLMENT_PREFERENCE=delivery_then_pickup

TWILIO_ACCOUNT_SID=...
TWILIO_AUTH_TOKEN=...
TWILIO_FROM_NUMBER=+14486782672
ORDER_REVIEW_NUMBER=+18137856599

MENU_DATA_PATH=data/menus.json
AGENT_NAME=tampa-food-phone
```

Use E.164 phone numbers without spaces or punctuation.

## Add menus

Replace the fake fixtures in `data/menus.json` before a real call. Each restaurant contains
stable IDs, location details, source/freshness metadata, and categorized items with prices in
cents. Preserve IDs across refreshes because the agent uses them in tool calls.

Do not scrape menus during a call. Refresh the file beforehand and treat delivery availability
and marketplace prices as provisional until checkout.

## Test

Run the deterministic tests:

```sh
uv run pytest
```

Start the worker in development mode:

```sh
uv run python -m tampa_phone.agent dev
```

In LiveKit Agent Console, select `tampa-food-phone` and test menu browsing, interruption,
repetition, cart readback, and SMS handoff.

## Connect Twilio to LiveKit

1. Create a Twilio **Elastic SIP Trunk**.
2. Set its Origination URI to:

   ```text
   sip:YOUR_PROJECT.sip.livekit.cloud;transport=tcp
   ```

3. Associate Twilio number `+14486782672` with the trunk.
4. In `livekit/inbound-trunk.example.json`, set `allowedNumbers` to the approved caller's
   E.164 number.
5. Create the LiveKit trunk and dispatch rule:

   ```sh
   lk sip inbound create livekit/inbound-trunk.example.json
   lk sip dispatch create livekit/dispatch-rule.json
   ```

Each call receives an isolated LiveKit room. The caller is checked at both the SIP trunk and
application layers.

## Run

```sh
# Development
uv run python -m tampa_phone.agent dev

# Production worker
uv run python -m tampa_phone.agent start
```

For deployment, copy `.env.local` values into deployment secrets; never commit the file.

## Pilot checklist

- Replace all demo menu data.
- Test approved and rejected callers over the actual phone connection.
- Confirm SMS permissions and delivery to the review number.
- Verify that readback includes quantities, notes, subtotal, and fulfillment preference.
- Confirm that no action claims an order was placed.
