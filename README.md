# Crucible

Crucible is an AI-powered multi-agent debate workspace for reviewing complex project files. It ingests documents and 3D assets, generates a tailored panel of specialist agents, runs a live adversarial discussion, and produces a concise judge verdict so users can pressure-test an idea before they build it.

## What it does

Crucible turns a static project upload into an interactive review process:

- Upload one or more files, including text documents and supported 3D model files.
- Extract and merge the input into a unified project context.
- Use an LLM-driven architect flow to generate a relevant debate roster.
- Keep two anchor agents constant: a failure-side critic and a success-side defender.
- Run a streamed multi-round debate in the browser.
- Produce a short, structured verdict with strengths, risks, actions, and a score.

This makes the project useful for early design review, technical due diligence, capstone demonstrations, and internal concept validation.

## Why this project exists

Most project reviews happen in one of two weak modes: either a single person scans a document and misses edge cases, or a team review takes too long and is hard to reproduce. Crucible tries to bridge that gap by creating an on-demand panel of AI specialists that can challenge assumptions from multiple angles while still giving the user a clean final decision.

Instead of behaving like a general chatbot, the system is built around adversarial reasoning. That means the value comes from disagreement, rebuttal, and synthesis rather than just summarization.

## Key features

- **Multi-file analysis**: combines multiple uploaded inputs into one review context.
- **3D-aware intake**: includes 3D file uploads in the extracted project context so physical design artifacts are not ignored.
- **Dynamic agent generation**: creates document-specific specialists instead of using the same generic roster every time.
- **Fixed debate anchors**: always includes a failure advocate and a success advocate for consistent tension.
- **Streaming debate UI**: users see arguments appear live, round by round.
- **Custom agent editing**: generated agents can be removed, adjusted, or supplemented manually.
- **Short verdicts**: the judge output is intentionally compressed so the user gets signal without too much fluff.
- **Light/dark theme support**: simple UI theme toggle without local storage dependency.

## How it works

### 1. File intake

The frontend accepts one or more uploaded files. These are sent to the Flask backend using multipart form data.

Supported project inputs include:

- PDF
- DOCX
- TXT / Markdown / plain text
- CSV and other decodable text files
- 3D files such as STL, OBJ, GLTF, GLB, PLY, 3MF, STEP, and STP

### 2. Document extraction and merge

The backend extracts text from text-based files and builds a merged project context. Each file is wrapped with a labeled separator so the model can tell which content came from which source.

For multi-file uploads, the merged context includes a manifest header listing all supplied files. This helps the model understand that the project is being reviewed as a bundle rather than as a single isolated document.

### 3. Agent architecture

Crucible uses a two-part debate roster:

- **Fixed agents**
  - Devil's Advocate: argues the project will fail.
  - Champion: argues the project will succeed.
- **Dynamic specialists**
  - Generated from the uploaded project context.
  - Intended to vary based on the actual domain of the submission.
  - Focused on the most relevant review lenses for that specific project.

This structure keeps the debate consistent while still allowing domain-specific depth.

### 4. Debate engine

The debate runs in three stages:

1. Opening statements.
2. Cross-examination rounds.
3. Judge verdict.

Each agent speaks in very short turns so the conversation reads like a real exchange instead of long walls of text. Debate messages are streamed to the browser using Server-Sent Events, which makes the interaction feel live and transparent.

### 5. Judge synthesis

After the debate, a higher-capability model produces a structured final verdict with:

- Verdict
- Strengths
- Risks
- Actions
- Score

The verdict is designed to be short but evidence-driven, giving the user a decision summary without overwhelming them.

## Tech stack

### Backend

- Python
- Flask
- Flask-CORS
- Groq Python SDK
- PyPDF2
- python-docx
- python-dotenv

### Frontend

- HTML
- CSS
- Vanilla JavaScript
- Server-Sent Events for streamed debate updates

### Model roles

- Fast model for agent turns
- Stronger model for document analysis and the final judge verdict

## Project structure

```text
.
├── app.py
├── requirements.txt
├── core/
│   ├── __init__.py
│   ├── agent_factory.py
│   ├── debate_engine.py
│   ├── document_parser.py
│   └── groq_client.py
├── routes/
│   ├── __init__.py
│   └── api.py
└── static/
    ├── index.html
    ├── css/
    │   └── style.css
    └── js/
        ├── api.js
        ├── main.js
        ├── state.js
        └── ui.js
```

## Core modules

### `app.py`

Creates the Flask app, registers the API blueprint, serves the frontend, and starts the development server.

### `core/document_parser.py`

Handles extraction from supported file types. Text-based files are converted into plain text for downstream reasoning.

### `core/agent_factory.py`

Generates the debate roster from the uploaded project context. The intended behavior is:

- tailor specialists to the project,
- keep the failure and success agents consistent,
- and avoid returning the exact same specialist list every time.

### `core/debate_engine.py`

Runs the adversarial debate, streams messages as SSE events, and requests the final judge verdict.

### `core/groq_client.py`

