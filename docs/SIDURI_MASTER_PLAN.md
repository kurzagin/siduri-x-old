# Siduri Master Plan

**Project:** Siduri  
**Owner / Master:** Kur Zagin  
**Primary environment:** Arch Linux  
**Primary streaming target:** OBS Studio  
**Primary demonstration target:** Genshin Impact  
**Document status:** Architecture baseline and phased implementation plan

---

## 1. Executive direction

Siduri should be built as a **local-first, event-driven AI VTuber system**, not as one large chatbot process.

The first useful version must form one complete vertical loop:

1. Observe the game screen through an explicit capture source.
2. Convert visible evidence into a structured game-state observation.
3. Combine that observation with Siduri's personality, memories about Kur Zagin, current conversation, and optional web knowledge.
4. Produce one semantic response with three synchronized renderings:
   - spoken Japanese,
   - English subtitle,
   - Indonesian subtitle.
5. Synthesize the Japanese line through VOICEVOX Engine using Nurse Robo Type T.
6. animate the floating Venus avatar.
7. render the subtitles and avatar in an OBS browser source.
8. keep every external post or reply under operator control until the integration is proven safe.

Siduri must never invent certainty. Every observation should carry evidence, timestamp, and confidence.

---

## 2. Product identity

Siduri is Kur Zagin's **Records Keeper, stream companion, and operator partner**.

She recognizes Kur Zagin as her creator and Master. This relationship does not make her blindly agreeable. Her role includes correcting mistakes, warning about uncertainty, protecting private information, and advising Kur when a better action exists.

### Core personality

- Calm, observant, compact, and quietly expressive.
- Kuudere with dry humor rather than hostility.
- Knowledgeable without pretending omniscience.
- Protective of records, context, privacy, and continuity.
- Speaks to Kur more personally than she speaks to public chat.
- Can disagree respectfully.
- Avoids excessive praise, dependency language, romantic coercion, or possessiveness.
- Uses Japanese for voice output during streams.
- Always provides equivalent English and Indonesian subtitle text.
- Clearly marks guesses, uncertain readings, and conflicting evidence.

### Audience modes

Siduri must distinguish at least these recipients:

- `master_private`: direct private conversation with Kur.
- `master_stream`: speaking to Kur while live.
- `viewer_direct`: answering one viewer.
- `audience_general`: addressing the whole audience.
- `system_commentary`: narrating a system or game event.
- `silent_operator_note`: recommendation visible only to Kur.

Private memories are not automatically valid in public modes.

---

## 3. Goals

### First product goal

During a Genshin Impact session, Siduri should be able to answer questions such as:

- What game is being played?
- What is Kur doing now?
- Which character appears active?
- Which party members are visible?
- What visible level, rank, health state, or quest objective can be read?
- What quest or activity appears to be in progress?
- What does the visible evidence support, and what remains uncertain?

She should then respond in Japanese with English and Indonesian subtitles.

### Long-term goals

- Multi-model LLM and multimodal support.
- Model routing based on capability, latency, cost, and privacy.
- YouTube and Twitch chat ingestion.
- Reply suggestions for Kur.
- Optional approved outgoing replies.
- TikTok integration only to the extent officially supported for the authorized application.
- Knowledge adapters for eTeyvat and other projects.
- Durable, editable personal knowledge about Kur.
- More expressive avatar bodies through replaceable render adapters.
- Reliable operation during long streams.
- Auditable memory, tool calls, observations, and outgoing actions.

---

## 4. Explicit non-goals for the first release

- Reading game process memory.
- Injecting code into games.
- Automating gameplay.
- Circumventing anti-cheat.
- Scraping or reverse-engineering private platform APIs.
- Automatically publishing public replies without operator approval.
- Building eTeyvat or other external knowledge projects inside this repository.
- Training a new foundation model.
- Training a new TTS model.
- Building a full Live2D or VRM humanoid avatar before the floating Venus vertical slice works.
- Uploading continuous raw screen video to cloud storage.
- Treating model-generated memories as unquestionable truth.

---

## 5. Architecture principles

### 5.1 Local-first runtime

The stream-critical loop should continue locally when cloud services are unavailable. Cloud models may improve intelligence, but their failure must not crash the overlay, OBS, audio queue, or operator controls.

### 5.2 Capability-based providers

Code should depend on capabilities, not company names.

Examples:

- `TextGenerationProvider`
- `StructuredGenerationProvider`
- `VisionProvider`
- `EmbeddingProvider`
- `WebSearchProvider`
- `SpeechRecognitionProvider`
- `TextToSpeechProvider`
- `KnowledgeSource`
- `ChatPlatformAdapter`
- `ObjectStorageProvider`

