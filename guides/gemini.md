---
family: gemini
reviewed: 2026-11-14
sources:
  - https://aistudio.google.com/docs/prompting-strategies
  - https://aistudio.google.com/docs/whats-new-gemini-3.6
  - https://aistudio.google.com/docs/models
---

# Prompting Gemini (Google)

## Core rules
- Write direct, precise prompts. Gemini 3+ and 4 respond best to clear instructions and may over-analyze verbose or persuasive wording written for older models. Ask for a conversational or detailed tone explicitly if you want one, because the default is concise.
- Put the role, behavioral constraints and output format at the start of the system instruction or the prompt.
- Long context: put all the documents or data first and the question or task last, bridged by a phrase such as "Based on the information above, …".
- Separate the parts with consistent delimiters: XML-style tags or Markdown headings. Pick one style and do not mix them.
- State constraints explicitly, including what not to do and length ("in one sentence", "under 200 words").
- Specify the output format: table, bullets, paragraph, JSON, keywords. A response prefix such as "Output:" or a partial outline helps the model follow a pattern. For complex JSON, recommend structured output (a response schema) instead of prompt-only formatting.
- Classification: list the allowed labels and ask for exactly one.
- To ground the answer, supply the reference material and say "answer only from the provided text". Without context, answers are generic.

## Few-shot examples
- Gemini benefits strongly from few-shot examples, which show format, phrasing, scope and length. Use a few specific, varied examples. Too many cause overfitting.
- Keep every example's structure identical (tags, whitespace, separators). With clear examples, long explicit instructions can be dropped.

## Reasoning
- Gemini 2.5, 3.x and 4 think internally, so do not ask the response to lay out its reasoning. For a genuinely hard problem, "think carefully about X before answering" can help, at a token cost. Prefer setting thinking depth through the API (`thinking_level`).
- For recent facts, suggest Google Search grounding. For arithmetic or counting, suggest code execution.
- Gemini 3 Flash class: a system clause stating the current date and its knowledge cutoff improves time-sensitive answers.

## Agentic system instructions
- Ask the agent to plan before each action: prerequisites and policy checks, dependency order, risks, and alternative hypotheses when something fails.
- Distinguish low-risk actions (reads, searches), which proceed without asking, from high-risk ones (writes, sends), which need confirmation.
- Retry rules: retry transient errors up to N times, and change strategy instead of repeating an identical failed call.
- Say when the agent may assume and when it must ask, and whether it should narrate tool calls or stay quiet.

## Version notes
- **Gemini 4 Carbon:** strongest reasoning, for complex engineering, multimodal, science and security work. Give the full goal and success criteria. Scaffolding is unnecessary.
- **Gemini 4 Argon:** efficient frontier reasoning. Same rules as Carbon, with somewhat tighter scope.
- **Gemini 4 Hydrogen:** fast, for everyday coding and agentic workflows. Use clear task boundaries and an explicit output format.
- **Gemini 3.8 Flash / 3.6 Flash:** strong at software engineering and agents. They tend to run diagnostics before acting, so say when a quick change is enough. UI work needs explicit design guidelines (typography, spacing, colors).
- **Gemini 3.1 Pro:** reasoning-heavy. Keep prompts short and direct.
- **Gemini 3.5 Flash-Lite:** high-volume extraction, routing and classification. Use an explicit label set, an exact output format and examples.
- **Gemini 2.5 (legacy):** replace elaborate chain-of-thought scaffolding with plain instructions. Being deprecated: suggest Gemini 4 Hydrogen.

## Anti-patterns to remove
- Persuasive or emotional wording.
- Mixed delimiter styles.
- Key instructions buried in the middle of long context.
- Inconsistent example formats.
- Relying on the model for recent facts or exact math without tools.
- Prefilled model turns (not supported on Gemini 3+).
- Temperature or top_p advice (ignored on 3.6+ and 4).
