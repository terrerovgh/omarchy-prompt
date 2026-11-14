---
family: claude
reviewed: 2026-11-14
sources:
  - https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview
  - https://platform.claude.com/docs/en/about-claude/models/overview.md
  - Anthropic "claude-api" skill (prompt-audit and model-migration guides), cached 2026-11-03
---

# Prompting Claude (Anthropic)

## Core rules
- Current Claude models follow instructions closely and literally. Say exactly what you want, at normal volume. Write "Use X when…", not "CRITICAL: you MUST…". Aggressive emphasis now causes over-triggering.
- Give the context and the reason behind each constraint. "Keep answers short because they are read on a phone" works better than "Be brief". Claude generalizes from the reason.
- Describe the goal and what success looks like, not a step-by-step script. Hand-written STEP 1/STEP 2 choreography for judgment tasks makes the output worse on current models. Keep exact steps only for fragile, mechanical operations.
- Structure long prompts with XML tags: `<context>`, `<instructions>`, `<document>`, `<examples>`, `<output_format>`. Put long documents or data first and the question or task last.
- Name the audience, the purpose and the quality bar in one or two plain sentences. A short role line is fine as a focus-setter, but it does not replace real context.
- Examples are the strongest signal in a prompt. The model copies their length, tone and structure. Use two or three varied examples inside `<example>` tags, or none. Never use one gold example that the model will clone.
- Describe what to do rather than listing what not to do. Keep only the prohibitions that guard a real, likely failure, and give the reason for each.
- To control the format, describe the output you want, for example "Answer in flowing prose paragraphs". Claude matches the prompt's own style, so a prompt full of bullets gets bullets back.
- When information is missing, the prompt can ask Claude to state its assumptions or ask one clarifying question instead of guessing.

## Reasoning and thinking
- Claude 4.6+ and every 5.x model use adaptive thinking, and the API controls its depth (effort). Do not write "think step by step", "use a scratchpad", "think harder" or `<thinking>` tag instructions. They are redundant and can hurt.
- Do not ask for the reasoning in the output (reasoning fields in JSON, "show your work") unless the user needs it. If an explanation helps the reader, ask for a short explanation of the answer.
- Do not plan the model's thinking for it. "Plan before acting" causes over-planning on current models.

## Agentic and coding prompts
- State the end goal, the constraints (files or areas that are off-limits, actions that need confirmation) and the definition of done, for example "tests pass" or "the PR is ready to review".
- Say which actions are reversible and can be taken freely, and which ones (deploy, delete, send) need a check-in first.
- Do not add "be thorough / do not stop early / do not be lazy". Current models are proactive by default. On Fable 5.2, if the task is long, state that it should be finished end to end.
- Ask for brief progress notes and a final summary of what changed and what was verified. Do not suppress all updates.
- Do not discourage tool use ("only use tools when strictly necessary"). Sonnet 5.5 follows such lines literally and under-uses tools.

## Output and length
- Set length qualitatively: "a short paragraph" or "as long as the question needs". Hard word caps starve reasoning on hard problems.
- For machine-readable output, ask for JSON matching a schema the prompt describes, and suggest that the caller use structured outputs. Do not rely on "output ONLY JSON" stacks or prefill. Prefill is not supported on 4.6+ and 5.x.

## Version notes
- **Fable 5.2:** most capable model, for long-horizon agentic work. Prompts written for older models are often too prescriptive, so trim scaffolding and give the full task spec up front. Thinking is always on. Set length in the prompt, because effort barely changes reply length.
- **Opus 5.5:** the default flagship. Thinking cannot be disabled. Strong vision, so skip chart-reading or OCR pre-steps. Under-formats rather than over-formats: ask for headers or tables when you want them.
- **Sonnet 5.5:** fast everyday coding and agent model. It takes tool-use limits literally and tends to answer chat questions from its own knowledge: say when it should use tools or search.
- **Haiku 5.5:** cheap and fast. Give tighter, more explicit instructions and one or two examples for format. Keep prompts short and focused on a single task.
- **Opus 5 / Sonnet 5 / Opus 4.8:** same principles. Thinking may be off on some deployments, so do not add anti-thinking rules.
- **Claude 4.x (Sonnet 4.6, Haiku 4.5):** more literal than 3.x. Explicitly ask for "above and beyond" behavior if wanted. XML structure and examples help more here.

## Anti-patterns to remove
- ALL-CAPS pressure words and repeated IMPORTANT/NEVER lines.
- "You are a helpful assistant" as the only context.
- "Think step by step" or scratchpad instructions on thinking models.
- Bullet walls of generic virtues: "be accurate, thorough, clear".
- Mentions of graders, hidden tests or "you will be evaluated".
- Hard output word caps on hard tasks.
- Contradictory rules.
