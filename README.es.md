# Prompt Improver para Omarchy

*[Read in English](README.md)*

Plugin del shell de [Omarchy](https://omarchy.org/) que reescribe el prompt que tengas seleccionado para que funcione mejor con el modelo al que lo vas a enviar. La reescritura sigue la guía oficial de prompting de cada proveedor.

![preview](preview.png)

Selecciona un prompt en cualquier aplicación y pulsa **SUPER + ALT + P**. Se abre una tarjeta con el tema actual que hace lo siguiente:

1. **Traduce al inglés.** Si el prompt está en otro idioma, muestra el idioma detectado y la traducción al inglés.
2. **Permite elegir el modelo y la versión de destino.** Cubre Claude, GPT, Gemini, Kimi, DeepSeek, Qwen, Meta (Muse / Llama), Grok, o un modelo genérico: de razonamiento, de chat o local pequeño.
3. **Reescribe el prompt** con una guía resumida de la documentación de ese proveedor (`guides/*.md`). Muestra qué cambió y qué regla de la guía motivó cada cambio.
4. **Detecta el contexto.** Asigna categoría, subtipo, título y etiquetas. Las categorías son código, agente/herramientas, escritura, análisis, extracción, resumen, educación, negocios, system prompt, imagen y otro.
5. **Guarda cada resultado** en un historial con búsqueda, filtros por categoría y modelo, y favoritos.

Al cambiar el modelo, la versión o el contexto, la reescritura se repite al momento. La traducción se reutiliza, así que solo se repite la reescritura.

## Teclas

| Tecla | Vista Mejorar | Vista Historial |
|---|---|---|
| `SUPER + ALT + P` | Mejora la selección (el atajo lo añades tú) | |
| `Enter` / `Ctrl + C` | Copia el prompt mejorado y cierra | Copia el prompt seleccionado y cierra |
| `Ctrl + R` | Reescribe de nuevo | |
| `Ctrl + F` | Marca o desmarca favorito | Marca o desmarca favorito |
| `Tab` | Pasa por los selectores de modelo, versión y contexto | Pasa a los filtros |
| `Ctrl + H` | Va al historial | Vuelve a Mejorar |
| `↑ ↓` / `j k` | Desplaza el texto | Selecciona |
| Escribir, `Retroceso`, `Ctrl + U` | | Busca, corrige y limpia la búsqueda |
| `Ctrl + O` / doble clic | | Abre la entrada en la vista Mejorar |
| `Supr` (dos veces) | | Borra la entrada |
| `Esc` / clic fuera | Cierra | Cierra |

`omarchy-prompt-selection --history` abre directamente el historial.

## Instalación

```bash
omarchy plugin add https://github.com/terrerovgh/omarchy-prompt --enable
ln -sf ~/.config/omarchy/plugins/io.github.terrerovgh.prompt-improver/bin/omarchy-prompt-selection ~/.local/bin/
```

En `~/.config/hypr/bindings.lua`:

```lua
o.bind("SUPER + ALT + P", "Mejorar prompt seleccionado", os.getenv("HOME") .. "/.local/bin/omarchy-prompt-selection")
```

Después compruébalo con `hyprctl reload && hyprctl configerrors`.

## Qué LLM hace la reescritura

El que reescribe (el «motor») es independiente del modelo de destino. Se elige en el selector **Motor** de la tarjeta, que lista solo las herramientas CLI de IA que encuentra instaladas:

| Motor | CLI | Modelo por defecto | Cómo se desactivan las herramientas |
|---|---|---|---|
| pi | `pi` | DeepSeek Flash | `--no-tools --no-session --no-context-files` |
| Claude | `claude` (Claude Code) | Sonnet 5.5 | `--tools ""`, sin MCP, sin settings, sin guardar sesión |
| Codex | `codex exec` | GPT-6 Luna | `--sandbox read-only`, `--ephemeral` |
| Antigravity | `agy` | Gemini 4 Hydrogen (`-low`) | En modo headless deniega las herramientas que piden aprobación (comandos, ediciones); nunca se pasa `--dangerously-skip-permissions`; sin slash commands |
| Kimi | `kimi` (Kimi Code) | K2.8 Preview (`kimi-for-coding`) | Agente propio con `tools: []` |
| OpenCode | `opencode run` | El que tenga configurado | Agente temporal con permisos que lo deniegan todo |
| Hermes | `hermes -z` | El que tenga configurado | **Desactivado por defecto:** Hermes no permite desactivar sus herramientas. Se habilita con `profiles.hermes.allow_tools: true` |

El motor por defecto es **pi**. **Auto** usa la primera herramienta instalada en el orden de la tabla, y pi va primero. Elegir otro motor en la tarjeta vale solo para esa vez; para cambiar el predeterminado: `./promptctl.py config set backend claude`.

Una herramienta cuenta como instalada solo si responde a `--version`, así que los shims viejos de mise no aparecen. La detección se guarda en caché 6 horas; `./promptctl.py engines --refresh` la repite. Cada ejecución corre en un directorio temporal vacío.

Claude, Codex, Antigravity, Kimi y pi se probaron de verdad, incluida una comprobación de que una selección que le pide al motor ejecutar `touch` no consigue crear el archivo. Los adaptadores de OpenCode y Hermes siguen su documentación oficial, pero no se han ejecutado.

Los perfiles de API (`anthropic-api`, `openai-api`, `gemini-api`, `kimi-api`, `deepseek-api`, `openrouter`) aparecen en el selector cuando existe su archivo de clave en `~/.config/omarchy-prompt/keys/<nombre>` con permisos 600. Los locales (`ollama`, `s24-llama`) aparecen cuando pones `"enabled": true`.

Para cambiar un modelo, edita `~/.config/omarchy-prompt/config.json`:

```bash
./promptctl.py config set profiles.claude.model claude-haiku-5-5
./promptctl.py config set profiles.kimi.model kimi-code/kimi-for-coding-highspeed
```

Si el modelo escribe el prompt mejorado en otro idioma que no sea el inglés, el plugin lo detecta y se lo vuelve a pedir una vez.

## Actualizar las guías

```bash
tools/refresh-guides.py                # borradores en guides/_sources/<familia>.draft.md
diff -u guides/gemini.md guides/_sources/gemini.draft.md
tools/refresh-guides.py gemini --write # sobrescribe la guía, después de revisarla
```

Para añadir una versión de modelo, edita `models.json`. Para añadir una familia nueva, edita `models.json` y crea su `guides/<familia>.md`.

## Privacidad y seguridad

- **Traducción:** el texto se envía a Google Translate, igual que en omarchy-translate.
- **Reescritura:** el texto se envía al backend que hayas configurado.
- **Historial:** se guarda solo en local, en `~/.local/share/omarchy-prompt/history.sqlite3`.
- **Sin shell:** la selección nunca pasa por un shell. Cada motor CLI corre con sus herramientas desactivadas (ver la tabla de motores), en un directorio temporal vacío. Kimi Code guarda igualmente una sesión por ejecución, porque no tiene opción para evitarlo.
- **Inyección de prompts:** el texto seleccionado se trata como material a reescribir, nunca como instrucciones. La respuesta del modelo se valida con un esquema JSON y siempre se muestra como texto plano.

## Licencia

[MIT](LICENSE)
