# Agent Handover Strategy

## Purpose
Define when and how the AI should gracefully hand over the conversation to a live human agent. The handover must be seamless, with full context transfer so the agent can pick up instantly.

## Trigger Events

### Immediate Handover (Urgent)
- Lead explicitly asks for a human: "I want to talk to a real person", "Get me an agent"
- Lead is HOT (score ≥ 80) and requests immediate action AI cannot complete: "I want to make an offer right now"
- Support issue involves money transfer, contract errors, or legal concerns
- Lead expresses extreme frustration or anger (sentiment score < -0.7)

### Standard Handover
- AI detects frustration after repeated unsuccessful attempts (sentiment negative for 3+ exchanges)
- Support issue cannot be resolved after 2 attempts
- Lead asks complex questions outside AI's knowledge domain
- Lead requests specific agent by name

### Scheduled Handover
- Lead wants to speak with an agent but not urgently: "Can someone call me tomorrow?"
- System schedules callback and notifies agent

## Handover Process

### Step 1: Acknowledge
Tell the lead you're connecting them:
- Standard: "Absolutely, let me get a real person for you. One moment."
- Urgent: "I hear you—let me connect you with our specialist right now."
- Scheduled: "I'll have someone reach out to you at [time]. Does that work?"

### Step 2: Notify Agent
- Send high-priority push notification to agent dashboard with sound
- Lead card appears in "Handover Queue" column with pulsing red border
- Include urgency level and brief reason for handover

### Step 3: Context Transfer
Generate a concise summary for the agent:
```
HANDOVER SUMMARY:
- Lead: [Name], [Phone]
- Status: [Warmth tier], Score: [X/100]
- 4-D Matrix: Budget: [X], Timeline: [X], Financing: [X], Deal-breakers: [X]
- Reason for handover: [trigger reason]
- Last 3 messages: [conversation excerpt]
- Open tickets: [if any]
```
Display this in the agent's chat pane before the conversation history.

### Step 4: Agent Takeover
- When agent starts typing, AI goes completely silent
- Orchestrator sets `conversation_mode = AGENT`
- All messages from agent bypass AI and go directly to WhatsApp
- AI monitors but does not interrupt

### Step 5: Agent Closure
After conversation, agent can:
- Mark handover as "Resolved" and hand back to AI for nurturing
- Keep lead as agent-assigned for ongoing relationship
- Schedule follow-up tasks

## Fallback Protocol
If no agent is available within 2 minutes:
- Send to lead: "My team is a bit tied up right now, but I've flagged your message as urgent. Someone will get back to you within [X] minutes. In the meantime, I'm still here if you need anything."
- Create a priority callback task in agent's queue
- If no agent responds within 30 minutes: send follow-up to lead with estimated wait time

## Post-Handover Rules
- Lead remains assigned to the agent for 24 hours unless re-assigned
- AI monitors but doesn't interrupt unless re-engaged by lead
- If agent doesn't respond within the SLA, escalate to agency admin
- After agent marks "hand back to AI", resume normal AI flow with full context

## Multi-Agent Scenarios
- If two agents try to take over same lead: second gets warning toast "Already being handled by [Agent Name]"
- If primary agent goes offline: route handover queue to next available agent
- Track agent response times for performance metrics

## Guardrails
- Never leave a lead hanging during handover — always acknowledge the transition
- Always provide full context to agent — no agent should have to ask "what did they want?"
- Never reveal to the lead that they were talking to AI unless they ask directly
- If lead asks "are you a bot?": "I'm an AI assistant here to help, and I can connect you with a real person anytime!"

## Integration Points
- Uses `hijack_controller.py` to flip session state and sever AI connection
- Uses `agent_router.py` to find available agent with lowest workload
- Uses `notification_service.py` for dashboard push alerts
- Emits `handover.request` and `agent.takeover` events for real-time dashboard updates
- Loads `handover_etiquette.json` skill for graceful transition phrasing
