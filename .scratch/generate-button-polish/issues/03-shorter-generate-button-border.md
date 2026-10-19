# Make the Generate button's border about half as tall

Status: ready-for-agent
Type: task

## What

The pill border around the Generate button is too tall. Make it about **half its current height**, with the text still centred vertically inside it.

## Where

`ai_answers.py`, `OVERVIEW_MODE_CSS`:

- `.sxng-generate-btn` (around line 281): `padding: 0.3rem 0.8rem; font-size: 0.9rem;`. Its height comes from the vertical padding plus the line-height inherited from the theme.
- `@media (pointer: coarse)` (around line 359): `.sxng-generate-btn { padding: 0.55rem 1rem; }` for touch.

Measure the current rendered height in the default SearXNG theme (simple), then cut it to about half. That probably means less vertical padding and an explicit `line-height` (for example `1.2`), with `display: inline-flex; align-items: center` if needed to keep the text centred. Keep the horizontal padding and the 999px radius.

On touch (`pointer: coarse`) the 44px tap target matters. If the visible pill gets shorter there, keep the tap area large with an invisible hit area (for example a pseudo-element or transparent outer padding) instead of a tall border.

The gear button next to it (`.sxng-gear`, 28px) should still line up vertically with the shorter pill in `.sxng-generate-row`.

## Acceptance criteria

- [ ] On desktop, the button's border box is about 50% of its current height.
- [ ] The label is centred vertically.
- [ ] The gear and the button line up in the row.
- [ ] On touch, the tap target stays ≥44px tall even if the visible pill is shorter.
- [ ] Checked in light and dark themes.

## Comments