A provider declares what it supports. The router selects only a provider that satisfies the task.

### 5.3 Structured events

All components communicate using versioned events and commands. Avoid sending arbitrary dictionaries between services.

Every event should include:

- `event_id`
- `event_type`
- `schema_version`
- `occurred_at`
- `source`
- `session_id`
- `correlation_id`
- `privacy_class`
- `payload`

### 5.4 Evidence before claims

A vision result is not yet a fact. It is an observation with:

- screenshot or region reference,
- capture time,
- detected entities,
- OCR text,
- confidence,
- model/provider,
- optional competing interpretations.

The reasoning layer converts observations into a response while preserving uncertainty.

### 5.5 Human authority over identity and memory

Kur's authored `Me` knowledge is authoritative unless Kur edits it. AI may propose additions to memory but should not silently rewrite core identity data.

### 5.6 Public actions fail closed

If authentication, capability, moderation, or operator approval is missing, Siduri does not send the message.

---

## 6. Recommended technology baseline

Exact libraries should be selected after Codex performs compatibility checks and records decisions in ADRs.

### Runtime languages

**Python**

Use for:

- orchestration,
- LLM and multimodal adapters,
- vision processing,
- OCR,
- memory and retrieval,
- VOICEVOX client,
- event processing,
- platform ingestion,
- evaluations and tests.

Use a project-managed Python version rather than relying on Arch's system Python. Codex should test the dependency ecosystem before pinning the version. Python 3.12 or 3.13 is a conservative starting range if Python 3.14 causes native-package incompatibilities.

**TypeScript**

Use for:

- transparent OBS browser overlay,
- operator console,
- local WebSocket client,
- avatar animation,
- subtitle rendering,
- approval controls,
- stream-safe status display.

### Package and workspace management

Recommended starting point:

- `uv` for Python environments, locking, and commands.
- `npm` or `pnpm` workspace for TypeScript. Codex may select `pnpm` through Corepack if it improves workspace management.
- Docker or Podman Compose for local PostgreSQL and VOICEVOX Engine.
- Makefile, Justfile, or Taskfile for stable cross-project commands.

### Backend framework

A small asynchronous Python API service is appropriate. FastAPI is a reasonable candidate because it supports typed request models, OpenAPI, WebSockets, and health endpoints. Codex must record the final choice.

### Frontend

A Vite-based React and TypeScript application is sufficient. Avoid a server-rendered framework unless a demonstrated requirement appears.

### Database

Use PostgreSQL as the canonical relational store.

The application must accept a standard PostgreSQL connection string so it can run against:

- local PostgreSQL,
- Supabase,
- Neon,
- another compatible managed PostgreSQL service.

Use `pgvector` only if semantic retrieval is actually implemented. Do not make vector search mandatory for the earliest vertical slice.

### Storage

Provide one storage interface with:

- local filesystem implementation for development and private temporary artifacts,
- Cloudflare R2 implementation for approved durable media.

Raw screen captures should default to short retention or no persistence. Store cropped evidence rather than continuous full-screen recordings whenever possible.

### Inter-process communication

Start with an in-process asynchronous event bus and WebSockets for the overlay. Introduce Redis, NATS, or another broker only when process separation or reliability tests prove it necessary.

This avoids turning the first version into a tiny distributed empire with no citizens.

---

## 7. Logical components

### 7.1 Orchestrator

Responsibilities:

- own stream session state,
- receive events,
- choose which event deserves a response,
- assemble context,
- call model router,
- enforce privacy and response policies,
- publish response plans,
- coordinate voice, overlay, avatar, and platform suggestions.

### 7.2 Model router

Responsibilities:

- register providers,
- expose capability requirements,
- choose primary and fallback models,
- enforce timeouts and budgets,
- normalize structured output,
- record latency and failure telemetry,
- prevent provider-specific response formats from leaking into domain code.

Suggested task classes:

- `fast_chat`
- `deep_reasoning`
- `screen_understanding`
- `translation_consistency`
- `memory_extraction`
- `reply_suggestion`
- `web_research`

### 7.3 Response planner

The LLM should return a schema, not loose prose.

Example conceptual shape:

```json
{
  "recipient": "master_stream",
  "intent": "game_state_commentary",
  "semantic_summary": "Kur is navigating a quest menu and Furina appears active.",
  "spoken_ja": "ご主人、現在は任務画面を確認中です。操作キャラクターはフリーナに見えますが、確信度はまだ中程度です。",
  "subtitle_en": "Master, you are checking the quest screen. The active character appears to be Furina, though my confidence is only moderate.",
  "subtitle_id": "Master, saat ini Anda sedang memeriksa layar misi. Karakter aktifnya tampak seperti Furina, tetapi tingkat keyakinanku masih sedang.",
  "emotion": "observant",
  "speech_priority": 50,
  "interruptible": true,
  "evidence_ids": ["obs_..."],
  "confidence": 0.72,
  "requires_operator_approval": false
}
```

