# ServiceMitra Bot: A-to-Z Project Walkthrough

This document explains the full project from top to bottom so a new developer can understand what the system does, how it works, and where each important file belongs.

---

## 1. What this project is

ServiceMitra AI is a multilingual, voice-first government scheme assistant for India. It runs through Telegram and helps citizens discover welfare schemes, evaluate eligibility, and understand application steps.

The system combines:
- Telegram chat interactions
- Deterministic Python-based scheme matching
- Gemini-based language processing and parsing
- Sarvam AI speech-to-text and text-to-speech
- A scraped and validated scheme dataset
- A new multi-agent orchestration layer plus MCP tool server

The key idea is simple:
- The bot collects profile information from the user.
- It filters schemes based on state/applicability.
- It checks eligibility using deterministic rules.
- It returns a scheme shortlist and relevant details.
- It can support multilingual text and voice interaction.

---

## 2. Project structure overview

```text
SeviceMitraBot/
├── README.md
├── PROJECT_WALKTHROUGH.md
├── bot.py
├── config.py
├── mcp_server.py
├── mcp_client.py
├── requirements.txt
├── agents/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── schemas.py
│   └── specialists.py
├── services/
│   ├── eligibility_service.py
│   ├── gemini_service.py
│   └── voice_service.py
├── scraper/
│   ├── umang_scraper.py
│   └── validate_schemes.py
├── utils/
│   └── session.py
├── data/
│   ├── categories.json
│   ├── schemes.json
│   ├── schemes_test.json
│   └── raw/
│       ├── rtif_full.json
│       ├── stpss_full.json
│       ├── umang_raw_schemes.json
│       └── wbisaito_full.json
├── scratch/
│   └── test_eligibility.py
├── temp/
│   └── generated TTS files
└── .env
```

---

## 3. How the app starts

The main entry point is:
- `bot.py`

When launched, it:
1. Loads environment variables via `config.py`
2. Reads the scheme dataset from `data/schemes.json`
3. Initializes logging
4. Registers Telegram handlers
5. Starts polling for user messages and button clicks

The app is designed to start using:

```bash
python bot.py
```

---

## 4. Configuration layer

File: `config.py`

This file contains all central settings such as:
- Telegram bot token
- Gemini API key
- Sarvam AI API key
- supported languages
- state names
- sector categories
- eligibility question options
- age/income ranges

This file is the single source of truth for:
- bot configuration
- supported Indian states
- option lists for age, occupation, education, income, etc.
- conversational state names

Why it matters:
- It prevents hardcoding values across the codebase.
- It keeps the bot easy to extend.
- It is the place you adjust if you add a new state, language, or field.

---

## 5. Telegram flow: how the bot talks to users

The Telegram app lives in `bot.py`.

### Core responsibilities
- `/start` command handler
- language selection screen
- sector selection menu
- questionnaire flow for profile collection
- profile confirmation page
- scheme list page
- scheme details page
- voice help generation
- callback-button processing for all interactive UI actions

### Bot behavior
The bot uses Telegram inline keyboards and callback data like:
- `language:hi`
- `category:3`
- `scheme:abc123`
- `action:check_schemes`
- `edit_field:state`

This makes the chatbot feel more app-like and avoids forcing users to type long responses.

---

## 6. Session and memory management

File: `utils/session.py`

This module stores the in-memory user profile and conversation state.

Each user has a session dictionary with keys like:
- language
- state
- profile
- selected_category
- eligible_schemes
- selected_scheme
- current_question_index
- questions_to_ask

Each user profile stores fields such as:
- age
- gender
- occupation
- annual_income
- state
- social_category
- education
- exact_age
- disability_percentage
- bpl_status
- widow_status
- land_ownership
- minority_status
- student_year
- domicile

This is the bot’s short-term memory during a live Telegram conversation.

Important limitation:
- It is in-memory only.
- Restarting the bot clears sessions.
- This is acceptable for an MVP but not production-grade persistence.

