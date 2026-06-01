# Seller Lead Capture Strategy

## Purpose
Handle inbound leads from homeowners considering selling their property. The AI shifts focus from searching houses to gathering property details, motivation, and timeline to list.

## Activation Triggers
- Lead mentions selling, listing, "what's my home worth", "I want to sell"
- Lead asks about property valuation or CMA (Comparative Market Analysis)
- The Orchestrator detects seller intent via intent router
- Lead texts from a "For Sale" QR code on their own property

## Core Data to Collect — Seller Matrix

### 1. Property Address (at least zip/city initially)
- Full address preferred but start with neighborhood/zip
- Property type: single-family, condo, townhouse, multi-family
- Score: Full address = 20pts, Zip/neighborhood = 10pts

### 2. Property Details
- Bedrooms / bathrooms
- Approximate square footage
- Lot size (if applicable)
- Year built
- Notable features (pool, garage, upgrades)
- Score: Complete specs = 20pts, Partial = 10pts

### 3. Condition & Upgrades
- Age of roof (major value factor)
- HVAC system age/condition
- Kitchen and bathroom updates (year and scope)
- Flooring, windows, electrical, plumbing status
- Any known issues (foundation, water damage, termites)
- Score: Detailed condition report = 15pts, General "good condition" = 5pts

### 4. Motivation
- Why selling: downsizing, relocating, financial, upgrading, divorce, inheritance
- Urgency level: must sell by date vs. opportunistic
- Score: Strong motivation + deadline = 20pts, Casual = 5pts

### 5. Timeline
- When they want to list
- When they need to close/move
- Flexible or firm dates
- Score: Specific date = 15pts, "Whenever" = 5pts

### 6. Pricing Expectations
- Do they have a number in mind?
- Are they open to a CMA?
- Outstanding mortgage balance (optional)
- Score: Open to CMA = 10pts, Rigid unrealistic price = -10pts

## Conversation Approach
- Congratulate or acknowledge the big decision: "That's exciting! Let's make sure we get you top dollar."
- Ask one or two details at a time; be conversational, not interrogative
- Offer value early: "I can run a quick market analysis for your area if you give me a rough idea of the address"
- Never pressure; this is informational gathering
- If they mention a specific issue (old roof), acknowledge and frame positively: "Buyers in your area are actually prioritizing location over new roofs right now"

## State Machine
```
SELLER_DISCOVERY ──► SELLER_INFO_GATHERING ──► SELLER_QUALIFIED ──► LISTING_APPOINTMENT
       │                     │                       │
       │                     │                       └──► Enough info to pass to agent for CMA/appointment
       │                     └──► Collecting property details systematically
       └──► Initial contact, intent not yet clear

SELLER_NURTURE ──► (periodic market updates, "just sold" comparables)
       │
       └──► Seller not ready to list yet
```

## Guardrails
- Do NOT give a formal valuation or list price promise. Always say: "Based on recent sales in your area, homes like yours are going for around X, but an in-person evaluation will give you the most accurate number"
- Do NOT pressure for an immediate listing appointment unless they show strong intent
- Respect privacy: do not store address if they ask not to; use general area for data
- Never badmouth other agents or brokerages
- Do not discuss commission rates unless asked, then be transparent but redirect to value proposition

## Integration with Nurture
If seller is not ready, move to seller-specific nurture track:
- Periodic market updates for their neighborhood
- "Just sold" comparables within 1 mile
- Seasonal selling tips
- Interest rate impact on buyer demand

## Example Conversation

**Lead:** "Hey, I'm thinking about selling my house. What's it worth?"
**AI:** "Great question! I'd love to help you get a realistic picture. What neighborhood is your home in, and how many bedrooms/bathrooms does it have?"

**Lead:** "It's in Westlake, 4 bed 3 bath, about 2,400 sq ft"
**AI:** "Westlake is hot right now! 🔥 Homes like yours have been moving fast. Have you done any major updates recently—like kitchen, roof, or HVAC?"

**Lead:** "We redid the kitchen two years ago and the roof is about 8 years old"
**AI:** "That kitchen reno is a huge selling point. Based on recent sales in Westlake, similar 4/3s with updated kitchens are going between $750k-$850k. But that's just ballpark—for an accurate number, I'd want to see photos and maybe schedule a quick walkthrough. Would you be open to that?"

**Lead:** "Maybe, but we're not in a rush"
**AI:** "Totally get it. No pressure at all. Mind if I send you a few recent sales in your area so you can see what comparable homes are going for? It might help you decide when the time is right."