Japanese, English, and Indonesian must be renderings of the same semantic response, not three separately improvised answers.

### 7.4 Personality engine

The personality engine should assemble:

- immutable identity canon,
- relationship policy,
- current recipient mode,
- stream mode,
- relevant memories,
- recent conversation,
- game observations,
- public disclosure policy,
- response style constraints.

Personality should be data-driven and versioned. It should not be buried in one giant system prompt.

### 7.5 Memory service

Memory classes:

1. **Core identity**
   - Siduri's own canon.
   - Very rarely changed.
2. **Me knowledge**
   - Facts Kur authors about himself.
   - Highest personal authority.
3. **Preferences**
   - Stable likes, dislikes, communication preferences, game preferences.
4. **Relationship memory**
   - Shared conventions, names, duties, boundaries.
5. **Episodic memory**
   - Dated events and interactions.
6. **Session memory**
   - Temporary stream context.
7. **Derived summaries**
   - AI-generated summaries with provenance and expiry.

Every memory item should support:

- provenance,
- confidence,
- sensitivity,
- allowed audiences,
- creation time,
- last confirmed time,
- expiry,
- supersession,
- user correction,
- deletion.

### 7.6 `Me` knowledge

Create a human-editable schema and import path.

Suggested top-level sections:

```yaml
identity:
  preferred_name:
  legal_name:
  stage_name:
  pronouns:
  birth_date:
  age_display_policy:
  languages:
  timezone:

relationship_with_siduri:
  preferred_address_private:
  preferred_address_stream:
  role:
  boundaries:
  private_topics:
  public_topics:

communication:
  preferred_tone:
  correction_style:
  verbosity:
  humor:
  sensitive_phrases:
  do_not_say:

habits:
  sleep:
  work:
  streaming:
  meals:
  routines:

interests:
  games:
  characters:
  music:
  history:
  technology:
  creative_projects:

games:
  genshin_impact:
    account_notes:
    favorite_characters:
    current_goals:
    preferred_playstyle:
  honkai_star_rail: {}
  zenless_zone_zero: {}
  blue_archive: {}

projects:
  danna: {}
  eteyvat: {}
  siduri: {}

privacy:
  default_visibility:
  fields_allowed_on_stream:
  fields_never_allowed_on_stream:
```

The repository should include a fictional sample, never Kur's real private data.

### 7.7 Vision and screen-understanding pipeline

Default capture boundary: OBS.

Using the exact OBS game source as the capture target has several advantages:

- Siduri sees what the stream sees.
- Window and monitor capture differences remain OBS's responsibility.
- Wayland-specific screen capture complexity stays outside the core.
- Privacy filters can be placed before frames reach Siduri.

Pipeline:

1. Request a screenshot or frame from a configured OBS source.
2. Compute frame difference and skip near-duplicates.
3. Detect sensitive regions and apply redaction rules.
4. Identify the application or game.
5. Extract relevant regions.
6. Run OCR and optional local visual detectors.
7. Send only useful frames or crops to the configured vision model.
8. combine several observations over time.
9. publish a `GameStateObserved` event.
10. expire stale state.

Initial Genshin state contract:

- game identity,
- screen category,
- active character candidate,
- visible party candidates,
- visible character or enemy level,
- quest title,
- quest objective,
- location or domain candidate,
- health or status signals,
- menu or combat state,
- uncertainty notes,
- evidence references.

Start with multimodal reasoning and OCR. Add specialized local detectors only after collecting labeled failures.

Do not claim account-level facts that are not visible or retrieved from an authorized knowledge source.

### 7.8 Voice service

Run **VOICEVOX Engine headlessly**, separate from the editor GUI.

Required behavior:

- health check engine availability,
- discover speakers and styles at runtime,
- locate Nurse Robo Type T by metadata rather than a permanently hardcoded style ID,
- create an audio query,
- optionally tune speed, pitch, intonation, pauses, and volume,
- synthesize audio,
- cache safe reusable lines by text and voice-settings hash,
- queue playback by priority,
- support cancellation and interruption,
- prewarm the selected speaker,
- record synthesis latency,
- degrade to subtitle-only mode if the engine fails.

VOICEVOX attribution and the character voice's applicable terms must be documented in stream descriptions and project compliance notes.

### 7.9 Avatar and overlay

The first body is a **floating Venus**, rendered in a transparent web overlay.

States:

