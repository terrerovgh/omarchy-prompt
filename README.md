# Prompt Improver for Omarchy

*[Leer en español](README.es.md)*

An [Omarchy](https://omarchy.org/) shell plugin that rewrites the prompt you have selected so it works better with the model you are sending it to. The rewrite follows that vendor's official prompting guide.

Select a prompt in any app and press **SUPER + ALT + P**. A themed card opens. It:

1. **Translates to English.** If the prompt is in another language, the card shows the detected language and an English translation.
2. **Lets you pick the target model and version.** It covers Claude, GPT, Gemini, Kimi, DeepSeek, Qwen, Meta (Muse / Llama), Grok, or a generic reasoning, chat or small-local model.
3. **Rewrites the prompt** using a guide distilled from that vendor's documentation (`guides/*.md`). The result shows what changed and which rule motivated each change.
4. **Detects the context.** The prompt gets a category, a subtype, a title and tags. Categories are coding, agent/tools, writing, analysis, extraction, summary, education, business, system prompt, image generation, and other.
5. **Saves every result** to a searchable history, which you can filter by category and model and mark with favorites.

Changing the model, version or context re-runs the rewrite right away. The translation is reused, so only the rewrite runs again.

## Keys

| Key | Improve view | History view |
|---|---|---|
| `SUPER + ALT + P` | Improve the selection (you add this binding) | |
| `Enter` / `Ctrl + C` | Copy the improved prompt and close | Copy the selected prompt and close |
| `Ctrl + R` | Rewrite again | |
| `Ctrl + F` | Toggle favorite | Toggle favorite |
| `Tab` | Move between the model / version / context selectors | Move to the filters |
| `Ctrl + H` | Switch to history | Back to improve |
| `↑ ↓` / `j k` | Scroll | Select |
| Typing, `Backspace`, `Ctrl + U` | | Search, edit, clear the search |
| `Ctrl + O` / double-click | | Open the entry in the improve view |
| `Del` (twice) | | Delete the entry |
| `Esc` / click outside | Close | Close |

`omarchy-prompt-selection --history` opens the history directly.

## Install

```bash
omarchy plugin add https://github.com/terrerovgh/omarchy-prompt --enable
ln -sf ~/.config/omarchy/plugins/io.github.terrerovgh.prompt-improver/bin/omarchy-prompt-selection ~/.local/bin/
```

Add the key binding to `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + ALT + P", "Improve selected prompt", os.getenv("HOME") .. "/.local/bin/omarchy-prompt-selection")
```

Then check it with `hyprctl reload && hyprctl configerrors`.

## Which LLM does the rewriting

The rewriting LLM (the "backend") is a separate choice from the target model. Configure it in `~/.config/omarchy-prompt/config.json`, which is created on first use. Set `"backend"` to one of the profiles:

| Profile | Type | Needs |
|---|---|---|
| `claude-cli` (default) | Runs `claude -p` without tools or session history, using your Claude Code login | Claude Code installed and logged in |
| `anthropic` | Claude API over HTTPS | An API key in `~/.config/omarchy-prompt/keys/anthropic` (mode 600) or `ANTHROPIC_API_KEY` |
| `openai`, `gemini`, `kimi`, `deepseek`, `openrouter` | Any OpenAI-compatible `/chat/completions` endpoint | A key file in `~/.config/omarchy-prompt/keys/<name>` (mode 600) |
| `ollama`, `s24-llama` | Local OpenAI-compatible server | No key |

```bash
./promptctl.py config set backend ollama
./promptctl.py config set profiles.ollama.model qwen3.6:27b
./promptctl.py config set profiles.claude-cli.model sonnet   # faster rewrites (~8 s instead of ~25 s with opus)
```

The plugin refuses key files that other users can read.

## Keeping the guides current

The guides are bundled so rewrites are fast and work offline. Each guide lists its sources and a `reviewed` date. To redraft them from the current official docs:

```bash
tools/refresh-guides.py                # drafts in guides/_sources/<family>.draft.md
diff -u guides/gemini.md guides/_sources/gemini.draft.md
tools/refresh-guides.py gemini --write # overwrite after reviewing
```

To add a model version, add an entry to `models.json`. To add a whole family, add an entry to `models.json` and a matching `guides/<family>.md`.

## Command-line use

```bash
echo "escribe un email anunciando una subida de precios" | ./promptctl.py improve --target openai/gpt-6-astra
./promptctl.py models
./promptctl.py history list --category coding --q sort
./promptctl.py history export --format md > prompts.md
./promptctl.py guide deepseek/r1        # show the guide a target uses
```

`improve` prints NDJSON progress lines (`translating`, `translated`, `rewriting`) and then a final `{"ok": true, ...}` object.

## Files

| File | Purpose |
|---|---|
| `manifest.json` | Plugin manifest (`overlay`) |
| `PromptImprover.qml` | The overlay card (Quickshell). UI only |
| `promptctl.py` | CLI that does all the work |
| `promptkit/` | Catalog, translation, backends, rewrite prompt and validation, SQLite history |
| `models.json` | Target families and versions, and the official source URLs |
| `guides/*.md` | Prompting guides distilled from official docs |
| `tools/refresh-guides.py` | Re-fetches the sources and drafts updated guides |
| `bin/omarchy-prompt-selection` | Reads the selection and opens the plugin |
| `tests/` | Offline tests: `python3 -m unittest discover -s tests` |

## Privacy and security

- **Translation:** the selected text is sent to Google Translate's keyless endpoints, just like omarchy-translate.
- **Rewriting:** the selected text is sent to the configured backend: Anthropic through Claude Code or the API, or whichever provider or local server you configure.
- **History:** stored locally in `~/.local/share/omarchy-prompt/history.sqlite3`.
- **No shell:** the selection is passed as a process argument and never runs through a shell. The Claude Code backend runs with all tools disabled, no MCP servers, no settings files, and no saved session, in an empty temporary directory.
- **Prompt injection:** the selected text is wrapped in tags and marked as material to rewrite, not instructions. Model output is validated against a JSON schema and always shown as plain text.
- **Limits:** input is capped at 20 000 characters and HTTP responses at 1 MB. The default timeout is 90 s.

## License

[MIT](LICENSE)
