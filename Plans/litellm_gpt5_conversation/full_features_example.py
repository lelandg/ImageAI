import os
from litellm import completion, responses

# 1. Setup
os.environ["OPENAI_API_KEY"] = "YOUR_OPENAI_KEY"

# 2. Chat completion with reasoning + verbosity
def run_chat(prompt: str):
    resp = completion(
        model="openai/gpt-5-chat-latest",
        messages=[{"role": "user", "content": prompt}],
        reasoning_effort="high",
        verbosity="high",
        temperature=0.7,
        max_output_tokens=512,
    )
    return resp

# 3. Responses API
def run_responses(prompt: str):
    resp = responses(
        model="openai/gpt-5",
        input=prompt,
        reasoning_effort="medium",
        verbosity="medium",
        max_output_tokens=256,
    )
    return resp

# 4. Streaming
def run_stream(prompt: str):
    stream = completion(
        model="openai/gpt-5-chat-latest",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )
    for chunk in stream:
        print(chunk.choices[0].delta.content or "", end="", flush=True)
    print()

# 5. Structured JSON output
def run_structured(prompt: str):
    resp = completion(
        model="openai/gpt-5-chat-latest",
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        max_output_tokens=300,
    )
    return resp

# 6. Tool calling
def run_tool_call(prompt: str):
    resp = completion(
        model="openai/gpt-5-chat-latest",
        messages=[{"role": "user", "content": prompt}],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "get_weather",
                    "description": "Get current weather",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "location": {"type": "string"},
                            "unit": {"type": "string", "enum": ["C", "F"]},
                        },
                        "required": ["location"],
                    },
                },
            }
        ],
        tool_choice="auto",
    )
    return resp

# 7. JSON schema validation
def run_json_schema(prompt: str):
    resp = completion(
        model="openai/gpt-5-chat-latest",
        messages=[{"role": "user", "content": prompt}],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "user_info",
                "schema": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "age": {"type": "integer"},
                    },
                    "required": ["name", "age"],
                    "additionalProperties": False,
                },
            },
        },
    )
    return resp

if __name__ == "__main__":
    q = "Summarize the benefits of quantum computing for programmers."

    print("\n=== Chat ===")
    print(run_chat(q))

    print("\n=== Responses API ===")
    print(run_responses(q))

    print("\n=== Streaming ===")
    run_stream(q)

    print("\n=== Structured JSON ===")
    print(run_structured("Give me a JSON object with 'language' and 'creator' for Python."))

    print("\n=== Tool calling ===")
    print(run_tool_call("What’s the weather in Chicago in C?"))

    print("\n=== JSON Schema ===")
    print(run_json_schema("My name is Alice and I am 34 years old."))