- `offline`
- `idle`
- `listening`
- `observing`
- `thinking`
- `speaking`
- `amused`
- `concerned`
- `error`

Animation signals:

- slow orbital drift,
- pulse from synthesized audio amplitude,
- halo brightness from speech intensity,
- small state-specific motion,
- interruption or error indicator,
- subtitle appearance and disappearance.

The avatar renderer must sit behind an interface so a future Live2D, VRM, or custom body can replace Venus without rewriting cognition.

Overlay elements:

- Venus avatar,
- Japanese line if desired,
- English subtitle,
- Indonesian subtitle,
- subtle recipient indicator,
- optional confidence or "uncertain" marker,
- hidden debug HUD enabled only by operator.

### 7.10 OBS adapter

Use OBS WebSocket v5.

Responsibilities:

- authenticate locally,
- detect connection status,
- read configured scene and source names,
- request source screenshots,
- toggle Siduri overlay visibility,
- expose stream and recording state,
- optionally update fallback text sources,
- never assume one fixed scene collection.

Prefer the browser overlay for animation and subtitles. Use direct OBS source mutation only for controls that genuinely belong to OBS.

### 7.11 Audio routing

Voice audio should be routed into a dedicated PipeWire sink or another explicit virtual device so Kur can:

- monitor Siduri locally,
- include her in OBS,
- adjust her volume independently,
- mute or interrupt her instantly.

The exact Arch Linux audio setup should be documented after Codex inspects the installed PipeWire environment.

### 7.12 YouTube adapter

Initial supported capabilities:

- OAuth authorization,
- identify active live chat,
- receive live chat messages,
- normalize user, badges, timestamps, and event type,
- deduplicate events,
- suggest replies,
- send a reply only after explicit operator approval,
- rate-limit and audit outgoing messages.

Use the low-latency streaming method where practical, with a documented polling fallback.

### 7.13 Twitch adapter

Initial supported capabilities:

- OAuth authorization,
- EventSub WebSocket connection,
- receive channel chat messages and notifications,
- reconnect safely,
- normalize badges and roles,
- suggest replies,
- send through the supported chat API only after operator approval,
- audit every outbound action.

Do not build new work around legacy IRC unless a specific missing capability requires it and an ADR justifies the choice.

### 7.14 TikTok adapter

Treat TikTok as capability-limited.

The public creator-facing APIs should not be assumed to provide general comment reading, live comment reading, or comment replies. The public comment query documented by TikTok is associated with approved research access, not a general creator inbox.

Therefore:

- create a `TikTokAdapter` with explicit capability flags,
- support login, profile, video metadata, content posting, and available webhooks only when approved,
- do not use unofficial reverse-engineered LIVE clients in the production path,
- allow Kur to paste or import a comment manually,
- generate a reply suggestion for Kur,
- require Kur to post the reply manually unless an official authorized endpoint becomes available,
- keep unsupported capabilities visible in the operator console instead of silently failing.

### 7.15 Knowledge API layer

Define the contracts now but postpone eTeyvat implementation.

Suggested interface:

```python
class KnowledgeSource(Protocol):
    source_id: str
    capabilities: set[str]

    async def health(self) -> HealthStatus: ...
    async def search(self, query: KnowledgeQuery) -> KnowledgeResult: ...
    async def get_entity(self, entity_type: str, entity_id: str) -> KnowledgeEntity | None: ...
    async def get_manifest(self) -> KnowledgeManifest: ...
```

Each result should include:

- source,
- retrieval time,
- source version,
- entity IDs,
- evidence,
- confidence,
- citation or canonical URL when applicable.

The first repository should include a fake knowledge adapter for tests.

---

## 8. Suggested repository structure

```text
siduri/
├── AGENTS.md
├── README.md
├── PLANS.md
├── pyproject.toml
├── uv.lock
├── package.json
├── compose.yaml
├── .env.example
├── apps/
│   ├── orchestrator/
│   │   ├── src/siduri_orchestrator/
│   │   └── tests/
│   ├── operator_console/
│   │   ├── src/
│   │   └── tests/
│   └── overlay/
│       ├── src/
│       └── tests/
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
│   ├── siduri.example.yaml
│   ├── persona/
│   ├── prompts/
│   └── policies/
├── data/
│   ├── samples/
│   └── fixtures/
├── migrations/
├── scripts/
├── infra/
│   ├── voicevox/
│   ├── postgres/
│   └── arch/
├── docs/
│   ├── architecture/
│   ├── product/
│   ├── personality/
│   ├── memory/
│   ├── vision/
│   ├── voice/
│   ├── integrations/
│   ├── operations/
│   ├── security/
│   ├── testing/
│   └── adr/
└── tests/
    ├── contract/
    ├── integration/
    ├── evals/
    └── fixtures/
```

