# AI Answers Plugin for SearXNG
**Single file install**
**Does not block result loading time**

A SearXNG plugin that generates AI answers using search results as RAG context. Supports 8+ LLM providers.

> This is a fork of [cra88y/ai-answers-searxng](https://github.com/cra88y/ai-answers-searxng) tuned for a DeepSeek-via-OpenRouter deployment, with additional features: reasoning-model token budgets, markdown rendering, a collapsed-by-default answer box with zero layout shift, a real system role, extra request-body passthrough, and a pytest suite.

Features:
- token-by-token UI streaming
- markdown rendering (bold, italics, code, lists, headers) with clickable inline citations
- collapsed preview with "Show more" — the results list never shifts while the answer streams
- reasoning-model support: streamed thinking shown in a collapsible "Thought Process" box, with a separate reasoning token budget
- interactive mode to continue summary, ask follow ups, copy, or regenerate
- simple response mode with no extras
- internally called low-latency RAG for follow ups (bypasses http loopback)
- stateless conversation persistence/sharability via URL
- provider detection based on URL
- per-user opt-in/opt-out via the SearXNG Preferences page

## Installation (Docker on Windows)

This guide assumes the official `searxng-docker` layout, e.g.:

```
searxng/
├── docker-compose.yml
├── .env
└── core-config/
    └── settings.yml
```

### Step 1 — Get the plugin file

From the folder containing `docker-compose.yml`, in PowerShell:

```powershell
mkdir core-config\plugins
curl.exe -o core-config\plugins\ai_answers.py https://raw.githubusercontent.com/drittich/ai-answers-searxng/master/ai_answers.py
```

> The file must be named exactly `ai_answers.py` — a different name (e.g. `ai-answers.py`) causes `ModuleNotFoundError: No module named 'searx.plugins.ai_answers'` at startup.

### Step 2 — Mount it in `docker-compose.yml`

Add a volume line under the SearXNG service:

```yaml
  core:
    container_name: searxng-core
    image: docker.io/searxng/searxng:${SEARXNG_VERSION:-latest}
    restart: always
    ports:
      - ${SEARXNG_HOST:+${SEARXNG_HOST}:}${SEARXNG_PORT:-8080}:${SEARXNG_PORT:-8080}
    env_file: ./.env
    volumes:
      - ./core-config/:/etc/searxng/:Z
      - ./core-config/plugins/ai_answers.py:/usr/local/searxng/searx/plugins/ai_answers.py:ro
      - core-data:/var/cache/searxng/
```

### Step 3 — Add LLM environment variables to `.env`

Open `.env` and add the variables for your provider, for example (DeepSeek V4 Flash via OpenRouter):

```
LLM_PROVIDER=openrouter
LLM_KEY=sk-or-xxxxxxxx
LLM_MODEL=deepseek/deepseek-v4-flash
LLM_REASONING_MAX_TOKENS=2000
LLM_EXTRA_BODY={"reasoning_effort": "high"}
```

See the provider reference table below for other options.

### Step 4 — Enable the plugin in `settings.yml`

Open `core-config\settings.yml` and add (or extend) the `plugins:` section:

```yaml
plugins:
  searx.plugins.ai_answers.SXNGPlugin:
    active: true
```

If a `plugins:` key already exists, add this entry under it rather than creating a second `plugins:` block.

`active: true` is only the *default* — each user can turn the plugin on or off for themselves under **Preferences → General → AI Answers Plugin** (stored in their browser's preferences cookie). On a shared instance you can set `active: false` and let users opt in.

### Step 5 — Recreate the container

```powershell
docker compose up -d --force-recreate core
```

Only the SearXNG service needs to be recreated — `valkey`/`redis` is untouched.

### Step 6 — Verify

```powershell
docker compose logs -f core
```

On startup the plugin logs its resolved config, e.g.:

```
INFO:searx.plugins.ai_answers: AI Answers: provider=openrouter model=deepseek/deepseek-v4-flash endpoint=https://openrouter.ai/api/v1/chat/completions max_tokens=500 reasoning_max_tokens=2000 interactive=True collapsed=True
```

Then run a search in SearXNG. You should see the AI answer stream in above the regular results.

### Other platforms

The same steps apply anywhere: place `ai_answers.py` into the `searx/plugins` directory of your instance (bare-metal installs), set the environment variables, and enable the plugin in `settings.yml`.

## Configuration

Configure via the environment variables:

### Required

- `LLM_PROVIDER`: openrouter, openai, ollama, localai, lmstudio, gemini, azure, or huggingface
- `LLM_KEY`: Provider API key (optional for local providers: ollama, localai, lmstudio)

### Optional

- `LLM_MODEL`: Model identifier. Defaults vary. Recommended: 10-30B dense or 5-15B MoE activated.
- `LLM_URL`: Overrides endpoint URL for any provider preset. Include the scheme — local providers usually need an explicit `http://`.
- `LLM_SYSTEM_PROMPT`: Overrides the persona line of the system prompt. Default `You are a direct, citation-accurate search synthesis engine.`.
- `LLM_MAX_TOKENS`: Answer token budget. Default `500`.
- `LLM_REASONING_MAX_TOKENS`: Extra token headroom for thinking/reasoning models, added on top of `LLM_MAX_TOKENS` in the API request. Without it, a reasoning model can spend the whole budget thinking and never produce the answer. Default `0`. Suggested `1000`–`4000` for models like DeepSeek V4 Flash in thinking mode.
- `LLM_EXTRA_BODY`: JSON object merged into the chat-completions request body — use for provider-specific parameters, e.g. `{"reasoning_effort": "high"}` (DeepSeek thinking effort) or `{"provider": {"order": ["..."]}}` (OpenRouter routing). Default unset.
- `LLM_TEMPERATURE`: Default `0.2`.
- `LLM_CONTEXT_DEEP_COUNT`: results as context with full snippets. Default `5`.
- `LLM_CONTEXT_SHALLOW_COUNT`: Results with headlines only (additional breadth). Default `15`.
- `LLM_TABS`: Tab whitelist, comma delimiter. Default `general,science,it,news`.
- `LLM_INTERACTIVE`: UI mode. Default is `true` (interactive: copy, regenerate, follow up). Set to `false` for simple response only mode.
- `LLM_COLLAPSED`: Show the answer as a fixed-height preview with a "Show more" button (no layout shift while streaming). Set to `false` for the always-expanded behavior. Default `true`.
- `LLM_QUESTION_MARK_REQUIRED`: Only trigger AI answers when the query contains `?`. Default `false`.
- `LLM_OLLAMA_UNLOAD_AFTER`: Unload Ollama model after each response. Default `false`.

## How It Works
1. user initial search
2. results return server side
3. `post_search` plugin hook entry
4. token optimized context extracted
5. inject the ui/logic "shell" into standard results answer object
6. client side script calls custom endpoint with signed token
7. LLM response streams back token by token; thinking (`reasoning_content` or `<think>` tags) renders into a collapsible box, and the finished answer is re-rendered as markdown with linked citations

## Examples

### DeepSeek V4 Flash via OpenRouter (recommended)
```
LLM_PROVIDER=openrouter
LLM_KEY=sk-or-xxx
LLM_MODEL=deepseek/deepseek-v4-flash
LLM_REASONING_MAX_TOKENS=2000
LLM_EXTRA_BODY={"reasoning_effort": "high"}
```

### OpenRouter
```
LLM_PROVIDER=openrouter
LLM_KEY=sk-or-xxx
LLM_MODEL=google/gemma-3-27b-it:free
```

### Ollama (Local)
```
LLM_PROVIDER=ollama
LLM_KEY=ollama
LLM_MODEL=llama3.2
```

### LocalAI
```
LLM_PROVIDER=localai
LLM_KEY=your-key
LLM_MODEL=gpt-4
LLM_URL=http://localai.lan:8080/v1/chat/completions
```

### Gemini
```
LLM_PROVIDER=gemini
LLM_KEY=AIzaSy...
LLM_MODEL=gemma-3-27b-it
```

### Azure
```
LLM_PROVIDER=azure
LLM_KEY=your-api-key
LLM_URL=https://your-resource.openai.azure.com/openai/deployments/your-deployment/chat/completions?api-version=2024-02-01
```

### Hugging Face
```
LLM_PROVIDER=huggingface
LLM_KEY=hf_xxx
LLM_MODEL=meta-llama/Meta-Llama-3-8B-Instruct
```

## Troubleshooting

- **`No module named 'searx.plugins.ai_answers'` / `plugin ... is not implemented`** — the file isn't where SearXNG expects it, or is misnamed. It must be mounted/placed at `searx/plugins/ai_answers.py` exactly (underscore, not hyphen).
- **`[SSL: WRONG_VERSION_NUMBER]` or name-resolution errors with a local provider** — your `LLM_URL` is being called over https. Use an explicit `http://` prefix for non-TLS local endpoints. The plugin logs a warning at startup when it has to assume a scheme.
- **Answer box never appears** — check `docker compose logs core` for the plugin's startup line. Missing `LLM_PROVIDER`/`LLM_URL` or `LLM_KEY` is logged as a warning. Also check the plugin is enabled in your own Preferences (it's per-user).
- **"Model provided reasoning but stopped before the final answer"** — the model spent the whole token budget thinking. Set `LLM_REASONING_MAX_TOKENS` (e.g. `2000`).
- **Ollama on the Windows host, SearXNG in Docker** — `localhost` inside the container refers to the container itself. Use `LLM_URL=http://host.docker.internal:11434/v1/chat/completions`.

## Development

```bash
pip install flask pytest
python -m pytest tests/            # unit tests
python tests/extract_frontend_js.py && node --check frontend_test.js   # JS syntax check
pip install flask-babel
python tests/demo.py               # UI demo at localhost:5000
```
