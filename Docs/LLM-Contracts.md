# LLM Contracts: Reliable AI Integration

This document describes the "LLM Contract" pattern used in ImageAI to ensure reliable, parseable outputs from Large Language Models.

## What is an LLM Contract?

An **LLM Contract** is a strict agreement between the application code and the AI model regarding the format, structure, and constraints of the AI's output. It transforms generative AI from a probabilistic text generator into a reliable structured data processor.

Unlike standard prompting ("Please generate..."), a contract explicitly defines the JSON schema, validation rules, and failure modes, effectively treating the LLM prompt as an API specification.

## Key Components

A robust LLM Contract consists of three parts:

### 1. The System Prompt (The Definition)
This sets the "persona" and strict output rules. It often includes the schema version.

**Example:**
```text
You are "Lyric Timing Aligner — Strict v1.0".
Output must be a single JSON object that conforms exactly to the "Strict Lyric Timing Output Contract v1.0".
Do not include any commentary or code fences.
Do not split or merge lines.
Preserve input order.
```

### 2. The User Prompt (The Input & Context)
This provides the data to process and reiterates critical constraints.

**Example:**
```text
TASK: Align each lyric line to the attached audio.
Return exactly one JSON object per the Strict Lyric Timing Output Contract v1.0.

ASSETS:
- lyrics_text_utf8: ...

CONSTRAINTS:
- One JSON entry per input line, in exact order.
- start_ms/end_ms integers in milliseconds.
- No other fields beyond the contract.
```

### 3. The Code Handler (The Validator)
The application code must strictly validate the output against the contract.

**Implementation Pattern (Python):**
```python
# core/video/llm_sync_v2.py

response_text = llm.generate(...)
data = json.loads(response_text)

# Strict validation
if data.get('version') == '1.0' and data.get('units') == 'ms':
    logger.info("Detected Strict Contract v1.0 format")
    # Process confidently knowing the structure is guaranteed
else:
    # Fallback for legacy/malformed responses
    logger.warning("Contract violation detected, attempting fallback parsing...")
```

## Benefits

1.  **Deterministic Parsing**: By forbidding "chatty" responses (commentary, markdown blocks), JSON parsing becomes trivial.
2.  **Version Control**: Including a version string (e.g., `v1.0`) in the output allows the code to handle model upgrades or schema changes gracefully.
3.  **Error Reduction**: Explicit constraints (e.g., "Round to nearest millisecond", "No nulls") reduce logic errors in the consuming code.
4.  **Model Agnosticism**: A strong contract makes it easier to swap providers (OpenAI vs. Anthropic vs. Gemini) because the expected output is normalized.

## Example: Strict Lyric Timing Contract v1.0

Used in `core/video/llm_sync_v2.py` for synchronizing lyrics with GPT-5.

**Contract Definition:**
*   **Output**: JSON Object
*   **Required Fields**:
    *   `version`: "1.0"
    *   `units`: "ms"
    *   `lyrics`: Array of objects
*   **Lyric Object**:
    *   `text`: String (exact match to input)
    *   `start_ms`: Integer
    *   `end_ms`: Integer

**Success Story:**
Before this contract, GPT-5 would often return fragmented lyrics (splitting lines for better timing) or change the JSON structure randomly. Enforcing "One JSON entry per input line, in exact order" completely solved the synchronization drift issues.

## How to Apply This Pattern

1.  **Define the Schema**: Write down exactly what JSON you need.
2.  **Name the Contract**: Give it a versioned name (e.g., "Scene Description Contract v2").
3.  **Write the Prompt**:
    *   Tell the LLM its identity is the contract handler.
    *   Explicitly forbid markdown formatting (unless needed).
    *   Reiterate constraints in both System and User prompts.
4.  **Validate in Code**: Check for the contract version tag before processing.

## Best Practices

*   **Temperature**: Use low temperature (`0.0` - `0.1`) for logic/data tasks to reduce hallucination.
*   **JSON Mode**: Enable `response_format={"type": "json_object"}` if the provider supports it (OpenAI, Gemini).
*   **Logging**: Always log the raw LLM response *before* parsing to debug contract violations.
*   **Fallbacks**: Always have a "loose" parsing fallback for models that might ignore the contract (e.g., smaller local models).
