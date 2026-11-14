---
family: deepseek
reviewed: 2026-11-14
sources:
  - https://api-docs.deepseek.com/
  - https://api-docs.deepseek.com/guides/thinking_mode
  - DeepSeek-R1 model card (usage recommendations), huggingface.co/deepseek-ai/DeepSeek-R1
---

# Prompting DeepSeek

## Core rules (V4 Pro, V4.1 Flash)
- Thinking mode is on by default (effort `high`). The model reasons internally, and its chain of thought comes back separately (`reasoning_content`). Do not ask it to "think step by step" or to show its reasoning in the answer.
- Write the goal, the constraints and the exact output format plainly. Put stable rules in the system message and inputs in the user message.
- Sampling parameters (temperature, presence/frequency penalty) have no effect in thinking mode. Do not include sampling advice in the prompt.
- For agentic or tool use, describe each tool's purpose in the tool definition, not in prose. State when to stop calling tools and what the final answer must contain.
- Delimit documents and data clearly (XML tags or fenced blocks) and put the question after them.

## DeepSeek-R1 and R1-distilled open-weight models (local, legacy)
- Put every instruction in the user prompt and avoid a system prompt. The R1 card recommends this.
- Prefer zero-shot. Few-shot examples degrade R1's performance.
- For math, add: "Please reason step by step, and put your final answer within \boxed{}". This is the official R1 recommendation.
- State the expected output format clearly. R1 sometimes skips its thinking. Inference stacks may force a `<think>\n` start, but the prompt itself should not mention think tags.

## Version notes
- **V4 Pro:** strongest. Give the full spec and success criteria.
- **V4.1 Flash:** fast and cheap (served under the `deepseek-flash` alias). Keep each prompt to one clear task with an explicit format.
- **R1 (legacy, open weights):** follow the R1 rules above strictly.

## Anti-patterns to remove
- Chain-of-thought incantations on V4.
- System prompts and few-shot blocks for R1.
- Sampling-parameter instructions inside the prompt.
