# Rename the Generate button to "Generate AI Summary"

Status: ready-for-agent
Type: task

## What

Change the Generate button label from "Generate AI overview" to exactly **Generate AI Summary**, after the bot icon (see 01).

## Where

- `ai_answers.py` line 2889: the `#sxng-generate` button text.
- `README.md` line 169: the `manual` row in the modes table.
- Look for other places that quote the label word for word, such as tests (`tests/test_plugin.py`, `tests/demo.py`) and the gear menu's "You decide" description, "Only when you click Generate" (line 264). That description still works, so leave it unless it quotes the full label.

Out of scope: renaming "AI overview" elsewhere (menu title "Show AI overviews", aria labels, README prose). Only the button label changes.

## Acceptance criteria

- [ ] The button reads `Generate AI Summary`.
- [ ] README matches.
- [ ] Tests that check the label are updated and pass.

## Comments
