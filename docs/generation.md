# Answer Generation

This document defines the first end-to-end answer generation layer for the project.

## Goal

Build a QA layer that:

- consumes the packaged retrieval evidence
- answers only from manufacturer documentation
- stays scoped to the requested vehicle
- returns citations with page-aware evidence
- abstains when the evidence is insufficient
- is easy to evaluate separately from retrieval

## Recommendation

Start with `grounded evidence-first answer generation`.

That means:

- retrieval stays the source of truth for evidence selection
- the generation layer consumes `AnswerContext`
- the model answers only from the provided context
- the output is structured, not free-form only
- citations are required, not optional

## Why This Layer Matters

Retrieval alone is not yet the final user experience.

We still need a layer that can:

- turn evidence into a direct answer
- decide whether the evidence is sufficient
- keep the answer concise and useful
- surface citations in a stable format

This layer should not hide weak retrieval.

It should make it obvious when:

- the answer is well supported
- the answer is only partially supported
- the system should abstain

## Input To Generation

The generation layer should consume the packaged answer context from `src/generation/`.

At a minimum, the input should include:

- request metadata:
  - `question`
  - `make`
  - `model`
  - `year`
- retrieval metadata:
  - retrieval mode
  - selected result stage
  - doc IDs
  - latency
- ranked evidence chunks
- combined `context_text`

This keeps the contract between retrieval and generation explicit.

## Recommended v1 Generation Flow

### 1. Accept Packaged Evidence

The answering layer should start from `AnswerContext`, not raw retrieval bundles.

Why:

- retrieval packaging already normalizes evidence
- citations are already preserved
- the QA layer should not have to reconstruct provenance

### 2. Build A Strict System Prompt

The system prompt should enforce:

- answer only from the provided evidence
- do not use outside automotive knowledge
- do not merge information across unsupported chunks
- stay specific to the requested make, model, and year
- abstain if the evidence does not support a confident answer

### 3. Generate A Structured Output

Recommendation: return JSON or a similarly structured object first, then optionally render it for users.

Suggested fields:

- `answer`
- `answerability`
- `confidence`
- `citations`
- `used_chunk_ids`
- `notes`

The structured layer is important for:

- evaluation
- debugging
- UI rendering
- future automation

### 4. Post-Process Citations

The final answer payload should map citation references back to:

- `chunk_id`
- `doc_id`
- `section_title`
- `page_start`
- `page_end`

This makes citation rendering and auditing much easier.

### 5. Render A User-Facing Answer

After the structured response is validated, we can render:

- a concise natural-language answer
- page-aware citations
- optional “not enough evidence” wording when needed

## Suggested v1 Answer Output

Recommended v1 answer object:

```json
{
  "question": "How do I check the engine oil?",
  "vehicle": {
    "make": "toyota",
    "model": "camry",
    "year": 2023
  },
  "answerability": "answerable",
  "answer": "Park on level ground, wait for the engine to cool, remove the dipstick, wipe it clean, reinsert it fully, and check that the oil level is between the low and full marks.",
  "confidence": "medium",
  "citations": [
    {
      "chunk_id": "2023-toyota-camry::p0237::c0000",
      "doc_id": "2023-toyota-camry",
      "section_title": "Engine oil",
      "page_start": 412,
      "page_end": 413
    }
  ],
  "used_chunk_ids": [
    "2023-toyota-camry::p0237::c0000"
  ],
  "notes": ""
}
```

This schema is intentionally simple.

We can extend it later with:

- partial-answer handling
- unsupported-question reasons
- answer spans
- citation snippets

## Abstention Behavior

Abstention is required for this domain.

Recommended v1 behavior:

- if no evidence is clearly relevant, abstain
- if evidence is contradictory or too weak, abstain
- if the answer would require external knowledge, abstain

Suggested answerability labels:

- `answerable`
- `insufficient_evidence`
- `not_in_manual`

Do not let the answer model guess just because it has general automotive knowledge.

