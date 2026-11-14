---
family: qwen
reviewed: 2026-11-14
sources:
  - https://huggingface.co/Qwen/Qwen3.8-27B
  - https://qwen.readthedocs.io/en/latest/
  - https://www.alibabacloud.com/help/en/model-studio/models
---

# Prompting Qwen (Alibaba)

## Core rules
- Qwen3.x and Qwen4 are hybrid models. Thinking is on by default and can be disabled per request (`enable_thinking: false`). With thinking on, do not ask for step-by-step reasoning in the prose. With thinking off, a short "work through the steps, then give the answer" can help on multi-step tasks.
- Give a clear system message: role, rules and output format. Put the task and inputs in the user message.
- Standardize the output format explicitly, because Qwen's own evaluation prompts do this:
  - Math: "Please reason step by step, and put your final answer within \boxed{}."
  - Multiple choice: "Show your choice in the answer field with only the choice letter, e.g. \"answer\": \"C\"."
- Delimit long documents (native 262K context, up to 1M with YaRN) with tags or headings, and ask the question after the context.
- For agents and tools, describe the tools in their schemas. With preserved thinking, multi-turn agent consistency is good, so state the overall goal once at the start.
- Lower reasoning effort does not always save time on multi-turn agentic tasks: it can cause shallow analysis and retries. Do not ask for "quick, shallow" answers on hard tasks.

## Version notes
- **Qwen4 Max (preview):** complex reasoning and coding. Give the full goal and success criteria.
- **Qwen3.8 (open weights, 2.4T MoE / 27B):** strong generalist. If repetition appears, the fix is in the inference settings (presence_penalty 0–2), not in the prompt.
- **Qwen3.7 Plus:** balanced. Use explicit format and moderate detail.
- **Qwen3.8 Flash:** fast and cheap. One task per prompt, an exact output format, and an example if the format is unusual.
- **Qwen3 / 3.6 local:** smaller sizes need explicit instructions, short prompts and examples. Use `/no_think`-style switches only if the runtime supports them.

## Anti-patterns to remove
- Asking for chain-of-thought text with thinking on.
- Unspecified answer format for math or multiple-choice.
- Huge undelimited context.
