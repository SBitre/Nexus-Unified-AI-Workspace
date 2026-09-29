# Nexus — Unified AI Workspace Assistant

Ask one question, get answers across Gmail, Calendar, Notion and Slack.

Nexus is an AI assistant that sits on top of the tools people already use and answers or acts on plain-English requests across all of them. Instead of checking four apps to work out what's due this week, you ask once and get a single answer assembled from every connected service.

> **Status:** Early development. This repository currently holds coursework deliverables and design artifacts; the application backend has not been built yet. See [Roadmap](#roadmap).

---

## The problem

People work across many disconnected tools — email, calendar, notes, task boards, team chat — that don't talk to each other. Answering something as simple as *"what's due this week?"* means opening several apps and reassembling the answer by hand. The constant context-switching wastes time and lets things slip.

## The approach

A single natural-language interface backed by an AI agent that decides which services to query, calls each one through its REST API, and merges the results into one answer.

Each integration is a **self-contained plugin** registered at runtime. Adding a new service means writing one plugin — no changes to the agent core.

```
Chat UI
   ↓
AI agent  ──  intent parsing, plugin selection
   ↓
Plugin registry
   ↓
Service plugins  ──  Gmail · Calendar · Notion · GitHub · Slack
   ↓
Aggregation and response
```

## Planned features

| Feature | Description |
|---|---|
| Cross-tool query | One question, answered from multiple services at once |
| Plugin registry | Integrations discovered and loaded at runtime |
| Agent trace view | Shows which plugins were called, why, and how long it took |
| Connection manager | OAuth setup and status for each connected service |
| Entity resolution | Recognises when an email, an event and a task refer to the same thing |
| Confirmed write-actions | Create tasks or send replies, always behind an explicit confirmation |
| Scheduled digests | Automated cross-tool summaries via a low-code workflow layer |

## Planned tech stack

- **Backend:** Python, FastAPI
- **LLM:** Google Gemini (free tier), with Groq as a tested fallback
- **Agent:** Native function calling
- **Integrations:** Gmail, Google Calendar, Notion, GitHub, Slack — REST APIs with OAuth
- **Low-code layer:** n8n, for scheduled and event-triggered workflows
- **Frontend:** HTML / CSS / JavaScript
- **CI:** GitHub Actions

## Repository structure

```
.
├── labs/
│   └── lab2-ui/
│       ├── v1/              # Baseline MVP (Lab 1)
│       └── v2/              # Accessibility and responsive enhancements (Lab 2)
├── explorations/
│   └── ai-assisted-v1/      # Early AI-assisted restyle of V1, not a submission
├── docs/
│   └── design/              # Figma exports, wireframes, design annotations
└── README.md
```

The application code will live at the repository root once development begins.

## Running the front-end

No build step or dependencies. Open the `index.html` file inside any version folder directly in a browser:

```bash
open labs/lab2-ui/v1/index.html
```

## Roadmap

- [x] V1 baseline MVP
- [ ] AI-assisted design prototype (Figma)
- [ ] V2 with accessibility and responsive improvements
- [ ] Plugin interface and registry
- [ ] First service integration with OAuth
- [ ] Agent loop and plugin routing
- [ ] Evaluation harness for routing accuracy
- [ ] Remaining integrations
- [ ] Trace view and connection manager
- [ ] Scheduled digests via n8n

## Known constraints

- **Google restricted scopes.** Gmail and Calendar access is classified as restricted, so the app runs in testing mode with team accounts rather than being publicly deployed.
- **Slack read limits.** History-reading methods are rate-limited for apps distributed outside the Slack Marketplace. Nexus is built as an internal workspace app, which is exempt.
- **Free-tier LLM quotas.** Daily request allowances vary sharply between model variants and change over time. Development runs against a lighter model; quotas are re-checked before each build phase.

## Team

Group project for Final Assessment 2: Group Application Development.

| Name | Role |
|---|---|
| Sumukh Sachin Pitre | Integrations and infrastructure — plugin architecture, OAuth, service APIs |
| _[teammate]_ | AI and backend — intent parsing, orchestration, evaluation |
| _[teammate]_ | Frontend and product — UI, design, documentation |

## Academic note

Coursework for a graduate Informatics module at Northeastern University. Use of generative AI tools is disclosed in the accompanying assignment reflections.

## License

MIT — see [LICENSE](LICENSE).