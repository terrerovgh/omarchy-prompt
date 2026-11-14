---
family: meta
reviewed: 2026-11-14
sources:
  - https://dev.meta.ai/llama/docs/how-to-guides/prompting/
---

# Prompting Meta models (Muse, Llama)

## Core rules (Meta's official prompting guide)
- Detailed, explicit instructions produce better results than open-ended prompts. Treat rules as limits on how the model responds.
- Stylization: say the style or persona ("explain as if to a high-school student", "answer as a senior SRE").
- Formatting: request the exact output format (bullets, JSON object with named fields, table).
- Restrictions: state what the model must not do, such as limiting sources to a date range or answering "I don't know" when unsure.
- Few-shot examples give "a more accurate, consistent output" than zero-shot. Include two or three when format or style matters.
- Role-based prompts improve relevance, and the role should come with the context it needs.
- To limit extraneous tokens, combine a role, rules, explicit instructions and an example. This suppresses filler text and enforces JSON-only output.
- RAG: insert the retrieved facts into the prompt, clearly delimited, and ask the model to answer from them.
- Arithmetic: ask the model to write code for the calculation (program-aided generation) instead of computing in prose.
- Reduce hallucination: supply context, specify the perspective, and ask for sources.

## Reasoning
- Non-reasoning Llama models: chain-of-thought helps. Guide the model through a short sequence of steps or ask it to reason before answering.
- Muse Spark (reasoning): give goals and success criteria and skip step-by-step scaffolding.

## Version notes
- **Muse Spark 1.3 / Spark Open:** Meta's current reasoning models. Use goal-first prompts with explicit output format.
- **Llama 4 (Maverick / Scout):** explicit instructions plus examples. A system prompt sets the role and the rules.
- **Llama 3.x local:** small context windows in practice and weaker instruction following. Keep prompts short, use one task per prompt, give an example, and put the output format last.

## Anti-patterns to remove
- Open-ended asks with no format.
- Asking for exact math in prose.
- Long, unfocused prompts for small local models.
