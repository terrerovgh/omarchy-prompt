# Prompt Improver for Omarchy

*[Leer en español](README.es.md)*

An [Omarchy](https://omarchy.org/) shell plugin that rewrites the prompt you have selected so it works better with the model you are sending it to. The rewrite follows that vendor's official prompting guide.

![preview](preview.png)

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

## Uninstall

```bash
omarchy plugin remove io.github.terrerovgh.prompt-improver
rm -f ~/.local/bin/omarchy-prompt-selection
```

Then delete the `o.bind("SUPER + ALT + P", ...)` line from `~/.config/hypr/bindings.lua`. The plugin keeps its settings and history outside the plugin folder. Remove them too if you want a clean slate:

```bash
rm -rf ~/.config/omarchy-prompt ~/.local/share/omarchy-prompt ~/.cache/omarchy-prompt
```

## Dependencies

- `python3` (standard library only) and `wl-clipboard` (`wl-paste`, `wl-copy`). Omarchy ships both.
- At least one rewriter: Codex or Claude Code (built in), an optional CLI integration (pi, Kimi Code, Antigravity, OpenCode), or an API key for one of the API profiles.
- An internet connection. Translation uses Google Translate's keyless endpoints, and rewriting uses the provider behind the chosen engine. A local engine such as Ollama keeps the rewrite on your machine.

## Which LLM does the rewriting

The rewriter (the "engine") is a separate choice from the target model. Pick it in the card's **Engine** selector.

**Built-in engines.** Two engines come built in and are detected automatically. **Auto** uses the first one that is installed:

| Engine | CLI | Model | How tools are kept off |
|---|---|---|---|
| Codex | `codex exec` | GPT-6 Luna | Shell, unified exec, code mode, apps, plugins, hooks and browser features disabled; your `config.toml` and rules ignored (no MCP servers); web search off; `--sandbox read-only`, `--ephemeral`. If Codex still calls any tool, the result is thrown away |
| Claude | `claude` (Claude Code) | Sonnet 5.5 | `--tools ""`, no MCP, no settings, no saved session |

**Optional integrations.** Other AI CLIs are optional integrations, the way herdr handles its agent integrations. Their code is not loaded and their CLI is not probed until you install the integration:

```bash
./promptctl.py integration list              # built-in engines, integrations, and whether each CLI is found
./promptctl.py integration install pi
./promptctl.py integration uninstall pi
```

| Integration | CLI | Model | How tools are kept off |
|---|---|---|---|
| `pi` | `pi` | pi's configured model | `--no-tools --no-session --no-context-files --no-mcp` |
| `kimi` | `kimi` (Kimi Code) | Kimi Code's `default_model` | Custom agent file with `tools: []` |
| `antigravity` | `agy` | agy's default model | Headless mode auto-denies tools that need approval; `--dangerously-skip-permissions` is never passed; slash commands off |
| `opencode` | `opencode run` | OpenCode's default model | Temporary agent whose permissions deny everything (adapter not run yet) |
| `hermes` | `hermes -z` | Hermes's default model | Cannot disable its tools, so it stays blocked until you set `profiles.hermes.allow_tools: true` (adapter not run yet) |

A tool counts as installed only when it answers `--version`, so leftover shims are ignored. Detection is cached for 6 hours; add `--refresh` to re-check. Every run happens in an empty private temporary directory. Codex, Claude, pi, Kimi and Antigravity were tested for real, including checks that a selection asking the engine to run `touch` cannot create a file, and that one asking it (or a Codex sub-agent) to `cat` another file cannot read it.

**API profiles.** `anthropic-api`, `openai-api`, `gemini-api`, `kimi-api`, `deepseek-api` and `openrouter` appear in the selector once their key file exists in `~/.config/omarchy-prompt/keys/<name>` with mode 600. The local `ollama` and `s24-llama` profiles appear once you set `"enabled": true`.

**Your own default.** The default and the models are personal settings in `~/.config/omarchy-prompt/config.json`. Picking an engine in the card applies to that card only. For example, to make pi with DeepSeek Flash your default:

```bash
./promptctl.py integration install pi
./promptctl.py config set backend pi
./promptctl.py config set profiles.pi.model deepseek/deepseek-flash
./promptctl.py config set profiles.pi.model_label "DeepSeek 4.1 Flash"   # label shown in the selector
```

If the model writes the improved prompt in a language other than English, the plugin notices and asks once more.

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
| `promptkit/engines.py` | Engine registry, CLI detection, and the runner (tools off, private temp dir) |
| `promptkit/integrations/` | One adapter per CLI: built-in `codex`, `claude`; optional `pi`, `kimi`, `antigravity`, `opencode`, `hermes` |
| `tests/` | Offline tests: `python3 -m unittest discover -s tests` |

## Privacy and security

- **Translation:** the selected text is sent to Google Translate's keyless endpoints, just like omarchy-translate.
- **Rewriting:** the selected text is sent to the configured backend: Anthropic through Claude Code or the API, or whichever provider or local server you configure.
- **History:** stored locally in `~/.local/share/omarchy-prompt/history.sqlite3`. The folder is created `0700` and the database `0600`, whatever your umask, and older installs are tightened the next time the plugin runs, so other accounts on the machine cannot read your prompts.
- **Never in a command line:** the launcher does not read the selection. The plugin reads it with `wl-paste` through a pipe, and passes text to `promptctl.py`, the engines and `wl-copy` only through stdin or files in a private temporary directory (mode 700). Other local accounts cannot see it in `/proc/*/cmdline`, and it never runs through a shell. Every CLI engine runs with its tools off (see the engine table), in an empty temporary directory. Kimi Code still records a session per run, because it has no option to skip that.
- **Prompt injection:** the selected text is wrapped in tags and marked as material to rewrite, not instructions. Model output is validated against a JSON schema and always shown as plain text.
- **Limits:** input is capped at 20 000 characters and HTTP responses at 1 MB. The default timeout is 90 s.

## Developing

The Omarchy shell reads this plugin's QML once, when the shell starts, because the plugin folder is outside Quickshell's config folder. After editing `PromptImprover.qml` or `i18n/`, run `omarchy restart shell`. The Python side runs fresh on every request and needs no restart.

## License

[MIT](LICENSE)
