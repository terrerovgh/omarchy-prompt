---
family: grok
reviewed: 2026-11-14
sources:
  - https://docs.x.ai/docs/models
---

# Prompting Grok (xAI)

xAI's docs have no dedicated prompt-engineering guide. These rules come from their model docs plus OpenAI-compatible conventions, since the Grok API uses that format.

## Core rules
- `system`, `user` and `assistant` messages can be mixed in any order. Put stable rules in a system message at the start.
- Grok does not know events after its training cutoff (May 2026 for Grok 4.7). For current information, tell it to use Web Search or X Search, or provide the facts inline.
- Write the goal, the constraints and the output format explicitly, and delimit documents with tags or headings.
- Images (JPG/PNG) can be interleaved with text in any order. Refer to them by position ("the second image").

## Reasoning
- Grok 4.7 and the 4.20 reasoning models reason internally. Do not add "think step by step". Give goals and success criteria.
- Grok 4.20 non-reasoning: explicit step lists and an example help on multi-step tasks.

## Version notes
- **Grok 4.7:** most capable. Recommended for code and chat. Use goal-first prompts with a full task spec.
- **Grok 4.20 reasoning / multi-agent:** 1M context. Put long documents first, then the task.
- **Grok 4.20 non-reasoning:** fast. Use precise instructions and a fixed format.

## Anti-patterns to remove
- Asking for recent news without enabling search.
- Chain-of-thought incantations on reasoning variants.
