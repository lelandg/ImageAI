import os
from litellm import completion, responses

# Set API keys / endpoints if using OpenAI or Azure
os.environ["OPENAI_API_KEY"] = "YOUR_OPENAI_API_KEY"

def call_gpt5_chat(prompt: str,
                   reasoning_effort: str = "low",
                   verbosity: str = "medium",
                   model: str = "openai/gpt-5-chat-latest",
                   max_output_tokens: int = 512,
                   temperature: float = 1.0):
    resp = completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        max_output_tokens=max_output_tokens,
        temperature=temperature,
        stream=False,
    )
    return resp

def call_gpt5_responses(prompt: str,
                        reasoning_effort: str = "low",
                        verbosity: str = "medium",
                        model: str = "openai/gpt-5",
                        max_output_tokens: int = 512):
    resp = responses(
        model=model,
        input=prompt,
        reasoning_effort=reasoning_effort,
        verbosity=verbosity,
        max_output_tokens=max_output_tokens,
        stream=False,
    )
    return resp

if __name__ == "__main__":
    p = "Explain the significance of quantum entanglement in layman terms."
    out_chat = call_gpt5_chat(p, reasoning_effort="high", verbosity="high", temperature=0.8)
    print("Chat response:", out_chat)

    out_resp = call_gpt5_responses(p, reasoning_effort="medium", verbosity="low")
    print("Responses API output:", out_resp)
