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

El LLM que reescribe (el «backend») es independiente del modelo de destino. Se configura en `~/.config/omarchy-prompt/config.json`, que se crea la primera vez que usas el plugin. En `"backend"` pones uno de estos perfiles:

| Perfil | Qué es | Requisitos |
|---|---|---|
| `claude-cli` (por defecto) | `claude -p` sin herramientas ni sesión guardada, con tu login de Claude Code | Claude Code instalado y con sesión iniciada |
| `anthropic` | La API de Claude por HTTPS | Clave en `~/.config/omarchy-prompt/keys/anthropic` (permisos 600) o `ANTHROPIC_API_KEY` |
| `openai`, `gemini`, `kimi`, `deepseek`, `openrouter` | Cualquier endpoint `/chat/completions` compatible con OpenAI | Clave en `~/.config/omarchy-prompt/keys/<nombre>` (permisos 600) |
| `ollama`, `s24-llama` | Un servidor local compatible con OpenAI | Ninguno |

```bash
./promptctl.py config set backend ollama
./promptctl.py config set profiles.claude-cli.model sonnet   # más rápido (~8 s en vez de ~25 s con opus)
```

El plugin rechaza los archivos de clave que otros usuarios puedan leer.

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
- **Sin shell:** la selección nunca pasa por un shell. El backend `claude-cli` corre sin herramientas, sin servidores MCP y sin archivos de configuración, en un directorio temporal vacío.
- **Inyección de prompts:** el texto seleccionado se trata como material a reescribir, nunca como instrucciones. La respuesta del modelo se valida con un esquema JSON y siempre se muestra como texto plano.

## Licencia

[MIT](LICENSE)
