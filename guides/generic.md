---
family: generic
reviewed: 2026-11-14
sources:
  - Common ground of the Anthropic, OpenAI, Google and Meta official prompting guides
---

# Prompting any model (vendor-neutral)

## Core rules
- Lead with the goal and what a good result looks like, then context, then output format, then constraints.
- Give the context the model cannot guess: audience, purpose, inputs, and what has been tried.
- Delimit inputs (documents, code, data) with XML tags or fenced blocks. Put long material first and the task last.
- Specify the output format exactly, and the length qualitatively.
- Give the reason behind each constraint, and describe what to do rather than listing prohibitions.
- Remove contradictions, duplicates, generic virtues ("be accurate") and ALL-CAPS pressure.

## By model type
- **Reasoning models:** goals and success criteria, no "think step by step", zero-shot first.
- **Chat models without reasoning:** explicit instructions. A short "reason through the steps, then answer" helps on multi-step tasks. Two or three examples fix the format.
- **Small local models (≤14B):** short prompts, one task, an explicit format, one example, and the format reminder at the end. Avoid long multi-part instructions.
