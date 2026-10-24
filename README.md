# ServiceMitra AI 🇮🇳

ServiceMitra AI is a multilingual, voice-first government scheme assistant for India, built to run as a Telegram Bot. It is designed to assist citizens in finding eligible welfare schemes across different sectors (Education, Agriculture, Health, etc.) in their local language, utilizing both text and voice interfaces.

---

## Architecture Overview

```
                        +----------------------+
                        |     Telegram App     |
                        +----------+-----------+
                                   ^
                                   | (Text / Voice / Buttons)
                                   v
                        +----------+-----------+
                        |        bot.py        | <---+ (In-Memory Session Store)
                        +----+-------------+---+     |
                             |             |         +---> session.py
         (Deterministic Match)             | (Voice Files)
                             v             v
                +------------+---+     +---+------------+
                | eligibility_     |     | voice_service. |
                |   service.py   |     |     py (Sarvam) |
                +----------------+     +----------------+
                             ^             ^
                             | (Translation| STT / TTS)
                             v             v
                        +----+-------------+---+
                        |   gemini_service.py  |
                        +----------------------+
```

The system components are decoupled as follows:
- **Telegram Bot (`bot.py`)**: Manages the conversation flow, registers handlers for polling, and coordinates interaction.
- **Session Utilities (`utils/session.py`)**: Tracks in-memory conversation state, user profile parameters, and the questionnaire flow.
- **Eligibility Matching (`services/eligibility_service.py`)**: Evaluates user profile attributes against scheme criteria using deterministic python filtering.
- **Voice Integrations (`services/voice_service.py`)**: Interfaces with Sarvam AI REST endpoints to convert incoming voice messages to text (STT) and output texts to spoken regional language files (TTS).
- **Gemini Assistant (`services/gemini_service.py`)**: Uses Gemini 2.5 Flash to dynamically translate English scheme details to regional languages, extract profile criteria from conversational inputs, and generate natural-sounding voice summaries.
- **Crawler/Scraper (`scraper/umang_scraper.py`)**: Robust browser-first Playwright crawler that queries the public UMANG Scheme API, extracts detailed content, automates category and state applicability mapping, structures eligibility via Gemini, and compiles the scheme database.
- **Scheme Validator (`scraper/validate_schemes.py`)**: Utility script to validate schemes dataset integrity, checking for duplicates, missing keys, malformed ranges, or state contradictions.

---

## MVP Features

- **Multilingual Support**: Supports English, Hindi, Telugu, Tamil, and Kannada (`en-IN`, `hi-IN`, `te-IN`, `ta-IN`, `kn-IN`).
- **Optional Voice UI**: In standard chat flows, bot responses are text and buttons only. Spoken regional audio notes are delivered only when the user clicks the explicit `[🔊 Voice Help]` button or replies with a voice message, optimizing speed and bandwidth.
- **🔊 Voice Help Button**: A dedicated help utility on all screens that reads out the current conversational context in the user's selected language using a concurrent-click guard.
- **Button-First Navigation**: Streamlines interactions using callback keyboards for sectors and eligibility criteria to minimize typing.
- **Two-Stage State Filtering**: Screens schemes dynamically by matching user state applicability first (excluding unknown scopes), and checking profile eligibility parameters second.
- **Leakage Prevention**: Includes strict pre-display assertions to ensure no state leakage occurs.
- **Gemini Input Parser**: Automatically extracts profile parameters from free-text messages (e.g., "I am 24 and live in Karnataka").
- **Robust Scraper**: Automates schemes discovery and detail extraction from UMANG (`web.umang.gov.in`) utilizing public API calls.

---

## Installation