## Model Selection

Model choice should follow the needs of grounded QA, not chatbot demos.

What matters most here:

- strong instruction-following
- reliable citation discipline
- good summarization over multiple evidence chunks
- low hallucination pressure under constrained context
- acceptable latency and cost for repeated evaluation runs

### Recommended Starting Point

Recommendation for the first baseline:

- use a fast, capable general text model first
- keep the prompt and structured output strict
- compare one stronger model against one cheaper model

This project does not need the most expensive model by default on day one.

Because retrieval is already doing the heavy lifting, the answer model mainly needs to:

- synthesize grounded evidence
- stay inside scope
- abstain when unsupported

### Candidate Options As Of August 23, 2026

#### Option A: OpenAI Default Path

Best fit if we want to stay aligned with the current OpenAI-based embedding stack.

- `gpt-5-mini`
  - recommended first default for v1
  - good choice when we want strong quality with lower latency and cost
- `gpt-5.1`
  - quality-focused comparison option
  - useful when we want to test whether a stronger model materially improves grounding or citation quality
- `gpt-4.1`
  - useful non-reasoning baseline
  - good comparison if we want to test whether simpler generation behaves more predictably on tightly grounded QA
- `gpt-4o`
  - practical general-purpose comparison option
  - useful if we want a fast, established model for grounded answer generation without immediately defaulting to the newest frontier option

Why this path is attractive:

- it matches the current API direction in the repo
- it is operationally simple
- it makes early experimentation easier

### Recommended v1 Model Experiments

Keep the first experiments small and focused.

Recommended sequence:

1. `gpt-5-mini` as the first default
2. `gpt-5.1` as the stronger comparison
3. one practical alternate OpenAI baseline:
   - `gpt-4o` or
   - `gpt-4.1`

This gives us:

- one practical default
- one higher-quality check
- one simpler or more established OpenAI comparison

That is enough for v1 without turning Phase 5 into a provider benchmark project too early.

## Prompting Recommendations

Recommended prompt style:

- provide the vehicle identity explicitly
- provide the question explicitly
- provide only the packaged evidence
- instruct the model to cite only from the provided evidence
- require abstention when support is weak
- ask for structured output

Avoid:

- chain-of-thought style prompts in the output
- vague “answer as best you can” wording
- asking the model to infer unsupported repair advice

## What We Should Log

For each answer-generation run, log:

- request metadata
- answer context metadata
- model name
- prompt version
- structured answer output
- cited chunk IDs
- answerability decision
- latency

This will matter later for answer evaluation and regression testing.

## What We Are Not Doing In v1

Not in the first answer-generation implementation:

- agentic tool loops
- automatic query rewriting during answering
- answer generation from images directly
- external web knowledge
- autonomous verification passes
- complex debate or self-critique pipelines

These may become useful later, but they are not needed for the first grounded QA layer.

## Chosen Path

The recommended Phase 5 path is:

1. Consume `AnswerContext`.
2. Define a strict structured answer schema.
3. Start with a fast, capable default model.
4. Enforce abstention and citation requirements.
5. Evaluate answer quality separately from retrieval quality.
6. Expand model comparisons only after the first QA layer works end to end.

## Current Implementation Status

The repo now includes an initial answer-generation layer:

- `src/generation/context_builder.py` packages retrieval evidence
- `src/generation/answering.py` calls OpenAI with grounded prompts
- `src/generation/cli.py` runs retrieval plus answer generation end to end

This is the first implementation slice, not the final production shape.

Current behavior:

- uses the packaged `AnswerContext`
- generates a structured answer object
- resolves citations from returned chunk IDs
- abstains automatically when no evidence is available

Still to improve later:

- stricter schema validation
- richer abstention heuristics
- more robust prompt tuning
- answer-quality evaluation

## References

These model options were checked against official OpenAI documentation on August 23, 2026:

- OpenAI models: <https://platform.openai.com/docs/models>
