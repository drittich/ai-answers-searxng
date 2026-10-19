# Replace the sparkles emoji on the Generate button with the bot icon

Status: resolved
Type: task

## What

Replace the ✨ emoji on the "You decide" Generate button with the bot icon the panel header already uses. Don't put a sparkle (emoji, icon or SVG) next to anything AI-related anywhere in the UI or docs.

The bot icon is the inline SVG in `.sxng-ai-header` (around line 2893, a Lucide-style "bot" with the `M12 6V2H8` path). Reuse that same SVG rather than a 🤖 Unicode emoji, so it matches the header and picks up the theme colour through `currentColor`. If it's needed in two places, pull it into a shared constant (like `GEAR_HTML`).

## Where

- `ai_answers.py` line 2889: `<button id="sxng-generate" ...>✨ Generate AI overview</button>`
- `README.md` line 169: the `manual` row in the modes table says **✨ Generate AI overview**. Drop the emoji there; the README can't show the SVG.
- `.scratch/ai-overview-frequency/issues/01-ai-overview-frequency-setting.md` mentions it too. That's history, so leave it.

The panel header's bot icon stays as it is. The CSS keyframes are named `sxng-sparkle-pulse` (line 2663). Users never see that name, but rename it (for example to `sxng-icon-pulse`) so the next person doesn't take it as a hint to add sparkles.

## Acceptance criteria

- [x] The Generate button shows the header's bot SVG before its label. It's sized to the text (about 1em), lined up vertically, and `aria-hidden`.
- [x] No ✨ (U+2728) or other sparkle glyph/icon in `ai_answers.py` or `README.md`.
- [x] `sxng-sparkle-pulse` renamed everywhere it's used (lines 2663, 2668, 2733).
- [x] Tests pass.

## Comments
- 2026-10-18: Implemented on branch `generate-button-polish` and reviewed; status changed to resolved.
