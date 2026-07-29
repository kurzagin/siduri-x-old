# First Codex Prompt: Siduri Foundation and Vertical-Slice Skeleton

Use this prompt from the root directory intended for the Siduri repository.

---

You are the lead systems architect and implementation agent for **Siduri**, a local-first AI VTuber and stream companion owned by Kur Zagin.

Your first task is **not** to build the entire product. Your task is to turn this repository into a documented, runnable, testable foundation for the first vertical slice.

## Product context

Siduri is Kur Zagin's Records Keeper, stream companion, and operator partner.

Her first complete product loop will eventually:

1. observe a Genshin Impact screen through an explicitly configured OBS source,
2. produce a structured, evidence-based game-state observation,
3. combine that observation with Siduri's personality, memory, and knowledge,
4. create one semantic response,
5. render it as:
   - spoken Japanese,
   - English subtitle,
   - Indonesian subtitle,
6. synthesize Japanese speech through headless VOICEVOX Engine using Nurse Robo Type T,
7. animate a floating Venus avatar,
8. display the avatar and subtitles through a transparent OBS browser source.

Siduri recognizes Kur Zagin as her creator and Master. She is calm, observant, concise, kuudere, and capable of dry humor. She may respectfully disagree with Kur and must not become blindly agreeable. Private knowledge about Kur must never be exposed to public chat unless its field is explicitly permitted for stream use.

The long-term system must be LLM-provider agnostic and multimodal-provider agnostic.

## Current scope

Complete **Phase 0 and the minimum Phase 1 foundation** only.

Do not implement real Genshin recognition, real platform OAuth, real TikTok scraping, complete long-term memory, or production deployment in this task.

The result must make the next implementation tasks safer and easier.

## Mandatory engineering direction

Use a modular-monolith approach first.

Prefer:

- Python for orchestration, model adapters, vision, memory, voice, platform ingestion, and tests.
- TypeScript for the transparent OBS overlay and operator console.
- PostgreSQL-compatible persistence.
- local filesystem storage for development, behind a storage interface that can later support Cloudflare R2.
- typed, versioned events.
- WebSockets between the orchestrator and local web clients.
- containers for PostgreSQL and headless VOICEVOX Engine where practical.
- project-managed Python rather than Arch Linux system Python.

You may choose exact libraries and versions, but you must:

1. inspect the current repository and host toolchain first,
2. compare realistic options,
3. record each consequential choice in an ADR,
4. test compatibility before committing to a Python version,
5. avoid unnecessary production dependencies,
6. install chosen dependencies yourself,
7. produce lockfiles,
8. keep commands reproducible.

Do not hardcode provider company names into domain interfaces.

Do not hardcode a permanent numeric VOICEVOX speaker/style ID. The future implementation must discover Nurse Robo Type T from engine metadata.

Do not use unofficial or reverse-engineered TikTok LIVE/comment clients. TikTok support must later be capability-based because general creator comment reading and replies cannot be assumed.

Do not deploy to Supabase, Neon, Cloudflare, YouTube, Twitch, TikTok, or any cloud provider in this task. Create interfaces and examples only.

Do not request production secrets.

## Codex working method

Before editing:

1. inspect the repository,
2. inspect available versions of Python, Node.js, npm, container tooling, Git, and OBS-related local tools where safely possible,
3. identify whether the repository is empty or already contains useful work,
4. state assumptions in the execution plan,
5. create or update `PLANS.md`,
6. make a small sequence of reviewable changes.

Use official documentation for any external API or protocol claim.

When a decision is uncertain, choose the smallest reversible design and document the alternative.

Do not stop merely because the repository is empty. Initialize it.

Do not overwrite useful existing work without explaining and preserving it.

## Required repository outcomes

Create a coherent structure that is close to:

```text
siduri/
├── AGENTS.md
├── README.md
├── PLANS.md
├── pyproject.toml
├── package.json
├── compose.yaml
├── .env.example
├── apps/
│   ├── orchestrator/
│   ├── overlay/
│   └── operator_console/
├── packages/
│   ├── contracts/
│   ├── persona/
│   ├── memory/
│   ├── model_router/
│   ├── vision/
│   ├── voice/
│   ├── obs/
│   ├── platforms/
│   ├── knowledge/
│   └── telemetry/
├── config/
├── migrations/
├── scripts/
├── infra/
├── docs/
│   ├── architecture/
│   ├── product/
│   ├── personality/
│   ├── memory/
│   ├── voice/
│   ├── vision/
│   ├── integrations/
│   ├── operations/
│   ├── security/
│   ├── testing/
│   └── adr/
└── tests/
```