Wraps the Groq SDK and manages runtime API key configuration.

### `routes/api.py`

Exposes the backend endpoints for API key setup, analysis, and debate streaming.

## API overview

### `POST /api/set-key`

Stores a Groq API key in memory for the running server process.

Request body:

```json
{
  "api_key": "gsk_..."
}
```

### `POST /api/analyze`

Accepts uploaded files, extracts and merges content, and returns the generated roster.

Response shape:

```json
{
  "document_text": "...",
  "document_type": "...",
  "project_summary": "...",
  "agents": [],
  "file_count": 2,
  "file_names": ["spec.pdf", "model.obj"]
}
```

### `POST /api/debate`

Starts the live debate and streams results as Server-Sent Events.

Request body:

```json
{
  "document_text": "...",
  "agents": [],
  "rounds": 3
}
```

SSE event types:

- `phase`
- `message`
- `verdict`
- `error`
- `done`

## Local setup

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd crucible
```

### 2. Create a virtual environment

```bash
python -m venv .venv
```

Activate it:

```bash
# macOS / Linux
source .venv/bin/activate

# Windows PowerShell
.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure your Groq API key

You can either:

- set `GROQ_API_KEY` in a `.env` file, or
- launch the app and paste the key into the UI.

Example `.env`:

```env
GROQ_API_KEY=your_groq_key_here
HOST=0.0.0.0
PORT=5000
FLASK_ENV=development
```

### 5. Run the app

```bash
python app.py
```

Then open:

```text
http://localhost:5000
```

## How to use

1. Open the app in the browser.
2. Enter a Groq API key if one is not already set in `.env`.
3. Upload one or more files.
4. Click **Analyze Document**.
5. Review the extracted text and generated agents.
6. Add or remove agents if needed.
7. Click **Run Debate**.
8. Watch the live debate stream.
9. Read the final verdict in the right-side panel.

## Demo flow for a hackathon video

A clean 5-minute demo can follow this structure:

1. Show the problem: project reviews are slow, shallow, or inconsistent.
2. Upload a mixed project bundle, such as a PDF plus a 3D model.
3. Show agent generation and explain why the roster is relevant.
4. Run the live debate and let a few rounds play out.
5. Show the final verdict and score.
6. End with why adversarial multi-agent reasoning is more useful than plain summarization.

## Recommended hackathon framing

Crucible fits best in **Freestyle**, and it can also fit **Agents for Business** if positioned as a review assistant for technical, product, or design teams.

A strong framing is:

> Crucible is an AI multi-agent review system that pressure-tests complex project submissions by generating specialist agents, staging a structured adversarial debate, and producing a concise decision-ready verdict.

## Concepts demonstrated

This project can credibly claim the following course-aligned ideas:

- **Agent / multi-agent system**: the core product is a multi-agent debate engine.
- **Security awareness**: the API key is held in memory rather than hardcoded into source files.
- **Deployability**: the app is a simple Flask service with a static frontend and reproducible local setup.
- **Agent skills / specialization**: the architecture differentiates between dynamic specialists and fixed anchor roles.

If additional Kaggle course concepts such as MCP Server, Antigravity, or ADK-specific implementation are required explicitly, they should be called out carefully and only if they are truly present in the final codebase.

## Design choices

### Why adversarial debate?

A single-agent summary tends to flatten uncertainty. An adversarial structure forces trade-offs into the open and makes the final verdict more explainable.

### Why fixed success and failure anchors?

Keeping those two roles stable gives every debate a reliable tension structure. That makes outputs easier to compare across projects.

### Why dynamic specialists?

The same static expert panel is rarely appropriate across very different project types. Crucible is stronger when the specialist layer adapts to the uploaded files.

### Why short messages?

Long paragraph-sized turns overwhelm the user and make the live debate hard to follow. Short turns make the exchange feel more like a real design review.

## Limitations

- Quality depends on the quality of extracted text.
- Some 3D formats may contribute less semantic detail than richly documented text files.
- Verdict calibration is only as good as the prompting and the evidence surfaced during debate.
- The system is an analysis aid, not a substitute for human engineering review.
- Large or noisy uploads may require better chunking or retrieval in future versions.

## Future improvements

- Better 3D metadata extraction and geometry-aware summaries.
- Richer judge scoring methodology.
- Saved sessions and exportable reports.
- Team collaboration and shared review links.
- More explicit evidence citations in each agent message.
- Optional retrieval augmentation for larger project bundles.
- Side-by-side comparison between multiple candidate designs.

## Safety and security notes

- Do not commit real API keys.
- Keep `.env` out of version control.
- The backend should validate uploads and apply size limits in production.
- For deployment, add authentication, rate limiting, and structured logging.

## Submission checklist

Before publishing the hackathon submission, make sure the repository includes:

- A polished `README.md`
- Setup steps that actually work
- A short architecture diagram or screenshot set
- A public demo link or reproducible local demo path
- A 5-minute or shorter YouTube video
- A Kaggle writeup under 2,500 words

## License

Add your preferred open-source license here, such as MIT.