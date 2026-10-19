# AI overview frequency setting

Status: resolved
Type: task

## What

Let each user choose how often the AI overview is shown. There are four options: **Always**, **It decides**, **You decide** and **Never**.

## Design

### Where the user picks it

- Add a gear icon to the answer panel header and to the "You decide" button row, in both interactive and simple modes. Clicking it opens a menu with the four options.
- Save the choice in a cookie that the server reads in `post_search`. Set the path to the SearXNG script root, a one-year expiry and `SameSite=Lax`.
- A changed choice takes effect on the next search. The current page doesn't have to re-render.

### The modes

| Mode | Cookie / env value | Behaviour |
| --- | --- | --- |
| Always | `always` | Same as today: generate an overview for every eligible search. |
| It decides | `auto` | A rule on the server decides (see below). When it skips, show the "You decide" button instead. |
| You decide | `manual` | Show a one-line "✨ Generate AI overview" button where the panel normally sits. The context is already in the page, and clicking starts the stream straight away. The panel then grows below the button. Moving the results down is fine here because the user asked for it. |
| Never | n/a | This is the existing per-user plugin switch on the SearXNG Preferences page. The "Never" option in the menu explains this and links to Preferences. Turning the switch back on restores the panel. |

### The "It decides" rule (server-side, no AI request)

Generate an overview when **any** of these is true:

- the query contains `?`
- the query starts with a question word: who, what, why, how, when, where, which, is, are, can, does, do, should, explain, compare, difference (English-only for now)
- the query has 5 or more words (fixed in the code, not configurable)

Skip it when SearXNG already returned a direct answer (a calculator result, for example) or an infobox.

### Admin default

- Add a new env var: `LLM_OVERVIEW_MODE=always|auto|manual`, default `always`, so current installs behave the same. A user's cookie overrides it.
- Reject `never` and any other value, log a warning and fall back to `always`. Admins who want overviews off by default for new users use the plugin's existing `active: false` in `settings.yml`.

### Shared links and cached answers

A shared `#ai=` link or a cached answer for the same search (in `sessionStorage`) is **always** restored and shown, whatever the mode, including when the mode would otherwise show the button or nothing.

### `LLM_QUESTION_MARK_REQUIRED`

Its behaviour stays the same: it's an extra condition applied in every mode. When it's set, log a deprecation warning that points to `LLM_OVERVIEW_MODE=auto`. It will be removed in a later release.

## Acceptance criteria

- [ ] The gear menu appears in the panel header and on the "You decide" button row, in both interactive and simple modes.
- [ ] Choosing a mode writes the cookie, and the next search respects it.
- [ ] `always`: current behaviour, with no regressions.
- [ ] `auto`: the rule works as specified, and a skipped search shows the "Generate" button.
- [ ] `manual`: no AI request until the button is clicked, after which the stream starts straight away.
- [ ] The menu's "Never" option explains the Preferences switch and links to it.
- [ ] `LLM_OVERVIEW_MODE` is parsed and validated, and an invalid value logs a warning and falls back to `always`.
- [ ] Shared `#ai=` links and cached answers are restored in every mode.
- [ ] `LLM_QUESTION_MARK_REQUIRED` behaves as before and logs a deprecation warning.
- [ ] README documents the setting and `LLM_OVERVIEW_MODE`.
- [ ] pytest covers the rule, reading the cookie and env var, and choosing the mode in `post_search`.

## Comments

- 2026-10-17: Design settled in a grilling session; status changed from needs-triage to ready-for-agent.
- 2026-10-18: Implemented (commits 4b1b80e, 3fd9545); status changed from ready-for-agent to resolved. Follow-up polish tracked in `.scratch/generate-button-polish/`.
