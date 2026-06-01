# Appointment Scheduling Strategy

## Purpose
Handle booking of property viewings or agent consultations directly within WhatsApp. The AI presents available slots, confirms booking, and syncs with the agent's calendar automatically.

## Activation Triggers
- Lead explicitly requests a viewing: "Can I see this house?", "When can I tour it?"
- AI determines high qualification and offers viewing as next step (warmth threshold met)
- Lead taps `[Book a Viewing]` interactive button (WhatsApp list message or flow)
- Lead asks about open houses or showing availability
- Seller requests a listing appointment or CMA consultation

## Pre-conditions
- Property of interest must be identified (if not, ask first)
- Lead should ideally be qualified (warm/hot), but do NOT block a viewing request if lead refuses qualification questions — note it for the agent
- Agent's calendar availability (Google/Outlook) must be cached and fresh (max 5 minutes old)
- Time zone must be detected from lead's phone number or explicit mention

## Scheduling Steps

### Step 1: Fetch Available Slots
- Query `calendar_scheduler` tool for next 7 days of agent availability
- Filter out already-booked slots
- Consider property-specific constraints (occupied homes, lockbox availability)
- For seller appointments: allow longer slots (45-60 min vs 30 min for buyer viewings)

### Step 2: Present Slots
- Offer max 3-4 options in a friendly, concise way
- Use WhatsApp interactive list messages for one-tap booking when possible
- Format: "I've got Tuesday at 3pm, Wednesday at 10am, or Saturday at 1pm. Which works best?"
- Show times in lead's detected time zone

### Step 3: Confirm Slot Selection
- On slot selection, double-check availability (prevent double booking)
- If slot was just taken: "Oops, that just got booked. How about 4pm instead?"
- Suggest nearby alternatives immediately

### Step 4: Book & Confirm
- Book via Google Calendar API
- Create event with: lead name, phone, property address, agent assigned
- Send confirmation with address, date/time, and preparation instructions
- Attach `.ics` file if WhatsApp supports it
- Update CRM: set lead state to `VIEWING_SCHEDULED`

### Step 5: Reminders
- **24 hours before**: "Hey [Name], just a reminder about your viewing tomorrow at [time] at [address]. See you there! 🏠"
- **1 hour before**: "Your showing is in 1 hour! Here's the address: [address]. Looking forward to it!"
- If lead hasn't confirmed: "Just checking—are we still on for [time] today?"

## Handling Conflicts
- No slots available this week: "Looks like my calendar is packed this week, but let me find the next soonest time and get back to you. Or would a virtual tour work?"
- Offer to have agent reach out to squeeze them in
- For hot leads: flag agent for priority scheduling

## After Booking
- Transition lead state to `VIEWING_SCHEDULED`
- If buyer: remind to bring pre-approval letter
- If seller: confirm if agent needs to do CMA beforehand
- After viewing: prompt agent for feedback, update lead status

## Seller Consultation Adaptations
- Longer time slots (45-60 minutes)
- Confirm if agent needs property photos or docs beforehand
- Include CMA preparation notes in calendar event
- Ask seller to have recent upgrade/repair documentation ready

## Guardrails
- Never double-book — always verify before confirming
- Confirm property address is correct in the calendar event
- Never schedule viewings without lead's explicit consent
- If lead wants to bring someone (spouse, inspector), note it in the event
- Respect agent's personal time — don't book outside working hours unless agent has explicitly set availability

## Integration Points
- Uses `calendar_scheduler.py` execution worker for Google/Outlook API
- Emits `appointment.booked` event for dashboard notification
- Triggers `notification_service.py` to alert agent
- Updates lead state in database via `lead_data_service.py`
- Loads `buyer_discovery.json` skill to maintain warm tone during scheduling
