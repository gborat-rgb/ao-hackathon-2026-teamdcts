# AI Development Instructions

## Project Context
This repository is prepared for AO Hackathon 2026.
The final problem statement will be provided at the start of the event.

## Working Principles
- Understand the problem and data before generating implementation code.
- Prefer small, testable modules over large generated code blocks.
- Do not invent assumptions about the dataset; verify them first.
- Explain important architectural and analytical decisions.
- Preserve reproducibility of analysis and results.
- Never commit secrets, credentials, or production/customer data.

## Development Workflow
1. Inspect the provided dataset and problem statement.
2. Produce hypotheses and alternative solution approaches.
3. Select an approach with explicit reasoning.
4. Implement incrementally.
5. Test each component.
6. Record important prompts and decisions under `prompts/` and `docs/`.
7. Keep README.md and AI_JURI.md aligned with the implemented solution.

## Repository Structure
- `src/` implementation
- `docs/` architecture, plan and decisions
- `prompts/` important AI prompts
- `demo/` screenshots and demo assets
- `AI_JURI.md` jury-facing evidence
- `submission.json` machine-readable submission metadata

## Security
- Never commit `.env`.
- Never expose API keys or credentials.
- Use `.env.example` only for variable names and placeholders.
- Use only synthetic hackathon data.

## Quality
- Prefer readable and maintainable code.
- Add tests for critical logic where practical.
- Avoid unnecessary dependencies.
- Clearly document known limitations.
