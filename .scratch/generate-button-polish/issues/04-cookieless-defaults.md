# Default to "You decide" and no follow-up suggestions for users without cookies

Status: resolved
Type: task

## What

A user with no cookies (no `ai_answers_mode` cookie and no saved SearXNG preferences) should get:

- **Overview mode: You decide** (`manual`), which shows the Generate button and makes no AI request until it's clicked.
- **No follow-up suggestions**: the "Follow-up questions" chips are off.

Assumption: the request said "no auto-response suggestions". This ticket reads that as the follow-up question chips (`AIFollowupsPlugin` / `LLM_FOLLOWUPS`). If it meant something else, set this back to `needs-info`.

## Where

### Overview mode

- `ai_answers.py` `_load_config` (around lines 1722–1732): when `LLM_OVERVIEW_MODE` is unset, the fallback is `'always'`. Change the built-in default, and the fallback for invalid values, to `'manual'`.
- `_overview_mode` (around line 2473): the cookie still wins, and the admin env var still wins over the built-in default.
- Update the warning text for invalid values ("Falling back to 'always'").
- This reverses a decision in `.scratch/ai-overview-frequency/issues/01-ai-overview-frequency-setting.md` ("default `always`, so current installs behave the same"). Existing installs that don't set `LLM_OVERVIEW_MODE` will now show the button instead of auto-generating. Add a note to the README / changelog about that.

### Follow-up suggestions

- `AIFollowupsPlugin.active = False` (around line 2944) already makes the per-user switch default to off, and the `LLM_FOLLOWUPS` fallback (line 1716) already defaults to `false`. So the code may already be correct. Check this on the actual deployment: if follow-up chips show up with no cookies there, the cause is the instance config (`LLM_FOLLOWUPS=true` or `active: true` for the plugin in `settings.yml`), not this code. Note what you find in the comments below.
- Add a test that confirms cookieless requests get no follow-ups when the companion plugin is registered with its default state.

## Acceptance criteria

- [x] With no cookie and no `LLM_OVERVIEW_MODE`, `post_search` picks `manual` (the Generate button shows and no AI request is made).
- [x] An invalid `LLM_OVERVIEW_MODE` falls back to `manual`, with an updated warning.
- [x] `LLM_OVERVIEW_MODE=always|auto` and the user's cookie still override it.
- [x] Shared `#ai=` links and cached answers still restore in `manual` mode.
- [x] With no cookies, no follow-up chips show and the follow-up prompt instruction isn't sent.
- [x] README updated: the `LLM_OVERVIEW_MODE` default is now `manual`, plus a migration note.
- [x] pytest covers the new default and the invalid-value fallback.

## Comments

- Follow-up defaults (code check; the live deployment was not reachable from the agent): the code already defaults to off. `LLM_FOLLOWUPS` falls back to `false`; when `AIFollowupsPlugin` is registered, its per-user choice wins, and SearXNG seeds a cookieless user's choice from the plugin's `active`, which `Plugin.__init__` takes from `settings.yml` (the class attribute `active = False` is overwritten by the config value). So if chips show for cookieless users on the deployment, check `settings.yml` for `AIFollowupsPlugin: active: true` (or, with the companion not registered, `LLM_FOLLOWUPS=true`). Note that a registered companion with `active: false` beats `LLM_FOLLOWUPS=true`. Added `test_cookieless_user_gets_no_followups_with_companion_plugin_default`, which covers both the rendered page (`show_followups = false`) and the `/ai-stream` prompt (no `<<FOLLOWUPS>>` instruction).
- 2026-10-18: Implemented on branch `generate-button-polish` and reviewed; status changed to resolved.
