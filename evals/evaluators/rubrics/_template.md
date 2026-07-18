<!--
  Rubric template — copy this file to evaluators/rubrics/<imp_id>.md and edit.

  How to use:
    1. Rename to match your IMP id (e.g. imp_0014.md). The file stem becomes
       the rubric_id surfaced in eval reports.
    2. Edit the title after `# Rubric:` to a short human-readable name.
    3. Edit each `## Criterion:` block:
         - Set the criterion name (one word, lowercase, snake_case preferred).
         - Set the weight in parentheses. ALL WEIGHTS MUST SUM TO 1.0.
         - Replace the description line.
         - Rewrite all five score definitions (1-5) for your domain.
         - Optionally add anchor examples under `### Examples`.
    4. Add or remove `## Criterion:` blocks as needed; keep the weight sum at 1.0.
    5. Author at least 5 calibration examples in
       evaluators/rubrics/<imp_id>.calibration.jsonl and run the calibration
       gate before trusting this rubric for production scoring.

  Parsing rules enforced by load_rubric():
    - Title line:      `# Rubric: <title>`
    - Criterion line:  `## Criterion: <name> (weight: <float>)`
    - Sections:        `### Score Definitions` and `### Examples`
    - Score bullets:   `- **<1-5>**: <text>`
    - Sum of weights must equal 1.0 (±0.001).
    - Every criterion must define all five score levels.
-->

# Rubric: Template Quality Rubric

## Criterion: correctness (weight: 0.5)
Does the response factually accomplish what the prompt asked for, with no fabrications or logical errors?

### Score Definitions
- **5**: Fully correct. Every claim is verifiable, all requested actions are completed, no fabricated facts or APIs.
- **4**: Mostly correct. Minor inaccuracies that do not change the outcome (e.g. a slightly wrong version number).
- **3**: Partially correct. Core idea is right but the response misses a meaningful requirement or contains one notable error.
- **2**: Largely incorrect. Multiple inaccuracies or misses the central ask, but contains some salvageable content.
- **1**: Wrong. Fabricated facts, hallucinated APIs, or directly contradicts the prompt.

### Examples
- **5**: Returns working code that satisfies every requirement and cites real, current APIs.
- **3**: Returns code that compiles and addresses the main task but ignores one explicit constraint from the prompt.
- **1**: Returns code that references a non-existent function and would fail at import time.

## Criterion: tone (weight: 0.3)
Does the response match the expected voice — concise, professional, free of filler, and respectful of the reader's time?

### Score Definitions
- **5**: Crisp, professional, zero filler. Every sentence carries weight.
- **4**: Clear and professional with minor verbosity (one or two extra sentences).
- **3**: Acceptable but noticeably padded with hedging, apologies, or restated context.
- **2**: Off-tone — overly casual, overly formal, or buried in qualifiers and disclaimers.
- **1**: Tone is wrong for the audience (e.g. condescending, lecturing, or unprofessional).

### Examples
- **5**: "Done. The function now returns a typed Result instead of a dict."
- **3**: "Sure! I'd be happy to help with that. Here is what I did. Let me know if you have any other questions."
- **1**: "As I mentioned previously, you really should have specified that earlier — but fine, here is the answer."

## Criterion: structure (weight: 0.2)
Is the response organized appropriately for its content (correct use of code blocks, headings, lists), and easy to scan?

### Score Definitions
- **5**: Ideal structure — code in fenced blocks, lists for enumerations, headings only when warranted.
- **4**: Good structure with one minor lapse (e.g. an inline snippet that should have been a code block).
- **3**: Workable but inconsistent — mixes formats or buries key information in prose.
- **2**: Poorly structured — wall of text where structure was needed, or over-formatted simple content.
- **1**: No usable structure — code missing fences, lists missing markers, headings used as decoration.
