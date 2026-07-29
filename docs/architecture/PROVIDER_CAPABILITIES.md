# Provider capabilities

Providers declare capabilities: text generation, structured generation, vision, embeddings, web search, speech recognition, text-to-speech, and tool calling. Routers select by required capability, privacy, timeout, cost, and latency. Unsupported requests fail clearly; provider response formats do not cross the domain boundary.

The first real model adapter is GLM-5.2 through Z.AI's standard chat-completions endpoint. It is selected with `SIDURI_MODEL_PROVIDER=zai` and reads `ZAI_API_KEY` from the environment. The mock provider remains the safe fallback when no key is configured. A live provider request is intentionally not part of credential-free CI.