1. **Clone or navigate to the directory**:
   ```bash
   cd SeviceMitraBot
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install Playwright browsers**:
   ```bash
   playwright install
   ```

---

## Environment Setup

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Populate the `.env` file with your credentials:
   ```env
   TELEGRAM_BOT_TOKEN=1234567890:ABCdefGhIJKlmNoPQRsTUVwxyZ
   GEMINI_API_KEY=AIzaSy...
   SARVAM_API_KEY=your_sarvam_subscription_key
   ```
   > [!IMPORTANT]
   > Do NOT commit `.env` to Git. It is listed in `.gitignore` by default.

### Telegram BotFather Setup
1. Open Telegram and search for `@BotFather`.
2. Send `/newbot` and follow the instructions to set the bot's name and username.
3. Copy the HTTP API token provided by BotFather and paste it as `TELEGRAM_BOT_TOKEN` in `.env`.

---

## How to Run

### 1. Scrape Scheme Data
To crawl the schemes database dynamically from UMANG:

To run in debug mode (interactively logs the browser session to verify portal selectors and network configurations):
```bash
python scraper/umang_scraper.py --debug
```

To run a test crawl limited to a specific number of records (e.g. 10):
```bash
python scraper/umang_scraper.py --limit 10
```

To run the full crawl:
```bash
python scraper/umang_scraper.py
```

This script:
1. Discovers the complete welfare schemes catalog from the UMANG Schemes list API.
2. Iterates and fetches detailed descriptions, benefits, required documents, application steps, and reference links via the public details API.
3. Skips already cached entries to support resume capabilities (unless `--force` is used).
4. Structures complex eligibility text using Gemini.
5. Merges duplicate schemes and normalizes their applicability states.
6. Generates `data/schemes.json` and `data/categories.json` for the Telegram bot.

### 2. Validate Scraped Scheme Data
Ensure that all crawled items are valid and match the required schema:
```bash
python scraper/validate_schemes.py
```

### 3. Start the Telegram Bot
Launch the bot once data files are compiled:
```bash
python bot.py
```
The bot will run in polling mode. Open Telegram, search for your bot username, and send `/start` to begin.

### 4. Start the FastMCP Tool Server
The repository now includes a dedicated tool server for scheme search, eligibility evaluation, profile updates, and validation:
```bash
python mcp_server.py
```
This starts the ServiceMitra MCP server over stdio transport for compatible MCP clients.

### 5. Use the Agent Orchestration Layer
The multi-agent orchestration package is available in `agents/` and exposes a bounded supervisor + specialist workflow:
```bash
python -c "from agents import AgentOrchestrator, ConversationState; print(AgentOrchestrator().decide_agent('am I eligible for a scholarship', ConversationState(user_id='demo')).selected_agent)"
```
This keeps the original Telegram flow intact while allowing a future adapter to call the same agent logic via MCP or a provider-backed LLM loop.

---

## Multi-Agent + MCP Architecture

The project now contains a layered architecture that preserves the working bot while exposing a structured tool layer:

- `agents/` — supervisor or specialist workflow, Pydantic schemas, and bounded orchestration logic.
- `mcp_server.py` — FastMCP tool server with typed scheme and eligibility tools.
- `mcp_client.py` — stdio-based client wrapper for connecting external MCP clients.
- `services/eligibility_service.py` — deterministic scheme filtering and matching logic used by the MCP tools and bot.

The exposed tool names are:
- `search_schemes`
- `get_scheme_details`
- `get_user_profile`
- `update_user_profile`
- `check_eligibility`
- `validate_scheme_data`
- `save_eligibility_result`

These tool definitions are intentionally narrow and do not expose arbitrary SQL or Python execution.

---

## What is the new multi-agent system?

The new multi-agent layer is a bounded orchestration design built on top of the working Telegram bot. It is not a rewrite of the app; it is an extension that adds explicit agent responsibilities without removing the proven deterministic logic.

### Supervisor Agent
- Understands the incoming user intent.
- Decides whether the request is about scheme search, eligibility checking, verification, or language/voice support.
- Maintains typed conversation state and routes work to the correct specialist.
- Keeps tool usage bounded and safe.

### Scheme Research Agent
- Searches the validated scheme dataset.
- Pulls matching scheme details and metadata.
- Distinguishes actual verified data from missing or uncertain information.

### Eligibility Agent
- Uses the deterministic eligibility engine from `services/eligibility_service.py`.
- Evaluates user profile against scheme rules.
- Separates eligible, ineligible, and incomplete cases.

### Verification Agent
- Checks whether the final answer has evidence.
- Flags unsupported claims, missing evidence, or contradictions.
- Prevents false claims about source verification.

### Language / Voice capability
- Reuses the existing Gemini translation and Sarvam TTS/STT implementations.
- Keeps the original Telegram voice workflow working while allowing agent-aware language handling.

In short: the bot still uses the reliable deterministic scheme engine, and the new multi-agent layer adds a clean orchestration and tool-calling structure for future AI-driven expansions.

---

## Example User Flow

1. User sends `/start` -> Bot resets session and displays language options (English, Hindi, Telugu, Tamil, Kannada).
2. User selects **Telugu** -> Bot welcomes user with a Telugu voice note and presents available sectors.
3. User selects **Education & Learning** -> Bot queues relevant questions (Occupation, Age, Income, Education level, Social Category, State).
4. User selects choices via inline buttons, or types/sends a voice message ("నేను విద్యార్థిని" / "I am a student") -> Gemini extracts values and updates the profile.
5. Bot evaluates eligibility -> Displays matching schemes (e.g., "MJPJAY", "PM-KISAN") filtered by selected State.
6. User clicks `[🔊 Voice Help]` -> Bot plays a regional voice summary of the current screen context.
7. User clicks a scheme -> Shows details grid (Benefits, Eligibility checklist, Required Documents, Apply Steps, Official website link).
8. User selects **Benefits** -> Bot displays the translated benefits text.

---

## MVP Limitations

- **In-Memory Sessions**: User profiles are stored in-memory. Restarting `bot.py` resets active sessions.
- **Local Storage**: Schemes are cached in `data/schemes.json` locally.
- **Telegram Only**: Communication is restricted to Telegram.
- **Scraper Stability**: The scraper relies on the public UMANG Scheme API gateway. If the gateway endpoint or request headers are updated, the scraper settings may require maintenance.
- **No Application Submission**: The bot details how to apply and links to external portals, but does not submit applications or track real-time status.