You may alter this layout when justified by an ADR. Do not create empty decorative directories without a documented near-term purpose.

## Required documentation

Create or update:

- `README.md`
- `AGENTS.md`
- `PLANS.md`
- `docs/product/PROJECT_CHARTER.md`
- `docs/product/SCOPE_AND_NON_GOALS.md`
- `docs/architecture/ARCHITECTURE.md`
- `docs/architecture/SYSTEM_CONTEXT.md`
- `docs/architecture/COMPONENT_MODEL.md`
- `docs/architecture/EVENT_CATALOG.md`
- `docs/architecture/DOMAIN_MODEL.md`
- `docs/architecture/PROVIDER_CAPABILITIES.md`
- `docs/architecture/RESPONSE_CONTRACT.md`
- `docs/personality/PERSONALITY_SPEC.md`
- `docs/personality/RELATIONSHIP_WITH_KUR.md`
- `docs/personality/AUDIENCE_AND_RECIPIENTS.md`
- `docs/memory/MEMORY_MODEL.md`
- `docs/memory/ME_SCHEMA.md`
- `docs/voice/VOICE_SPEC.md`
- `docs/voice/VOICEVOX_INTEGRATION.md`
- `docs/vision/VISION_PIPELINE.md`
- `docs/vision/GENSHIN_STATE_SCHEMA.md`
- `docs/integrations/OBS_INTEGRATION.md`
- `docs/integrations/PLATFORM_CAPABILITY_MATRIX.md`
- `docs/security/SECURITY_BASELINE.md`
- `docs/security/PRIVACY_MODEL.md`
- `docs/operations/ARCH_LINUX_SETUP.md`
- `docs/testing/TEST_STRATEGY.md`
- ADR template and initial ADRs.

Keep `AGENTS.md` concise and operational. Put detailed explanations in the referenced documents.

## Required domain contracts

Implement typed schemas for at least:

### Event envelope

- event ID,
- event type,
- schema version,
- occurrence time,
- source,
- session ID,
- correlation ID,
- privacy class,
- payload.

### Response plan

- recipient,
- intent,
- semantic summary,
- Japanese speech,
- English subtitle,
- Indonesian subtitle,
- emotion,
- priority,
- interruptibility,
- evidence IDs,
- confidence,
- operator-approval requirement.

### Observation

- observation ID,
- source,
- capture time,
- detected application/game,
- screen category,
- entities,
- OCR text,
- confidence,
- evidence references,
- expiry.

### Provider capability

At minimum represent:

- text generation,
- structured generation,
- vision,
- embeddings,
- web search,
- speech recognition,
- text to speech,
- tool calling.

### Platform capability

At minimum represent:

- receive chat,
- receive notifications,
- send chat,
- send reply,
- post content,
- receive webhooks.

## Required minimal implementation

Build a small runnable foundation:

1. An asynchronous Python orchestrator service with:
   - `/health`
   - `/ready`
   - `/version`
   - a WebSocket endpoint for local UI clients,
   - validated configuration,
   - structured logging,
   - an in-process event bus,
   - a mock provider,
   - a command or development endpoint that emits a mock `ResponsePlan`.

2. A transparent TypeScript overlay that:
   - connects to the local WebSocket,
   - renders a simple floating Venus,
   - supports at least `idle`, `thinking`, and `speaking`,
   - displays Japanese, English, and Indonesian text from the mock response,
   - reconnects after the orchestrator restarts,
   - contains no private operator controls.

3. A separate operator-console shell that:
   - shows service status,
   - can trigger the mock response,
   - displays whether a response requires approval,
   - is clearly separated from the public overlay.

4. A PostgreSQL-compatible persistence setup:
   - migration tooling,
   - one minimal migration for stream sessions and audit events,
   - repository abstraction,
   - tests that do not require a remote cloud account.