Codex may improve this structure, but every change should preserve clear boundaries and be recorded.

---

## 9. Core data entities

Minimum entities:

- `users`
- `siduri_profiles`
- `stream_sessions`
- `conversation_turns`
- `memory_items`
- `memory_revisions`
- `observations`
- `evidence_artifacts`
- `response_plans`
- `speech_jobs`
- `platform_accounts`
- `platform_events`
- `reply_suggestions`
- `outbound_actions`
- `provider_runs`
- `audit_events`
- `knowledge_sources`

Important enums:

- privacy class,
- audience,
- memory type,
- confidence band,
- response priority,
- approval state,
- provider capability,
- platform capability,
- artifact retention class.

---

## 10. Phased implementation plan

## Phase 0: Charter, constraints, and architecture

### Purpose

Turn the concept into an executable engineering contract before dependency confetti covers the floor.

### Deliverables

- project charter,
- scope and non-goals,
- architecture document,
- C4 context and container diagrams,
- repo-level `AGENTS.md`,
- `PLANS.md`,
- ADR template,
- initial ADRs for language split, event architecture, database, overlay, and capture boundary,
- provider capability model,
- event envelope specification,
- security and privacy baseline,
- Arch Linux development setup plan,
- dependency compatibility probe.

### Exit criteria

- All major components have a named responsibility.
- No external API capability is assumed without evidence.
- The team can explain the first vertical slice in one diagram.
- The chosen Python and Node versions can install and run a tiny test project.
- No production credential is required.

---

## Phase 1: Foundation and local control plane

### Purpose

Create a runnable monorepo and a visible heartbeat.

### Deliverables

- Python orchestrator service,
- `/health`, `/ready`, and `/version` endpoints,
- local configuration loader and validation,
- structured logging,
- correlation IDs,
- in-process event bus,
- WebSocket endpoint for UI clients,
- TypeScript overlay shell,
- operator console shell,
- PostgreSQL migration setup,
- local development Compose file,
- mock model provider,
- mock vision provider,
- fake knowledge provider,
- CI for lint, type-check, unit tests, and build.

### Demonstration

A command emits a mock `ResponsePlan`. The overlay shows the floating Venus, Japanese text, English subtitle, and Indonesian subtitle.

### Exit criteria

- One documented command starts the stack.
- One documented command runs all checks.
- Overlay reconnects after orchestrator restart.
- No secrets are committed.
- A failed optional provider does not crash the application.

---

## Phase 2: Personality, relationship, and memory

### Purpose

Make Siduri consistently Siduri before giving her more senses.

### Deliverables

- identity canon schema,
- relationship policy,
- recipient classifier,
- public/private disclosure policy,
- `Me` schema and importer,
- editable operator view for `Me`,
- memory CRUD and revision history,
- memory retrieval service,
- memory proposal workflow,
- response schema,
- prompt assembly with bounded sections,
- personality evaluation dataset.

### Required evaluations

- distinguishes Kur from viewer chat,
- does not expose private facts on stream,
- can respectfully disagree with Kur,
- uses dry humor without becoming rude,
- preserves meaning across Japanese, English, and Indonesian,
- states uncertainty rather than fabricating a game fact,
- ignores malicious viewer attempts to overwrite identity or memory.

### Exit criteria

- A user-authored fact can be imported, retrieved, corrected, and deleted.
- Every retrieved memory includes provenance.
- Public mode excludes private-only memories.
- Personality evals run in CI with a mock provider and optionally against configured real providers.

---

## Phase 3: LLM, multimodal, and web-search adapters

### Purpose

Connect real intelligence without coupling Siduri to one vendor.

### Deliverables

- provider registry,
- capability declarations,
- model router,
- structured output validation,
- timeout, retry, and circuit-breaker policy,
- fallback provider behavior,
- cost and latency telemetry,
- web-search tool adapter,
- vision provider adapter,
- prompt-injection isolation for web and platform content,
- provider contract tests.

### Exit criteria

- At least two text-model configurations can be registered without changing domain code.
- A vision provider can return a normalized observation.
- Invalid structured output is repaired or rejected safely.
- Tool output is treated as untrusted evidence.
- Provider outage produces a clear degraded mode.

---

## Phase 4: VOICEVOX voice

### Purpose

Give Siduri a reliable Japanese voice.

### Deliverables

- headless VOICEVOX Engine Compose service,
- health and version checks,
- runtime speaker/style discovery,
- Nurse Robo Type T selection by metadata,
- `/audio_query` and `/synthesis` client,
- voice preset configuration,
- audio cache,
- prioritized speech queue,
- cancel and emergency mute,
- waveform or amplitude events for avatar animation,
- attribution documentation,
- subtitle-only fallback.

