---
family: kimi
reviewed: 2026-11-14
sources:
  - https://platform.kimi.ai/docs/introduction
  - https://platform.kimi.ai/docs/models.md
---

# Prompting Kimi (Moonshot AI)

Moonshot's official docs say little about prompting. Their one stated rule is: "clear instructions plus representative examples are the most effective way to get stable outputs". The rest of this guide combines that rule with OpenAI-compatible conventions, because Kimi's API follows the OpenAI chat format.

## Core rules
- Put stable rules in the system message and the task and inputs in the user message.
- Give clear, explicit instructions with a defined output format. Add one to three representative examples when the format or style matters. This is the most reliable lever according to Moonshot.
- Kimi does not access the internet, files or databases unless tools are provided. If the task needs current facts, say so and suggest enabling the official web-search tool, or provide the data inline.
- K3 and K3.1 have a 1M-token context. Put large documents first inside clear delimiters (XML tags or `---` fenced sections), then the question. Ask it to cite or quote the relevant passages for long-document Q&A.
- For long-horizon coding and knowledge work, state the end goal, the constraints, the deliverable and the definition of done up front.

## Reasoning
- K3 and K3.1 Pro reason internally. Do not add "think step by step". Ask for a brief justification only if the reader needs one.

## Version notes
- **Kimi K3.1 Pro:** flagship (3T-class, native vision, 1M context). Strong at long-horizon coding, 3D creation and financial research or modeling. Give the full spec at once, and attach images directly instead of describing them.
- **Kimi K3:** previous flagship with open weights. Same guidance.
- **K2.6 / K2.7 Code (legacy):** being deprecated. Use more explicit step lists and examples, and keep tasks narrower.

## Anti-patterns to remove
- Vague instructions without an output format.
- Assuming web access.
- Huge unstructured context with the question buried in the middle.
