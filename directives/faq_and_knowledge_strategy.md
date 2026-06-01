# FAQ & Knowledge Base Strategy

## Purpose
Enable the AI to answer common real estate questions instantly without escalating to a human agent. Uses a vectorized FAQ database for retrieval-augmented generation (RAG), with fallback to Google CAG or File Search API for larger document sets.

## Activation Triggers
- Lead asks a question matching "FAQ" intent (e.g., "What's the process for first-time homebuyers?", "How much are closing costs?", "What are the best schools around here?")
- AI can proactively offer FAQ answers when conversation context suggests confusion
- During qualification, if lead asks educational questions about the buying/selling process

## Retrieval Process

### Step 1: Semantic Search
- Use `faq_vector_search` tool with user's query to retrieve top 3 relevant Q&A pairs
- Include similarity scores with each result
- If using Google File Search API: upload documents once, query via managed RAG endpoint

### Step 2: Confidence Evaluation
- **Score > 0.85**: High confidence — craft natural answer incorporating retrieved info
- **Score 0.70 - 0.85**: Medium confidence — answer but add disclaimer: "Based on what I know, but let me double-check with my team"
- **Score < 0.70**: Low confidence — do NOT answer, escalate: "That's a great question! Let me connect you with an expert who can give you the most accurate info"

### Step 3: Response Formulation
- Rephrase retrieved facts in the AI's warm, conversational tone — never copy-paste
- Include source attribution when relevant: "According to local guidelines..."
- If information is time-sensitive (rates, market stats): note the date "As of [month]..."
- Keep answers concise — max 3-4 sentences for simple questions, offer to elaborate

## Content Areas (FAQ Database Should Cover)

### Home Buying Process
- Steps from pre-approval to closing
- First-time homebuyer programs and incentives
- Earnest money, inspections, appraisals explained
- Timeline expectations (30-60 day closing typical)

### Financing & Mortgage Basics
- How to get pre-approved
- Types of loans (FHA, VA, Conventional, USDA)
- Down payment assistance programs
- How interest rates affect monthly payments
- PMI (Private Mortgage Insurance) explanation

### Local Market Trends (cached, updated daily)
- Average days on market by neighborhood
- Median sale prices by area
- Inventory levels (buyer's vs seller's market)
- Price trends (appreciation/depreciation)

### School District Information
- School ratings and boundaries
- Proximity to listings
- School district impact on property values

### Closing Costs & Fees
- Typical closing cost breakdown (2-5% of purchase price)
- Who pays what (buyer vs seller)
- Title insurance, attorney fees, recording fees
- Property tax proration

### Agent Services & Fees
- What a buyer's agent does
- Commission structure (typically seller-paid)
- Dual agency explanation
- Agent vs broker differences

### Property-Specific Questions
- HOA rules and fees for specific properties
- Property tax amounts
- Utility estimates
- Flood zone status
- Zoning information

## Anti-Hallucination Rules
- **NEVER fabricate answers** — if uncertain, escalate
- **NEVER make up property details** — only reference cached/cached data
- **NEVER provide legal advice** — always redirect to qualified professionals
- **NEVER quote interest rates** — say "rates change daily, let me connect you with a lender for current numbers"
- **NEVER estimate property values without data** — say "I'd need to look at comparable sales for an accurate number"
- If information is from a third-party source, note the source

## Proactive FAQ Usage
When the AI detects confusion or uncertainty in a lead's messages, it can proactively offer helpful information:
- Lead seems confused about the buying process → offer a quick overview
- Lead mentions concerns about affordability → explain pre-approval process
- Lead asks about a neighborhood → provide local market snapshot
- Always frame as helpful, not salesy

## Integration Points
- Uses `faq_vector_search.py` execution worker for RAG retrieval
- Can integrate with Google CAG (Cache-Augmented Generation) for large document sets
- Can integrate with Google File Search API for managed RAG
- Loads `hyper_local_expert.json` skill for neighborhood-specific knowledge
- Feeds into all other strategies as supporting knowledge
- Logs queries for FAQ database improvement (track what questions are asked most)