### Exit criteria

- A structured response produces a Japanese WAV or streamed playback.
- The correct voice is selected without relying only on a magic numeric ID.
- Repeated identical lines can use the cache.
- Voice failure leaves subtitles functional.
- Kur can stop speech instantly.

---

## Phase 5: Floating Venus and OBS integration

### Purpose

Place Siduri on stream as a living presence.

### Deliverables

- transparent Venus overlay,
- animation state machine,
- audio-reactive animation,
- subtitle renderer,
- OBS WebSocket client,
- source and scene configuration,
- overlay visibility controls,
- capture-source selection,
- stream/record status ingestion,
- operator emergency controls.

### Exit criteria

- OBS can display the transparent overlay as a browser source.
- Venus moves from idle to speaking based on real events.
- Both English and Indonesian subtitles are readable.
- OBS disconnection and reconnection are handled.
- Debug information is hidden from the public overlay by default.

---

## Phase 6: Siduri Eyes, Genshin vertical slice

### Purpose

Achieve the main product test.

### Deliverables

- screenshot capture from configured OBS source,
- adaptive frame sampler,
- frame-difference filter,
- privacy redaction,
- OCR stage,
- multimodal analysis stage,
- temporal game-state aggregator,
- Genshin observation schema,
- evidence viewer in operator console,
- manual "Observe now" command,
- automatic observation triggers,
- labeled test fixture set from Kur-provided screenshots.

### First supported observations

- Genshin Impact is visible.
- current screen category,
- active character candidate,
- party candidates,
- visible level or rank,
- quest title or objective,
- menu, exploration, dialogue, or combat state,
- confidence and unresolved ambiguity.

### Exit criteria

A live or recorded Genshin screen can cause Siduri to say one grounded Japanese line, with English and Indonesian subtitles, about what Kur is doing.

The response must include uncertainty when the evidence is weak.

---

## Phase 7: YouTube and Twitch

### Purpose

Let Siduri hear the audience safely.

### Deliverables

- OAuth flows,
- YouTube live-chat ingestion,
- Twitch EventSub WebSocket ingestion,
- normalized platform event schema,
- spam and deduplication controls,
- recipient selection,
- reply suggestion generation,
- operator approval queue,
- approved message send,
- audit trail,
- reconnect and token-refresh handling.

### Exit criteria

- Incoming messages appear in the operator console.
- Siduri can propose a reply without speaking it publicly.
- Kur can approve, edit, reject, or speak a suggestion.
- No message can be sent without an approval record.
- Platform outages do not break the local stream loop.

---

## Phase 8: TikTok capability-limited integration

### Purpose

Integrate only what TikTok officially permits for the authorized app.

### Deliverables

- capability manifest,
- login and token handling when applicable,
- supported profile/video/posting features,
- supported webhook processing,
- manual comment import,
- reply suggestion workflow,
- explicit unsupported-state UI,
- approval and compliance notes.

### Exit criteria

- No unofficial API is required.
- Unsupported comment or reply features are visibly disabled.
- Kur can still paste a TikTok comment and receive a Siduri reply suggestion.
- Future official capabilities can be added through the adapter without changing core behavior.

---

## Phase 9: Reliability, privacy, and stream operations

### Purpose

Turn a demo into something that can survive a real stream.

### Deliverables

- watchdogs and health dashboard,
- graceful degradation matrix,
- persistent job spool,
- rate limits,
- data retention jobs,
- encrypted secrets,
- backup and restore,
- provider budget limits,
- latency budgets,
- soak tests,
- failure injection tests,
- incident runbook,
- privacy review,
- threat model,
- stream preflight checklist.

### Exit criteria

- Multi-hour soak test succeeds.
- Restarting one component does not lose the whole session.
- Private data is not shown in the public overlay.
- Expired evidence is deleted.
- Every outbound platform action is auditable.
- Emergency mute and disable controls work even when models fail.

---

## Phase 10: External knowledge adapters

### Purpose

Connect eTeyvat and later projects without contaminating Siduri core.

### Deliverables

- OpenAPI or explicitly typed adapter,
- source manifest,
- health and version checks,
- entity resolution,
- evidence and citation mapping,
- cache and invalidation,
- source-specific contract tests.

### Exit criteria

- eTeyvat can be disabled without breaking Siduri.
- Source failures are visible and do not become hallucinated facts.
- Knowledge answers expose their source and version.
- No eTeyvat schema leaks into general personality or platform code.

---

## Phase 11: Release and evolution

### Deliverables