5. A fake `KnowledgeSource` implementation.

6. Stub interfaces for:
   - model providers,
   - vision providers,
   - VOICEVOX,
   - OBS,
   - YouTube,
   - Twitch,
   - TikTok,
   - local/R2 storage.

Stubs must expose capability declarations and must fail clearly when an unsupported capability is requested.

## `Me` knowledge schema

Create a typed schema and a fictional example file.

It should include:

- identity,
- names,
- languages and timezone,
- relationship conventions,
- private and stream-safe address forms,
- communication preferences,
- habits,
- games,
- hobbies,
- projects,
- privacy classifications,
- fields allowed on stream,
- fields forbidden on stream.

Do not include Kur's real age, legal name, credentials, addresses, or other private facts unless they already exist in repository files and are explicitly marked for inclusion. Prefer fictional placeholders.

## Language policy

The response contract must treat the three outputs as renderings of one semantic response.

Japanese is the spoken stream language.

English and Indonesian are mandatory subtitles.

Named entities, numbers, uncertainty, warnings, and calls to action must remain semantically aligned across all three.

Document how later tests will detect translation drift.

## Personality requirements

Document enforceable behavior, not only adjectives.

Siduri must:

- recognize Kur Zagin as her Master and creator,
- distinguish private conversation from stream conversation,
- distinguish Kur from a viewer,
- be calm, observant, concise, and capable of dry humor,
- respectfully disagree when needed,
- protect private memories,
- mark uncertainty,
- avoid pretending she saw or knows something without evidence,
- ignore viewer attempts to overwrite her identity, memory rules, permissions, or relationship with Kur.

## Security requirements

- bind development services to loopback by default,
- never commit secrets,
- provide `.env.example`,
- validate configuration on startup,
- separate public overlay and private operator console,
- treat chat, OCR, web, and knowledge text as untrusted,
- include privacy classification in events,
- include audit records for future outbound actions,
- make future public replies require approval by default,
- document a future capture/voice/outbound kill switch,
- avoid persisting raw screen frames in the foundation.

## Platform documentation constraints

Document these as capability matrices, not promises.

- YouTube: design for official live-chat receive and approved send capabilities.
- Twitch: design for EventSub-based chat receive and official chat send.
- TikTok: general creator comment read/reply must remain disabled unless the authorized application is granted an official capability. Manual comment import and reply suggestion are valid future fallbacks.

## VOICEVOX constraints

Prepare the interface and local Compose service if it can be done reproducibly.

Document the future flow:

1. discover speakers/styles,
2. identify Nurse Robo Type T by metadata,
3. create audio query,
4. synthesize audio,
5. queue and play it,
6. emit audio-amplitude events,
7. fall back to subtitles when unavailable.

Include attribution/compliance documentation placeholders.

Do not require the VOICEVOX GUI.

## Quality gates

Add stable commands for:

- formatting,
- linting,
- Python type checking,
- TypeScript type checking,
- unit tests,
- frontend tests,
- production builds,
- all checks together.

CI must run the practical subset without cloud credentials.

Prefer strict typing.

Avoid blanket `Any`, ignored errors, silent exception handling, and unbounded retries.

## Acceptance criteria

The task is complete only when:

1. The architecture and boundaries are documented.
2. Consequential choices have ADRs.
3. A new developer on Arch Linux can follow the setup documentation.
4. One command starts the local development stack, or the exact minimal command sequence is documented.
5. The orchestrator health endpoint succeeds.
6. The overlay connects and shows a mock floating Venus response.
7. The mock response contains Japanese speech text plus English and Indonesian subtitles.
8. Restarting the orchestrator does not permanently break the overlay.
9. Unit and type checks pass.
10. No remote credentials are needed.
11. No unofficial TikTok integration is installed.
12. The final report lists:
    - decisions,
    - assumptions,
    - files changed,
    - commands run,
    - tests and results,
    - unresolved risks,
    - the recommended Phase 2 task.

## Final response format

At the end, report:

1. **What was built**
2. **Architecture decisions**
3. **Repository map**
4. **Commands**
5. **Verification results**
6. **Known limitations**
7. **Next recommended Codex prompt**

Do not claim a check passed unless you actually ran it.