---

## 7. Data model: schemes and categories

The data files are located under `data/`.

### `data/schemes.json`
This is the main government scheme dataset. Each scheme contains fields like:
- id
- name
- category
- description
- eligibility
- applicability
- benefits
- documents
- source metadata

### `data/categories.json`
This stores the top-level sectors or categories used by the bot UI.

### `data/raw/`
Contains raw scraped or source JSON used to build the normalized dataset.

---

## 8. Scraper and dataset generation

Directory: `scraper/`

### `scraper/umang_scraper.py`
This script crawls public UMANG scheme data and builds the dataset.

What it does:
1. Pulls scheme list information
2. Downloads scheme detail pages or API records
3. Extracts benefits, eligibility, documents, and official links
4. Uses Gemini to parse complex eligibility text
5. Normalizes categories and states
6. Merges duplicate schemes
7. Saves the final dataset to `data/schemes.json`

### `scraper/validate_schemes.py`
This checks the data quality and ensures the scraped scheme dataset matches the project’s required integrity rules.

It validates:
- duplicates
- missing required fields
- malformed eligibility objects
- invalid ranges
- contradictory state registrations

---

## 9. Deterministic core: eligibility engine

File: `services/eligibility_service.py`

This is the real decision engine that powers scheme matching.

### Why it matters
This module is the “source of truth” for whether a user is eligible for a scheme.

It handles:
- state applicability
- age range checks
- income threshold checks
- gender matches
- occupation matching
- education matching
- social category checks
- dynamic conditions like single girl child, disability, BPL status, widow status, etc.

### Important functions
- `normalize_state()`
- `normalize_category()`
- `normalize_profile()`
- `normalize_scheme_data()`
- `is_scheme_applicable_to_state()`
- `evaluate_scheme()`
- `find_matching_schemes()`
- `get_next_missing_field()`

### Example logic
A scheme can be:
- `eligible`
- `ineligible`
- `possible_match`

This makes the bot conservative and explainable. It never invents a scheme fit; it only matches when actual criteria support it.

---

## 10. Gemini language and extraction layer

File: `services/gemini_service.py`

This service uses the Google GenAI SDK to:
- extract profile values from user text
- translate text into Hindi, Telugu, Tamil, Kannada
- summarize a scheme for voice output
- parse raw scheme eligibility text during scraping

### Example use cases
- User says: “I am 24 years old and live in Karnataka”
- Gemini extracts:
  - age = 24
  - state = Karnataka

### Schema-based parsing
The file defines Pydantic models such as:
- `ExtractedProfile`
- `StructuredEligibility`
- `StateApplicability`

This helps keep outputs structured instead of raw free text.

---

## 11. Voice layer: Sarvam AI

File: `services/voice_service.py`

This connects to the Sarvam AI APIs for:
- text-to-speech (TTS)
- speech-to-text (STT)

### Responsibilities
- send text to Sarvam and save MP3 output
- convert user audio messages into text
- cache generated voice files
- clean expired temp files

### Why it matters
This is what gives the app voice-first capability and lets users interact using audio instead of only typed messages.

---

## 12. New multi-agent architecture

The project now includes a structured agent layer under `agents/`.

### Why this exists
The original bot works well as a rule-driven assistant. The new multi-agent layer adds:
- explicit supervisor logic
- specialty agent separation
- tool-use structure
- Pydantic schemas
- safer orchestration boundaries

### Files in the new layer

#### `agents/orchestrator.py`
This is the main orchestration coordinator.

It decides which workflow to use based on the message and user state.

Supported agent/workflow names:
- `supervisor`
- `scheme_research`
- `eligibility`
- `verification`
- `language`
- `fallback`

#### `agents/specialists.py`
This contains specialist implementations:
- `SchemeResearchAgent`
- `EligibilityAgent`
- `VerificationAgent`