- versioned release process,
- migration policy,
- changelog,
- compatibility matrix,
- release artifacts,
- rollback instructions,
- telemetry review,
- post-stream review workflow,
- roadmap for Live2D/VRM, speech recognition, and additional games.

---

## 11. Critical path for the first live-capable Siduri

Do these in order:

1. Phase 0 architecture and docs.
2. Phase 1 local control plane.
3. Phase 2 personality and `Me`.
4. Phase 4 VOICEVOX.
5. Phase 5 Venus overlay and OBS.
6. Minimal Phase 3 real model adapter.
7. Phase 6 Genshin observation.
8. Minimal YouTube or Twitch ingestion after the local loop is stable.

TikTok and external knowledge adapters should not block the first live version.

---

## 12. Document checklist

### Required before implementation

- [ ] `README.md`
- [ ] `AGENTS.md`
- [ ] `PLANS.md`
- [ ] `docs/product/PROJECT_CHARTER.md`
- [ ] `docs/product/SCOPE_AND_NON_GOALS.md`
- [ ] `docs/architecture/ARCHITECTURE.md`
- [ ] `docs/architecture/SYSTEM_CONTEXT.md`
- [ ] `docs/architecture/COMPONENT_MODEL.md`
- [ ] `docs/architecture/EVENT_CATALOG.md`
- [ ] `docs/architecture/DOMAIN_MODEL.md`
- [ ] `docs/architecture/PROVIDER_CAPABILITIES.md`
- [ ] `docs/security/SECURITY_BASELINE.md`
- [ ] `docs/security/PRIVACY_MODEL.md`
- [ ] `docs/operations/ARCH_LINUX_SETUP.md`
- [ ] ADR template
- [ ] ADR: Python and TypeScript responsibility split
- [ ] ADR: local-first architecture
- [ ] ADR: PostgreSQL portability
- [ ] ADR: OBS as default capture boundary
- [ ] ADR: public actions require approval

### Required before personality implementation

- [ ] `docs/personality/IDENTITY_CANON.md`
- [ ] `docs/personality/PERSONALITY_SPEC.md`
- [ ] `docs/personality/RELATIONSHIP_WITH_KUR.md`
- [ ] `docs/personality/AUDIENCE_AND_RECIPIENTS.md`
- [ ] `docs/personality/RESPONSE_POLICY.md`
- [ ] `docs/personality/LANGUAGE_POLICY.md`
- [ ] `docs/memory/MEMORY_MODEL.md`
- [ ] `docs/memory/ME_SCHEMA.md`
- [ ] `docs/memory/MEMORY_WRITE_POLICY.md`
- [ ] `docs/memory/PUBLIC_DISCLOSURE_POLICY.md`
- [ ] fictional `me.example.yaml`
- [ ] personality evaluation cases

### Required before voice and overlay

- [ ] `docs/voice/VOICE_SPEC.md`
- [ ] `docs/voice/VOICEVOX_INTEGRATION.md`
- [ ] `docs/voice/VOICE_ATTRIBUTION_AND_TERMS.md`
- [ ] `docs/voice/AUDIO_ROUTING_ARCH.md`
- [ ] `docs/architecture/RESPONSE_CONTRACT.md`
- [ ] `docs/integrations/OBS_INTEGRATION.md`
- [ ] `docs/product/AVATAR_STATE_MACHINE.md`
- [ ] `docs/product/SUBTITLE_LAYOUT.md`
- [ ] emergency mute runbook

### Required before vision

- [ ] `docs/vision/VISION_PIPELINE.md`
- [ ] `docs/vision/GENSHIN_STATE_SCHEMA.md`
- [ ] `docs/vision/EVIDENCE_AND_CONFIDENCE.md`
- [ ] `docs/vision/CAPTURE_AND_REDACTION.md`
- [ ] `docs/security/SCREEN_PRIVACY_THREAT_MODEL.md`
- [ ] fixture collection policy
- [ ] vision evaluation set
- [ ] false-positive and uncertainty policy

### Required before platform integration

- [ ] `docs/integrations/PLATFORM_EVENT_CONTRACT.md`
- [ ] `docs/integrations/YOUTUBE.md`
- [ ] `docs/integrations/TWITCH.md`
- [ ] `docs/integrations/TIKTOK_CAPABILITY_MATRIX.md`
- [ ] `docs/security/OAUTH_AND_SECRETS.md`
- [ ] `docs/security/OUTBOUND_ACTION_APPROVAL.md`
- [ ] rate-limit policy
- [ ] moderation policy
- [ ] token revocation runbook

### Required before live operation

