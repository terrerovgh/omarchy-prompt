---
family: openai
reviewed: 2026-11-14
sources:
  - https://developers.openai.com/api/docs/guides/latest-model
  - https://developers.openai.com/api/docs/guides/prompt-engineering
  - https://developers.openai.com/api/docs/guides/reasoning-best-practices
  - https://developers.openai.com/api/docs/models
---

# Prompting GPT (OpenAI)

## Core rules
- Separate the rules from the input. In API use, rules and business logic go in the `developer` message and the inputs go in the `user` message: "the developer message is the function definition, the user message its arguments". For a chat prompt, put the rules first and the input last.
- Lay out the prompt in this order: identity or role → instructions → examples → context. Put the stable content first and the variable context (documents, data) near the end.
- Use Markdown headers and lists to mark sections. Use XML tags to delimit documents or data, with attributes for metadata the instructions refer to.
- Lead with the result you want: goal → context → output format → boundaries. Do not open with procedural steps.
- Unclear or conflicting instructions destabilize current GPT models more than missing detail does. Remove contradictions and duplicate rules, and keep one clear rule per behavior.
- For few-shot, use a handful of diverse input/output pairs plus an explicit output constraint. Do not use near-duplicate examples.

## Reasoning models (all GPT-6 models, GPT-5.x, o-series)
- These are reasoning models. Give high-level goals and success criteria and let them work out the method. Treat them like a senior co-worker, not a junior one.
- Do not write "think step by step" or ask them to explain their reasoning. They reason internally, and these prompts can hurt.
- Try zero-shot first. Add examples only for complex output formats, and make them match the instructions exactly.
- State the end goal and constraints, such as budget, scope and files not to touch, and ask the model to keep iterating until the success criteria are met.
- Reasoning models in the API avoid Markdown by default. If formatted output is wanted, start the developer message with "Formatting re-enabled".

## Agentic prompts (GPT-6 Astra / 6.1 Sol)
- Tell the model to infer intent from context and carry the work through to completion. It should treat "can you…" or "help me…" as a request to act, not to describe a plan.
- Draw the autonomy line explicitly: reversible, low-impact steps proceed without asking. Destructive or irreversible steps (deploy, merge, publish, external writes) are prepared fully, with the user's approval as the final step.
- Forbid unsolicited warnings and disclaimers based on hypothetical risk. Say which questions are worth asking and which should be answered with a stated assumption.
- Testing: ask for tests suited to the change. Skip tests for trivial reversible edits, and do not write tests that just mirror the implementation.
- State that explicit user instructions override any skill or AGENTS.md guidance.

## Writing style guidance that works well
- Ask for concise paragraphs that each develop one idea, with the main point first. Lists only for parallel, sequential or comparison content, and no nested lists.
- Plain language, active voice, concrete examples, and jargon matched to the reader.
- Ban filler words and stock conclusions. Avoid unrequested "X, not Y" contrastive framing.

## Version notes
- **GPT-6 Astra:** most capable. It follows long instructions well but reacts strongly to unclear or conflicting context: audit the prompt for contradictions. It is more sensitive to skills and AGENTS.md files.
- **GPT-6.1 Sol:** near-Astra quality at lower cost. Same guidance.
- **GPT-6.1 Terra:** fast. Strong at visual reasoning, computer use and natural writing. Keep tasks focused.
- **GPT-6 Luna:** most efficient. For focused, high-volume tasks, give explicit format and one task per prompt.
- **GPT-5.6:** trim prompts. Older GPT-5 scaffolding (eagerness tuning, long tool preambles) is no longer needed. Conflicting rules cause instability.
- **o3 / o4-mini (legacy reasoning):** follow the reasoning-model rules above strictly. Keep prompts short and direct, with delimiters.
- **GPT-4.1 / GPT-4o (legacy, non-reasoning):** need precise, explicit instructions that spell out the logic and the output, like a junior co-worker. Here, asking it to plan step by step and putting the instructions at both the start and the end of long context do help.

## Anti-patterns to remove
- Prescriptive step-by-step choreography for reasoning models.
- Chain-of-thought incantations.
- Approval requests before any concrete result exists.
- Stopping at a plan when action was requested.
- Contradictory rules.
- Heavy Markdown or tables when prose is wanted.
- Sampling parameter advice (temperature, top_p). Current reasoning models reject or ignore it.