#### `agents/schemas.py`
This contains typed models for:
- agent decisions
- verification results
- final responses
- conversation state
- tool-call tracing

This adds structure and validation to the logic instead of relying on loose dictionaries.

---

## 13. MCP tool server

File: `mcp_server.py`

This is a dedicated FastMCP server for exposing narrow, safe tools.

### Why it was added
The project needed a clean tool layer that can be used by an LLM or a future MCP-based client.

### Tools exposed
- `search_schemes`
- `get_scheme_details`
- `get_user_profile`
- `update_user_profile`
- `check_eligibility`
- `validate_scheme_data`
- `save_eligibility_result`

### Design principles
- typed inputs and outputs
- limited scope
- no arbitrary Python execution
- no unrestricted SQL execution
- explicit field allowlisting for profile updates
- structured results instead of raw strings

### How to start it
```bash
python mcp_server.py
```

---

## 14. MCP client

File: `mcp_client.py`

This is a small wrapper for external clients that want to connect to the MCP server over stdio.

It is designed so another tool-enabled agent or external app can call the same ServiceMitra tools without directly importing all the bot logic.

---

## 15. Bot flow in real life

Here is the actual user journey.

### Step 1: Start
User sends `/start`.

The bot resets the session and asks for language preference.

### Step 2: Choose language
User selects Hindi, Telugu, Tamil, Kannada, or English.

The bot updates the session language and displays the sectors menu.

### Step 3: Choose sector
User picks a category like:
- Education & Learning
- Agriculture, Rural & Environment
- Health & Wellness
- Social Welfare & Empowerment
- Business & Entrepreneurship

### Step 4: Answer questions
The bot asks profile questions such as:
- age range
- gender
- occupation
- annual income
- education
- social category
- state

### Step 5: Evaluate and shortlist
The bot uses the deterministic eligibility service to filter `$eligible`, `$possible_match`, and `$ineligible` results.

### Step 6: Show schemes
The user sees scheme cards or buttons and can open the relevant scheme.

### Step 7: Review details
The bot shows:
- benefits
- eligibility checklist
- required documents
- application steps
- official website links

### Step 8: Voice help
If the user taps the voice help button, the bot generates a regional-language voice summary.

---

## 16. What is deterministic and what is AI-driven?

### Deterministic parts
These parts are rule-based and stable:
- eligibility evaluation
- state applicability checks
- income/age matching logic
- scheme filtering

### AI-assisted parts
These parts use Gemini or external APIs:
- entity extraction from user text
- translation to regional languages
- scheme summarization
- raw text parsing during scraping

This split is important because it makes the system both practical and reliable.

---

## 17. Current limitations

The project is strong as an MVP and portfolio-ready demo, but it still has real limitations:

- Sessions are in memory only.
- No real database persistence yet.
- No user authentication layer for production.
- MCP layer is structured but not yet plugged into a production-grade LLM loop.
- Bot is Telegram-specific.
- Scheme dataset depends on external scraped sources.

These are reasonable for a working prototype and are clear future upgrade targets.

---

## 18. Good extension points

If you want to keep improving this project, the best next steps are:

1. Add a PostgreSQL persistence layer for users and eligibility results.
2. Add a proper LLM agent loop via a provider with tool calling enabled.
3. Integrate the MCP server to a real AI client.
4. Add admin dashboards or evaluation tooling.
5. Add structured logs and analytics for usage and match quality.
6. Add authentication and user safety rules.

---

## 19. Summary

ServiceMitra is a government scheme discovery assistant that combines:
- Telegram UX
- deterministic eligibility rules
- AI-based parsing and translation
- voice support
- MCP-based tool architecture
- multi-agent orchestration for future expansion

It is valuable because it does not rely on vague AI guesswork alone. The core scheme matching remains deterministic and explainable, while the AI layer supports user understanding and translation.

That balance is what makes the project portfolio-ready and practically useful.