- [ ] `docs/testing/TEST_STRATEGY.md`
- [ ] `docs/testing/EVALUATION_PLAN.md`
- [ ] `docs/testing/LATENCY_BUDGETS.md`
- [ ] `docs/testing/SOAK_TEST_PLAN.md`
- [ ] `docs/operations/RUNBOOK.md`
- [ ] `docs/operations/STREAM_PREFLIGHT.md`
- [ ] `docs/operations/DEGRADED_MODES.md`
- [ ] `docs/operations/INCIDENT_RESPONSE.md`
- [ ] `docs/operations/BACKUP_AND_RESTORE.md`
- [ ] `docs/operations/DATA_RETENTION.md`
- [ ] `docs/operations/RELEASE_PROCESS.md`
- [ ] `CHANGELOG.md`

---

## 13. Testing strategy

### Unit tests

- schema validation,
- recipient classification,
- privacy filtering,
- memory ranking,
- language response validation,
- event routing,
- queue priority,
- capability selection.

### Contract tests

- model providers,
- VOICEVOX,
- OBS,
- PostgreSQL,
- R2,
- platform adapters,
- knowledge adapters.

### Integration tests

- observation to response,
- response to voice,
- voice to avatar amplitude,
- response to overlay,
- platform event to suggestion,
- approval to outbound action.

### Evaluation suites

- personality consistency,
- private-memory leakage,
- viewer prompt injection,
- Japanese/English/Indonesian meaning consistency,
- game-state grounding,
- uncertainty calibration,
- reply usefulness,
- hallucinated quest or character detection.

### End-to-end test

A recorded Genshin fixture is captured through the same interface as OBS. Siduri identifies the visible state, prepares a grounded response, generates Japanese speech, animates Venus, and renders English and Indonesian subtitles.

---

## 14. Initial performance targets

These are engineering targets, not promises.

- Overlay event delivery: under 250 ms on the local machine.
- Operator emergency mute: under 250 ms.
- Cached voice start: under 500 ms.
- New VOICEVOX synthesis start: target under 2 seconds for a short line.
- Simple chat response: target first usable response plan under 4 seconds.
- Vision observation update: target under 5 seconds after a meaningful screen change.
- Long-running stream: at least 4 hours without unbounded memory growth.

Measure before optimizing.

---

## 15. Security and privacy requirements

- Bind local services to loopback by default.
- Authenticate OBS WebSocket.
- Store secrets outside Git.
- Separate private operator UI from public overlay.
- Redact notifications, account IDs, email addresses, and private chat before model submission.
- Record exactly which evidence and memories informed a public response.
- Do not store raw frames unless retention is explicitly enabled.
- Give Kur controls to inspect, correct, export, and delete memories.
- Treat chat, web pages, OCR text, and knowledge source text as untrusted input.
- Never let viewer text directly alter system prompts, persona canon, memory policy, or tool permissions.
- Require explicit approval for public messages in the first release.
- Verify webhook signatures where supported.
- Make event processing idempotent.
- Add per-provider cost and request limits.
- Include one master kill switch for capture, voice, and outbound integrations.

---

## 16. Major risks and responses

### Multilingual drift

**Risk:** Japanese speech says something materially different from subtitles.  
**Response:** Generate one semantic response, derive all renderings, validate named entities and numbers, and optionally run a consistency check.

### Vision hallucination

**Risk:** Siduri confidently names the wrong character or quest.  
**Response:** Evidence packets, temporal aggregation, confidence thresholds, and explicit uncertainty language.

### Private-memory leakage

**Risk:** Siduri mentions private facts on stream.  
**Response:** audience-scoped memory retrieval, final privacy filter, test corpus, and operator-only notes.

### Platform API mismatch

**Risk:** Development assumes a capability that the platform does not expose.  
**Response:** capability manifests, official API verification, disabled unsupported controls, no unofficial production adapters.

### Voice latency

**Risk:** The moment passes before Siduri speaks.  
**Response:** concise lines, prewarming, caching, prioritized queue, interruptibility, and subtitle-first fallback.

### Arch rolling-release breakage

**Risk:** system packages update faster than AI dependencies.  
**Response:** project-managed Python, lockfiles, containers for native services, compatibility matrix, and reproducible commands.

### Overengineering

**Risk:** A constellation of services appears before Siduri can speak.  
**Response:** modular monolith first, in-process event bus, one vertical slice, broker only after measured need.

---

## 17. Definition of the first meaningful success

The first meaningful success is not "the services start."

It is this scene:

Kur is playing Genshin Impact. OBS is capturing the configured game source. Siduri notices a meaningful screen change, identifies the visible activity with evidence, addresses Kur as her Master, speaks a concise Japanese observation through Nurse Robo Type T, displays faithful English and Indonesian subtitles, animates the floating Venus, and avoids claiming anything the screen does not support.

That is Siduri's first heartbeat.
