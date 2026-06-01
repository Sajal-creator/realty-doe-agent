# Nurture & Re-Engagement Strategy

## Purpose
Define when and how to automatically re-engage leads that have gone silent. The goal is to deliver hyper-personalized value drops, not generic spam. This is the anti-ghosting engine.

## Trigger Rules (checked by Orchestrator Scheduler every hour)
- Lead has `status = AWAITING_REPLY` and no activity for **72 hours** → Tier 1 nurture
- After first nurture, still no reply after another **72 hours** → Tier 2 nurture
- After second nurture, still no reply after another **72 hours** → Tier 3 nurture (9 days total)
- After three unsuccessful nurtures, reduce frequency to **weekly** for 30 days
- After **30 days** of silence, mark as `COLD` and reduce to monthly check-ins
- If lead ever replies at ANY point → immediately exit nurture sequence, set session active, restart qualification/support

## Nurture Message Tiers

### Tier 1 — Value Drop (3 days silent)
**Strategy:** Use fresh MLS data matching their criteria. Craft message around a new listing, price drop, or market stat.
**Template (LLM-guided):**
"Hey [Name], that place we discussed might be gone, but I saw this similar gem that just popped up—want a virtual tour link?"
**Requirements:**
- Must insert a REAL listing or compelling stat (e.g., "prices in [neighborhood] just dropped 2%")
- Use `vector_mls_matcher` to find properties matching their stored preferences
- Personalize with their known budget, neighborhood, property type
- Never send the same listing twice

### Tier 2 — Market Insight (6 days silent)
**Strategy:** Softer value — market insight, article, neighborhood update, or educational content.
**Template:**
"Thought you'd find this interesting: new schools opening in [preferred area] might bump values. Here's a quick read: [link]"
**Requirements:**
- Use `hyper_local_expert` skill for neighborhood-specific content
- Frame as helpful information, not sales pitch
- No call-to-action pressure

### Tier 3 — Gentle Check-in (9 days silent)
**Strategy:** Direct but zero-pressure check-in.
**Template:**
"Hi [Name], just checking in. I'm still here if you have any questions or want to revisit your search. No rush!"
**Requirements:**
- Short and warm
- No listings attached
- Leave the door completely open

### Tier 4 — Reduced Frequency (14-30 days)
**Strategy:** Monthly market snapshot or seasonal content.
**Template:**
"Hey [Name], here's your monthly [Neighborhood] market snapshot: prices are [trending up/down], inventory is [low/high]. Let me know if you want to dive back in!"
**Requirements:**
- Once per month maximum
- Pure informational value
- Include unsubscribe option

## Personalization Rules
- The LLM MUST use lead's known preferences (neighborhood, budget, property type) to tailor every message
- If no preferences known, use the original source property as a hook
- Do NOT send the same listing/content twice — track sent items in database
- Respect opt-outs immediately: if lead says "stop", "unsubscribe", "leave me alone" → mark `DO_NOT_CONTACT` and cease ALL messages
- Do NOT nurture leads with `conversation_mode = AGENT` (human is actively chatting)
- Do NOT nurture leads with open support tickets

## Warmth Decay Algorithm
Over time without reply, warmth score decays automatically:
- After 7 days of silence → drop warmth by 10 points
- After 14 days → drop by 20 total
- After 30 days → drop by 35 total
- After 60 days → drop to minimum (floor at 10)
- Dashboard reflects this decay in real-time

## State Handling
Upon receiving ANY reply during nurture:
1. Immediately exit nurture sequence
2. Set session as active
3. Reset `awaiting_reply` timer
4. Run Context Summarizer to reconstitute conversation state
5. Restart appropriate flow (qualification, support, etc.)
6. Notify agent if lead was previously hot: "🔥 [Name] just came back!"

## Opt-Out Compliance
- Any variation of "stop", "unsubscribe", "remove me", "don't contact me" → immediate `DO_NOT_CONTACT`
- Send confirmation: "Got it, I've removed you from our messages. If you ever want to reconnect, just text here anytime."
- Log opt-out in database with timestamp and trigger word
- Never override opt-out, even if agent manually requests it

## Integration Points
- Triggered by `reengagement_cron.py` execution worker
- Uses `vector_mls_matcher.py` for fresh listing discovery
- Uses `hyper_local_expert.json` skill for neighborhood content
- Emits `nurture.sent` event for dashboard activity timeline
- Feeds data to `warmth_engine.py` for score decay
