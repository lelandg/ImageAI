"""LLM prompt generation dialog for ImageAI."""

import json
import logging
from typing import List, Dict, Optional
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QTextEdit,
    QPushButton, QListWidget, QListWidgetItem, QSpinBox,
    QComboBox, QGroupBox, QSplitter, QMessageBox,
    QTabWidget, QWidget, QDialogButtonBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt, Signal, QThread, QObject, QSettings
from PySide6.QtGui import QKeySequence, QShortcut

logger = logging.getLogger(__name__)
console = logging.getLogger("console")


class LLMWorker(QObject):
    """Worker thread for LLM operations."""
    finished = Signal(list)  # List of generated prompts
    error = Signal(str)
    progress = Signal(str)
    log_message = Signal(str, str)  # Message, level (INFO/WARNING/ERROR)

    def __init__(self, operation: str, input_text: str, num_variations: int,
                 llm_provider: str, llm_model: str, api_key: str,
                 temperature: float = 0.8, max_tokens: int = 1000,
                 reasoning_effort: str = "medium", verbosity: str = "medium"):
        super().__init__()
        self.operation = operation
        self.input_text = input_text
        self.num_variations = num_variations
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.reasoning_effort = reasoning_effort
        self.verbosity = verbosity

    def run(self):
        """Run the LLM operation."""
        try:
            self.progress.emit(f"Generating {self.num_variations} prompt variations...")
            self.log_message.emit(f"Generating {self.num_variations} prompt variations...", "INFO")

            # Log LLM request details to both log file and console
            logger.info(f"LLM Request - Provider: {self.llm_provider}, Model: {self.llm_model}")
            console.info(f"LLM Request - Provider: {self.llm_provider}, Model: {self.llm_model}")
            self.log_message.emit(f"Provider: {self.llm_provider}, Model: {self.llm_model}", "INFO")

            logger.info(f"LLM Request - API Key: {'***' + self.api_key[-4:] if self.api_key and len(self.api_key) > 4 else 'None'}")
            console.info(f"LLM Request - API Key: {'***' + self.api_key[-4:] if self.api_key and len(self.api_key) > 4 else 'None'}")

            logger.info(f"LLM Request - Number of variations: {self.num_variations}")
            console.info(f"LLM Request - Number of variations: {self.num_variations}")

            logger.info(f"LLM Request - Input text: {self.input_text}")
            console.info(f"LLM Request - Input text: {self.input_text}")

            # Try to import and use litellm for better compatibility
            try:
                import litellm
                import logging as py_logging

                # Set up custom handler to capture litellm logs
                class LiteLLMConsoleHandler(py_logging.Handler):
                    def emit(self, record):
                        if record.name == "LiteLLM":
                            # Only show the message, not the file info
                            msg = record.getMessage()
                            console.info(f"LiteLLM: {msg}")

                # Add console handler for litellm
                litellm_logger = py_logging.getLogger("LiteLLM")
                console_handler = LiteLLMConsoleHandler()
                console_handler.setFormatter(py_logging.Formatter('%(message)s'))
                litellm_logger.addHandler(console_handler)

                litellm.drop_params = True  # Drop unsupported params
                litellm.set_verbose = True  # Enable verbose for debugging
                use_litellm = True

                logger.info("LiteLLM imported successfully")
                console.info("LiteLLM imported successfully")
                self.log_message.emit("LiteLLM imported successfully", "INFO")
            except ImportError:
                logger.warning("LiteLLM not installed, falling back to direct SDK")
                console.warning("LiteLLM not installed, falling back to direct SDK")
                use_litellm = False

            # Create the prompt for the LLM
            system_prompt = """You are a creative prompt engineer for AI image generation.
                Generate creative, detailed prompts based on the user's input.
                Return ONLY a JSON array of prompt strings, no other text or formatting.
                Each prompt should be unique and explore different creative angles."""

            user_prompt = f"""Based on this idea: "{self.input_text}"
                Generate exactly {self.num_variations} creative image generation prompts.
                Return as a JSON array of strings like: ["prompt1", "prompt2", "prompt3"]"""

            # Import LLM provider
            if self.llm_provider.lower() == "openai":
                model_name = self.llm_model or "gpt-4"

                if use_litellm:
                    # Use litellm for better compatibility
                    # Adjust parameters based on model
                    if "gpt-5" in model_name.lower():
                        # GPT-5 specific parameters
                        temp = 1.0  # GPT-5 only supports temperature=1
                        # Note: reasoning_effort and verbosity are not yet supported by the API
                        logger.info(f"  Reasoning effort: {self.reasoning_effort} (UI only - not sent to API)")
                        console.info(f"  Reasoning effort: {self.reasoning_effort} (UI only - not sent to API)")
                        logger.info(f"  Verbosity: {self.verbosity} (UI only - not sent to API)")
                        console.info(f"  Verbosity: {self.verbosity} (UI only - not sent to API)")
                    else:
                        temp = self.temperature

                    request_data = {
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": temp,
                        "max_tokens": self.max_tokens  # litellm will handle conversion
                    }

                    logger.info(f"LLM Request - Sending via LiteLLM to OpenAI:")
                    console.info(f"LLM Request - Sending via LiteLLM to OpenAI:")

                    logger.info(f"  Model: {model_name}")
                    console.info(f"  Model: {model_name}")

                    logger.info(f"  Temperature: {request_data['temperature']}")
                    console.info(f"  Temperature: {request_data['temperature']}")

                    logger.info(f"  Max tokens: {request_data['max_tokens']}")
                    console.info(f"  Max tokens: {request_data['max_tokens']}")

                    # Clean up multi-line strings for logging
                    clean_system = system_prompt.replace('\n', ' ').strip()
                    clean_user = user_prompt.replace('\n', ' ').strip()

                    logger.info(f"  System prompt: {clean_system}")
                    console.info(f"  System prompt: {clean_system}")

                    logger.info(f"  User prompt: {clean_user}")
                    console.info(f"  User prompt: {clean_user}")

                    response = litellm.completion(**request_data)
                else:
                    # Fallback to direct OpenAI SDK
                    from openai import OpenAI
                    client = OpenAI(api_key=self.api_key)

                    # Use max_completion_tokens for newer models (gpt-4, gpt-5, etc), max_tokens for gpt-3.5
                    token_param = "max_completion_tokens" if "gpt-3.5" not in model_name.lower() else "max_tokens"

                    # For gpt-5, use temperature=1 (the only supported value)
                    temperature = 1.0 if "gpt-5" in model_name.lower() else self.temperature

                    request_data = {
                        "model": model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": temperature,
                        token_param: self.max_tokens
                    }

                    logger.info(f"LLM Request - Sending to OpenAI API:")
                    console.info(f"LLM Request - Sending to OpenAI API:")

                    logger.info(f"  Model: {request_data['model']}")
                    console.info(f"  Model: {request_data['model']}")

                    logger.info(f"  Temperature: {request_data['temperature']}")
                    console.info(f"  Temperature: {request_data['temperature']}")

                    logger.info(f"  Token limit ({token_param}): {request_data[token_param]}")
                    console.info(f"  Token limit ({token_param}): {request_data[token_param]}")

                    # Clean up multi-line strings for logging
                    clean_system = system_prompt.replace('\n', ' ').strip()
                    clean_user = user_prompt.replace('\n', ' ').strip()

                    logger.info(f"  System prompt: {clean_system}")
                    console.info(f"  System prompt: {clean_system}")

                    logger.info(f"  User prompt: {clean_user}")
                    console.info(f"  User prompt: {clean_user}")

                    response = client.chat.completions.create(**request_data)

                # Log raw response to both log file and console
                logger.info(f"LLM Response - Status: Success")
                console.info(f"LLM Response - Status: Success")

                # Handle both litellm and direct SDK response formats
                if hasattr(response, 'model'):
                    logger.info(f"LLM Response - Model used: {response.model}")
                    console.info(f"LLM Response - Model used: {response.model}")

                if hasattr(response, 'usage') and response.usage:
                    logger.info(f"LLM Response - Completion tokens: {response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 'N/A'}")
                    console.info(f"LLM Response - Completion tokens: {response.usage.completion_tokens if hasattr(response.usage, 'completion_tokens') else 'N/A'}")

                    logger.info(f"LLM Response - Prompt tokens: {response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 'N/A'}")
                    console.info(f"LLM Response - Prompt tokens: {response.usage.prompt_tokens if hasattr(response.usage, 'prompt_tokens') else 'N/A'}")

                    logger.info(f"LLM Response - Total tokens: {response.usage.total_tokens if hasattr(response.usage, 'total_tokens') else 'N/A'}")
                    console.info(f"LLM Response - Total tokens: {response.usage.total_tokens if hasattr(response.usage, 'total_tokens') else 'N/A'}")

                # Parse the response (same structure for both litellm and direct SDK)
                if hasattr(response.choices[0], 'message'):
                    content = response.choices[0].message.content
                else:
                    content = response.choices[0].text

                # Check for empty response
                if not content or not content.strip():
                    logger.warning("Empty response from LLM, using fallback prompts")
                    console.warning("Empty response from LLM, using fallback prompts")
                    # Generate fallback prompts based on the input
                    base_prompt = self.input_text[:100]
                    prompts = [
                        f"A detailed, photorealistic image of {self.input_text}",
                        f"An artistic interpretation of {self.input_text}, cinematic lighting, highly detailed",
                        f"A futuristic visualization of {self.input_text}, trending on artstation, 8k resolution"
                    ][:self.num_variations]
                    logger.info(f"LLM Response - Using {len(prompts)} fallback prompts")
                    console.info(f"LLM Response - Using {len(prompts)} fallback prompts")
                    console.info("=" * 60)
                    console.info("Fallback Prompts (Empty Response):")
                    for i, p in enumerate(prompts, 1):
                        console.info(f"  {i}. {p}")
                    console.info("=" * 60)
                    self.finished.emit(prompts)
                    return

                content = content.strip()
                logger.info(f"LLM Response - Raw content: {content}")
                console.info(f"LLM Response - Raw content: {content}")

                # Remove markdown formatting if present
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                    logger.info(f"LLM Response - Cleaned content: {content}")

                try:
                    prompts = json.loads(content)
                    if not isinstance(prompts, list):
                        raise ValueError("Response is not a JSON array")
                    if len(prompts) == 0:
                        raise ValueError("Empty prompts array")

                    logger.info(f"LLM Response - Successfully parsed {len(prompts)} prompts")
                    console.info(f"LLM Response - Successfully parsed {len(prompts)} prompts")
                    console.info("=" * 60)
                    console.info("Generated Prompts:")
                    for i, p in enumerate(prompts, 1):
                        logger.info(f"LLM Response - Prompt {i}: {p}")
                        console.info(f"  {i}. {p}")
                    console.info("=" * 60)
                    self.finished.emit(prompts)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse LLM response as JSON: {e}, using fallback")
                    console.warning(f"Failed to parse LLM response as JSON: {e}, using fallback")
                    # Try to extract prompts from plain text if JSON parsing fails
                    lines = content.split('\n')
                    prompts = []
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#') and len(line) > 20:
                            # Clean up common prefixes like "1.", "- ", etc.
                            import re
                            line = re.sub(r'^[\d\.\-\*\s]+', '', line).strip()
                            if line:
                                prompts.append(line)

                    if prompts:
                        prompts = prompts[:self.num_variations]
                        logger.info(f"LLM Response - Extracted {len(prompts)} prompts from text")
                        console.info(f"LLM Response - Extracted {len(prompts)} prompts from text")
                        console.info("=" * 60)
                        console.info("Extracted Prompts:")
                        for i, p in enumerate(prompts, 1):
                            console.info(f"  {i}. {p}")
                        console.info("=" * 60)
                        self.finished.emit(prompts)
                    else:
                        # Final fallback
                        prompts = [
                            f"A detailed, photorealistic image of {self.input_text}",
                            f"An artistic interpretation of {self.input_text}, cinematic lighting",
                            f"A creative visualization of {self.input_text}, highly detailed"
                        ][:self.num_variations]
                        logger.info(f"LLM Response - Using {len(prompts)} fallback prompts")
                        console.info(f"LLM Response - Using {len(prompts)} fallback prompts")
                        console.info("=" * 60)
                        console.info("Fallback Prompts:")
                        for i, p in enumerate(prompts, 1):
                            console.info(f"  {i}. {p}")
                        console.info("=" * 60)
                        self.finished.emit(prompts)

            elif self.llm_provider.lower() == "gemini" or self.llm_provider.lower() == "google":
                model_name = self.llm_model or "gemini-pro"

                if use_litellm:
                    # Use litellm for better compatibility
                    request_data = {
                        "model": f"gemini/{model_name}" if not model_name.startswith("gemini/") else model_name,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens
                    }

                    logger.info(f"LLM Request - Sending via LiteLLM to Gemini:")
                    console.info(f"LLM Request - Sending via LiteLLM to Gemini:")

                    logger.info(f"  Model: {request_data['model']}")
                    console.info(f"  Model: {request_data['model']}")

                    logger.info(f"  Temperature: {request_data['temperature']}")
                    console.info(f"  Temperature: {request_data['temperature']}")

                    logger.info(f"  Max tokens: {request_data['max_tokens']}")
                    console.info(f"  Max tokens: {request_data['max_tokens']}")

                    # Clean up multi-line strings for logging
                    clean_system = system_prompt.replace('\n', ' ').strip()
                    clean_user = user_prompt.replace('\n', ' ').strip()

                    logger.info(f"  System prompt: {clean_system}")
                    console.info(f"  System prompt: {clean_system}")

                    logger.info(f"  User prompt: {clean_user}")
                    console.info(f"  User prompt: {clean_user}")

                    response = litellm.completion(**request_data)

                    # Parse litellm response
                    if hasattr(response.choices[0], 'message'):
                        # Handle None content from Gemini models
                        if response.choices[0].message.content is None:
                            logger.warning("Received None content from LLM response")
                            content = "[]"  # Return empty array as fallback
                        else:
                            content = response.choices[0].message.content.strip()
                    else:
                        if response.choices[0].text is None:
                            logger.warning("Received None text from LLM response")
                            content = "[]"  # Return empty array as fallback
                        else:
                            content = response.choices[0].text.strip()
                else:
                    # Fallback to direct Gemini SDK
                    import google.generativeai as genai
                    genai.configure(api_key=self.api_key)
                    model = genai.GenerativeModel(model_name)

                    prompt = f"""Generate exactly {self.num_variations} creative image generation prompts based on: "{self.input_text}"
                    Return ONLY a JSON array of strings, no other text: ["prompt1", "prompt2", "prompt3"]"""

                    # Log request details to both log file and console
                    logger.info(f"LLM Request - Sending to Gemini API:")
                    console.info(f"LLM Request - Sending to Gemini API:")

                    logger.info(f"  Model: {model_name}")
                    console.info(f"  Model: {model_name}")

                    # Clean up multi-line strings for logging
                    clean_prompt = prompt.replace('\n', ' ').strip()

                    logger.info(f"  Prompt: {clean_prompt}")
                    console.info(f"  Prompt: {clean_prompt}")

                    response = model.generate_content(prompt)
                    content = response.text.strip()

                logger.info(f"LLM Response - Status: Success")
                console.info(f"LLM Response - Status: Success")

                logger.info(f"LLM Response - Raw content: {content}")
                console.info(f"LLM Response - Raw content: {content}")

                # Clean up response
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                    logger.info(f"LLM Response - Cleaned content: {content}")

                try:
                    prompts = json.loads(content)
                    if not isinstance(prompts, list):
                        raise ValueError("Response is not a JSON array")
                    if len(prompts) == 0:
                        raise ValueError("Empty prompts array")

                    logger.info(f"LLM Response - Successfully parsed {len(prompts)} prompts")
                    console.info(f"LLM Response - Successfully parsed {len(prompts)} prompts")
                    console.info("=" * 60)
                    console.info("Generated Prompts:")
                    for i, p in enumerate(prompts, 1):
                        logger.info(f"LLM Response - Prompt {i}: {p}")
                        console.info(f"  {i}. {p}")
                    console.info("=" * 60)
                    self.finished.emit(prompts)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.warning(f"Failed to parse LLM response as JSON: {e}, using fallback")
                    console.warning(f"Failed to parse LLM response as JSON: {e}, using fallback")
                    # Try to extract prompts from plain text if JSON parsing fails
                    lines = content.split('\n')
                    prompts = []
                    for line in lines:
                        line = line.strip()
                        if line and not line.startswith('#') and len(line) > 20:
                            # Clean up common prefixes like "1.", "- ", etc.
                            import re
                            line = re.sub(r'^[\d\.\-\*\s]+', '', line).strip()
                            if line:
                                prompts.append(line)

                    if prompts:
                        prompts = prompts[:self.num_variations]
                        logger.info(f"LLM Response - Extracted {len(prompts)} prompts from text")
                        console.info(f"LLM Response - Extracted {len(prompts)} prompts from text")
                        console.info("=" * 60)
                        console.info("Extracted Prompts:")
                        for i, p in enumerate(prompts, 1):
                            console.info(f"  {i}. {p}")
                        console.info("=" * 60)
                        self.finished.emit(prompts)
                    else:
                        # Final fallback
                        prompts = [
                            f"A detailed, photorealistic image of {self.input_text}",
                            f"An artistic interpretation of {self.input_text}, cinematic lighting",
                            f"A creative visualization of {self.input_text}, highly detailed"
                        ][:self.num_variations]
                        logger.info(f"LLM Response - Using {len(prompts)} fallback prompts")
                        console.info(f"LLM Response - Using {len(prompts)} fallback prompts")
                        console.info("=" * 60)
                        console.info("Fallback Prompts:")
                        for i, p in enumerate(prompts, 1):
                            console.info(f"  {i}. {p}")
                        console.info("=" * 60)
                        self.finished.emit(prompts)

            elif self.llm_provider.lower() in ["claude", "anthropic"]:
                logger.info("Using Claude/Anthropic for prompt generation")
                console.info("Using Claude/Anthropic for prompt generation")

                model_name = self.llm_model or "claude-sonnet-4-5"

                if use_litellm:
                    # Use litellm with Anthropic provider - must prefix with "anthropic/"
                    litellm_model = f"anthropic/{model_name}"
                    request_data = {
                        "model": litellm_model,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt}
                        ],
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens,
                        "api_key": self.api_key  # Pass API key directly to LiteLLM
                    }

                    logger.info(f"LLM Request - Sending via LiteLLM to Claude:")
                    console.info(f"LLM Request - Sending via LiteLLM to Claude:")

                    logger.info(f"  Model: {litellm_model} (original: {model_name})")
                    console.info(f"  Model: {litellm_model} (original: {model_name})")

                    logger.info(f"  Temperature: {request_data['temperature']}")
                    console.info(f"  Temperature: {request_data['temperature']}")

                    logger.info(f"  Max tokens: {request_data['max_tokens']}")
                    console.info(f"  Max tokens: {request_data['max_tokens']}")

                    # Clean up multi-line strings for logging
                    clean_system = system_prompt.replace('\n', ' ').strip()
                    clean_user = user_prompt.replace('\n', ' ').strip()

                    logger.info(f"  System prompt: {clean_system}")
                    console.info(f"  System prompt: {clean_system}")

                    logger.info(f"  User prompt: {clean_user}")
                    console.info(f"  User prompt: {clean_user}")

                    response = litellm.completion(**request_data)
                else:
                    # Fallback to direct Anthropic SDK
                    from anthropic import Anthropic
                    client = Anthropic(api_key=self.api_key)

                    request_data = {
                        "model": model_name,
                        "messages": [
                            {"role": "user", "content": user_prompt}
                        ],
                        "system": system_prompt,
                        "temperature": self.temperature,
                        "max_tokens": self.max_tokens
                    }

                    logger.info(f"LLM Request - Sending to Claude API:")
                    console.info(f"LLM Request - Sending to Claude API:")

                    logger.info(f"  Model: {request_data['model']}")
                    console.info(f"  Model: {request_data['model']}")

                    logger.info(f"  Temperature: {request_data['temperature']}")
                    console.info(f"  Temperature: {request_data['temperature']}")

                    logger.info(f"  Max tokens: {request_data['max_tokens']}")
                    console.info(f"  Max tokens: {request_data['max_tokens']}")

                    # Clean up multi-line strings for logging
                    clean_system = system_prompt.replace('\n', ' ').strip()
                    clean_user = user_prompt.replace('\n', ' ').strip()

                    logger.info(f"  System prompt: {clean_system}")
                    console.info(f"  System prompt: {clean_system}")

                    logger.info(f"  User prompt: {clean_user}")
                    console.info(f"  User prompt: {clean_user}")

                    response = client.messages.create(**request_data)

                # Log raw response to both log file and console
                logger.info(f"LLM Response - Status: Success")
                console.info(f"LLM Response - Status: Success")

                # Handle both litellm and direct SDK response formats
                if hasattr(response, 'model'):
                    logger.info(f"LLM Response - Model used: {response.model}")
                    console.info(f"LLM Response - Model used: {response.model}")

                if hasattr(response, 'usage'):
                    logger.info(f"LLM Response - Tokens used: {response.usage}")
                    console.info(f"LLM Response - Tokens used: {response.usage}")

                # Extract content - handle both formats
                if use_litellm and hasattr(response, 'choices'):
                    content = response.choices[0].message.content
                elif hasattr(response, 'content'):
                    # Direct Anthropic SDK returns content as list of blocks
                    content = response.content[0].text if isinstance(response.content, list) else response.content
                else:
                    content = str(response)

                logger.info(f"LLM Response - Raw content: {content}")
                console.info(f"LLM Response - Raw content: {content}")

                # Handle None content
                if not content:
                    logger.warning("LLM returned empty content")
                    console.warning("LLM returned empty content")
                    self.error.emit("Claude returned empty response")
                    return

                # Parse JSON response
                # Clean any markdown formatting
                content = content.strip()
                if content.startswith('```'):
                    # Remove markdown code blocks
                    lines = content.split('\n')
                    content = '\n'.join(lines[1:-1] if len(lines) > 2 else lines)

                # Try to parse as JSON
                try:
                    prompts = json.loads(content)
                except json.JSONDecodeError:
                    # If direct parsing fails, try to extract JSON array
                    import re
                    json_match = re.search(r'\[.*\]', content, re.DOTALL)
                    if json_match:
                        prompts = json.loads(json_match.group())
                    else:
                        # Fallback: split by newlines and clean
                        lines = [line.strip() for line in content.split('\n') if line.strip()]
                        prompts = [line.strip('"').strip("'").strip('- ').strip() for line in lines]
                        prompts = [p for p in prompts if p][:self.num_variations]

                # Ensure we have a list
                if not isinstance(prompts, list):
                    prompts = [str(prompts)]

                logger.info(f"LLM Response - Parsed {len(prompts)} prompts:")
                console.info(f"LLM Response - Parsed {len(prompts)} prompts:")

                logger.info("=" * 60)
                console.info("=" * 60)

                for i, p in enumerate(prompts, 1):
                    logger.info(f"  {i}. {p}")
                    console.info(f"  {i}. {p}")

                logger.info("=" * 60)
                console.info("=" * 60)

                self.finished.emit(prompts)

            elif self.llm_provider.lower() == "ollama":
                # Add Ollama support
                logger.info("Using Ollama for prompt generation")
                # Ollama implementation would go here
                self.error.emit(f"Ollama support coming soon")

            elif self.llm_provider.lower() == "lm studio":
                # Add LM Studio support
                logger.info("Using LM Studio for prompt generation")
                # LM Studio implementation would go here
                self.error.emit(f"LM Studio support coming soon")

            else:
                self.error.emit(f"Unsupported LLM provider: {self.llm_provider}")

        except json.JSONDecodeError as e:
            logger.error(f"LLM Error - JSON parsing failed: {e}")
            console.error(f"LLM Error - JSON parsing failed: {e}")

            logger.error(f"LLM Error - Content that failed to parse: {content if 'content' in locals() else 'N/A'}")
            console.error(f"LLM Error - Content that failed to parse: {content if 'content' in locals() else 'N/A'}")

            self.error.emit(f"Failed to parse LLM response as JSON: {e}")
        except Exception as e:
            logger.error(f"LLM Error - Request failed: {str(e)}")
            console.error(f"LLM Error - Request failed: {str(e)}")

            logger.error(f"LLM Error - Exception type: {type(e).__name__}")
            console.error(f"LLM Error - Exception type: {type(e).__name__}")

            logger.error(f"LLM Error - Full exception:", exc_info=True)
            console.error(f"LLM Error - Full exception: {str(e)}")

            self.error.emit(f"LLM generation failed: {str(e)}")


class PromptGenerationDialog(QDialog):
    """Dialog for generating prompts using LLM."""

    promptSelected = Signal(str)

    def __init__(self, parent=None, config=None):
        super().__init__(parent)
        self.config = config
        self.generated_prompts = []
        self.prompt_history = self.load_history()
        self.last_session = self.load_last_session()
        self.worker = None
        self.thread = None
        self.settings = QSettings("ImageAI", "PromptGenerationDialog")

        self.setWindowTitle("AI Prompt Generator")
        self.setMinimumWidth(800)
        self.setMinimumHeight(700)

        # Restore window geometry
        self.restore_settings()

        self.init_ui()
        self.load_llm_settings()
        self.restore_last_session()
        self.update_history_list()  # Populate history list on dialog open

    def init_ui(self):
        """Initialize the UI."""
        main_layout = QVBoxLayout(self)

        # Create splitter for main content and status console
        splitter = QSplitter(Qt.Vertical)

        # Main content widget
        main_widget = QWidget()
        layout = QVBoxLayout(main_widget)

        # Tab widget for Generate and History
        self.tab_widget = QTabWidget()

        # Generate tab
        generate_widget = QWidget()
        generate_layout = QVBoxLayout(generate_widget)

        # Input section
        input_group = QGroupBox("Your Idea")
        input_layout = QVBoxLayout(input_group)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText(
            "Enter a basic idea or concept, e.g., 'futuristic city at sunset' or 'magical forest'"
        )
        self.input_text.setMaximumHeight(100)
        input_layout.addWidget(self.input_text)

        generate_layout.addWidget(input_group)

        # Settings section
        settings_group = QGroupBox("Generation Settings")
        settings_layout = QVBoxLayout(settings_group)

        # First row: variations, provider, model
        first_row = QHBoxLayout()
        first_row.addWidget(QLabel("Number of variations:"))
        self.num_variations_spin = QSpinBox()
        self.num_variations_spin.setRange(1, 10)
        self.num_variations_spin.setValue(3)
        first_row.addWidget(self.num_variations_spin)

        first_row.addStretch()

        first_row.addWidget(QLabel("LLM Provider:"))
        self.llm_provider_combo = QComboBox()
        first_row.addWidget(self.llm_provider_combo)

        first_row.addWidget(QLabel("Model:"))
        self.llm_model_combo = QComboBox()
        first_row.addWidget(self.llm_model_combo)

        settings_layout.addLayout(first_row)

        # Standard parameters (temperature, max tokens)
        self.standard_params_widget = QWidget()
        standard_layout = QHBoxLayout(self.standard_params_widget)
        standard_layout.setContentsMargins(0, 0, 0, 0)

        standard_layout.addWidget(QLabel("Temperature:"))
        self.temperature_spin = QDoubleSpinBox()
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setSingleStep(0.1)
        self.temperature_spin.setValue(0.8)
        self.temperature_spin.setToolTip("Controls randomness (0=deterministic, 2=very creative)")
        standard_layout.addWidget(self.temperature_spin)

        standard_layout.addWidget(QLabel("Max Tokens:"))
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(200, 4000)
        self.max_tokens_spin.setSingleStep(100)
        self.max_tokens_spin.setValue(1500)
        self.max_tokens_spin.setToolTip("Maximum length of the response (recommended: ~150 tokens per variation)")
        standard_layout.addWidget(self.max_tokens_spin)

        standard_layout.addStretch()
        settings_layout.addWidget(self.standard_params_widget)

        # GPT-5 specific parameters
        self.gpt5_params_widget = QWidget()
        gpt5_layout = QHBoxLayout(self.gpt5_params_widget)
        gpt5_layout.setContentsMargins(0, 0, 0, 0)

        gpt5_layout.addWidget(QLabel("Reasoning:"))
        self.reasoning_combo = QComboBox()
        self.reasoning_combo.addItems(["low", "medium", "high"])
        self.reasoning_combo.setCurrentText("medium")
        self.reasoning_combo.setToolTip("GPT-5 reasoning effort level")
        gpt5_layout.addWidget(self.reasoning_combo)

        gpt5_layout.addWidget(QLabel("Verbosity:"))
        self.verbosity_combo = QComboBox()
        self.verbosity_combo.addItems(["low", "medium", "high"])
        self.verbosity_combo.setCurrentText("medium")
        self.verbosity_combo.setToolTip("GPT-5 response detail level")
        gpt5_layout.addWidget(self.verbosity_combo)

        gpt5_layout.addStretch()
        settings_layout.addWidget(self.gpt5_params_widget)
        self.gpt5_params_widget.setVisible(False)  # Hidden by default

        generate_layout.addWidget(settings_group)

        # Generate button
        self.generate_btn = QPushButton("Generate Prompts")
        self.generate_btn.setToolTip("Generate creative prompts with AI (Ctrl+Enter)")
        self.generate_btn.setDefault(True)
        self.generate_btn.setStyleSheet("""
            QPushButton {
                font-weight: bold;
            }
        """)
        self.generate_btn.clicked.connect(self.generate_prompts)
        generate_layout.addWidget(self.generate_btn)

        # Add shortcut hint label
        shortcut_label = QLabel("<small style='color: gray;'>Shortcuts: Ctrl+Enter to generate, Esc to close</small>")
        shortcut_label.setAlignment(Qt.AlignCenter)
        generate_layout.addWidget(shortcut_label)

        # Set up keyboard shortcuts
        # Ctrl+Enter to generate prompts
        generate_shortcut = QShortcut(QKeySequence("Ctrl+Return"), self)
        generate_shortcut.activated.connect(self.generate_prompts)

        # Escape to close
        escape_shortcut = QShortcut(QKeySequence("Escape"), self)
        escape_shortcut.activated.connect(self.reject)

        # Results section
        results_group = QGroupBox("Generated Prompts")
        results_layout = QVBoxLayout(results_group)

        self.results_list = QListWidget()
        self.results_list.itemDoubleClicked.connect(self.on_item_double_clicked)
        results_layout.addWidget(self.results_list)

        # Result preview
        self.preview_text = QTextEdit()
        self.preview_text.setReadOnly(True)
        self.preview_text.setMaximumHeight(100)
        results_layout.addWidget(self.preview_text)

        generate_layout.addWidget(results_group)

        self.tab_widget.addTab(generate_widget, "Generate")

        # History tab
        history_widget = QWidget()
        history_layout = QVBoxLayout(history_widget)

        self.history_list = QListWidget()
        self.history_list.itemDoubleClicked.connect(self.on_history_item_double_clicked)
        history_layout.addWidget(self.history_list)

        clear_history_btn = QPushButton("Clear History")
        clear_history_btn.clicked.connect(self.clear_history)
        history_layout.addWidget(clear_history_btn)

        self.tab_widget.addTab(history_widget, "History")

        layout.addWidget(self.tab_widget)

        # Add main widget to splitter
        splitter.addWidget(main_widget)

        # Status console at the bottom
        from .llm_utils import DialogStatusConsole
        from .history_widget import DialogHistoryWidget
        self.status_console = DialogStatusConsole("Status", self)
        splitter.addWidget(self.status_console)

        # Set splitter sizes (70% content, 30% console)
        splitter.setSizes([490, 210])
        splitter.setStretchFactor(0, 1)  # Main content can stretch
        splitter.setStretchFactor(1, 0)  # Console maintains minimum size but can expand

        # Add splitter to main layout
        main_layout.addWidget(splitter)

        # Restore splitter state if saved
        splitter_state = self.settings.value("splitter_state")
        if splitter_state:
            splitter.restoreState(splitter_state)

        # Always start on Generate tab (index 0), not History tab
        if hasattr(self, 'tab_widget'):
            self.tab_widget.setCurrentIndex(0)

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel,
            Qt.Horizontal
        )
        buttons.accepted.connect(self.accept_selection)
        buttons.rejected.connect(self.reject)
        main_layout.addWidget(buttons)

        # Connect list selection to preview
        self.results_list.currentItemChanged.connect(self.on_selection_changed)

        # Update LLM models when provider changes
        self.llm_provider_combo.currentTextChanged.connect(self.update_llm_models)
        self.llm_model_combo.currentTextChanged.connect(self.on_model_changed)

    def load_llm_settings(self):
        """Load LLM settings from config."""
        # Import MainWindow to use its LLM functions
        from gui.main_window import MainWindow

        # Populate providers
        self.llm_provider_combo.clear()
        providers = [p for p in MainWindow.get_llm_providers() if p != "None"]
        self.llm_provider_combo.addItems(providers)

        if self.config:
            # Use saved provider, or default to first available
            provider = self.config.get("llm_provider", "")
            if provider and provider != "None":
                index = self.llm_provider_combo.findText(provider)
                if index >= 0:
                    self.llm_provider_combo.setCurrentIndex(index)
                else:
                    # Saved provider not available, use first
                    if self.llm_provider_combo.count() > 0:
                        self.llm_provider_combo.setCurrentIndex(0)
            else:
                # No saved provider, use first available
                if self.llm_provider_combo.count() > 0:
                    self.llm_provider_combo.setCurrentIndex(0)

            # Update models for the provider
            self.update_llm_models()

            # Set model if saved
            model = self.config.get("llm_model", "")
            if model:
                index = self.llm_model_combo.findText(model)
                if index >= 0:
                    self.llm_model_combo.setCurrentIndex(index)

    def update_llm_models(self):
        """Update available models based on selected provider."""
        from gui.main_window import MainWindow

        provider = self.llm_provider_combo.currentText()
        self.llm_model_combo.clear()

        # Get models for the selected provider
        models = MainWindow.get_llm_models_for_provider(provider)
        if models:
            self.llm_model_combo.addItems(models)

        # Trigger model change to update parameter visibility
        self.on_model_changed()

    def on_model_changed(self, text=None):
        """Handle model change to show/hide GPT-5 specific parameters."""
        if text is None:
            text = self.llm_model_combo.currentText()

        # Show GPT-5 params only for GPT-5 models, hide standard params
        is_gpt5 = "gpt-5" in text.lower() if text else False
        self.gpt5_params_widget.setVisible(is_gpt5)
        self.standard_params_widget.setVisible(not is_gpt5)

    def generate_prompts(self):
        """Generate prompts using LLM."""
        input_text = self.input_text.toPlainText().strip()
        if not input_text:
            QMessageBox.warning(self, "Input Required", "Please enter an idea or concept.")
            return

        # Get settings
        num_variations = self.num_variations_spin.value()
        llm_provider = self.llm_provider_combo.currentText()
        llm_model = self.llm_model_combo.currentText()

        # Get API key using same method as enhance prompt for backward compatibility
        api_key = None
        if self.config:
            provider_lower = llm_provider.lower()

            # Try multiple locations for backward compatibility
            if provider_lower == "openai":
                # Use ConfigManager's get_api_key method
                api_key = self.config.get_api_key('openai')
                # Check direct config as fallback
                if not api_key:
                    api_key = self.config.get('openai_api_key')

            elif provider_lower == "gemini" or provider_lower == "google":
                # Use ConfigManager's get_api_key method
                api_key = self.config.get_api_key('google')
                # Check direct config (try multiple keys)
                if not api_key:
                    api_key = self.config.get('google_api_key') or self.config.get('api_key')
                # Check using get_api_key method
                if not api_key:
                    api_key = self.config.get_api_key('google')

            elif provider_lower == "claude" or provider_lower == "anthropic":
                # Use ConfigManager's get_api_key method
                api_key = self.config.get_api_key('anthropic')
                # Check direct config as fallback
                if not api_key:
                    api_key = self.config.get('anthropic_api_key')

            elif provider_lower == "stability":
                # Use ConfigManager's get_api_key method
                api_key = self.config.get_api_key('stability')
                # Check direct config as fallback
                if not api_key:
                    api_key = self.config.get('stability_api_key')

            if not api_key:
                QMessageBox.warning(
                    self, "API Key Required",
                    f"Please configure your {llm_provider} API key in Settings."
                )
                return
        else:
            QMessageBox.warning(self, "Config Error", "Configuration not available.")
            return

        # Save session for restoration
        self.save_last_session()

        # Disable UI during generation
        self.generate_btn.setEnabled(False)
        self.generate_btn.setText("Generating...")

        # Clear previous results
        self.results_list.clear()
        self.preview_text.clear()

        # Log to status console
        self.status_console.clear()
        self.status_console.log(f"Generating {num_variations} prompt variations...", "INFO")
        self.status_console.log(f"Provider: {llm_provider}, Model: {llm_model}", "INFO")

        # Get GPT-5 specific params if applicable
        is_gpt5 = self.gpt5_params_widget.isVisible()
        if is_gpt5:
            reasoning = self.reasoning_combo.currentText()
            verbosity = self.verbosity_combo.currentText()
            temperature = 1.0  # GPT-5 only supports temperature=1
            max_tokens = 1500  # Default for GPT-5
        else:
            reasoning = "medium"
            verbosity = "medium"
            temperature = self.temperature_spin.value()
            max_tokens = self.max_tokens_spin.value()

        # Ensure sufficient tokens for the requested number of variations
        # Each detailed prompt needs ~150 tokens, plus overhead for JSON formatting
        min_tokens = num_variations * 150 + 100
        if max_tokens < min_tokens:
            max_tokens = min_tokens
            logger.warning(f"Increased max_tokens from {self.max_tokens_spin.value()} to {max_tokens} for {num_variations} variations")
            console.warning(f"Increased max_tokens to {max_tokens} to accommodate {num_variations} variations")

        # Create worker thread
        self.thread = QThread()
        self.worker = LLMWorker(
            "generate", input_text, num_variations,
            llm_provider, llm_model, api_key,
            temperature, max_tokens, reasoning, verbosity
        )
        self.worker.moveToThread(self.thread)

        # Connect signals
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_generation_finished)
        self.worker.error.connect(self.on_generation_error)
        self.worker.progress.connect(self.on_generation_progress)
        self.worker.log_message.connect(self.on_log_message)
        self.worker.finished.connect(self.thread.quit)
        self.worker.error.connect(self.thread.quit)
        self.thread.finished.connect(self.cleanup_thread)

        self.thread.start()

    def on_generation_finished(self, prompts: List[str]):
        """Handle successful generation."""
        self.generated_prompts = prompts
        self.status_console.log(f"Successfully generated {len(prompts)} prompts!", "SUCCESS")

        # Add to results list
        for i, prompt in enumerate(prompts, 1):
            item = QListWidgetItem(f"Variation {i}: {prompt[:80]}...")
            item.setData(Qt.UserRole, prompt)
            self.results_list.addItem(item)

        # Select first item
        if self.results_list.count() > 0:
            self.results_list.setCurrentRow(0)

        # Save to history (no error)
        self.save_to_history(self.input_text.toPlainText(), prompts, error=None)
        self.update_history_list()

        # Re-enable UI
        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Prompts")

    def on_generation_error(self, error: str):
        """Handle generation error."""
        QMessageBox.critical(self, "Generation Error", error)
        self.status_console.log(f"Error: {error}", "ERROR")

        # Save to history with error
        self.save_to_history(self.input_text.toPlainText(), [], error=error)
        self.update_history_list()

        self.generate_btn.setEnabled(True)
        self.generate_btn.setText("Generate Prompts")

    def on_generation_progress(self, message: str):
        """Handle progress updates."""
        self.generate_btn.setText(message)
        self.status_console.log(message, "INFO")

    def on_log_message(self, message: str, level: str):
        """Handle log message from worker."""
        self.status_console.log(message, level)

    def cleanup_thread(self):
        """Clean up worker thread."""
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        if self.thread:
            self.thread.deleteLater()
            self.thread = None

    def on_selection_changed(self, current, previous):
        """Handle selection change in results list."""
        if current:
            prompt = current.data(Qt.UserRole)
            self.preview_text.setPlainText(prompt)

    def on_item_double_clicked(self, item):
        """Handle double-click on result item."""
        prompt = item.data(Qt.UserRole)
        self.promptSelected.emit(prompt)
        self.accept()

    def on_history_item_double_clicked(self, item):
        """Handle double-click on history item."""
        prompt = item.data(Qt.UserRole)
        self.promptSelected.emit(prompt)
        self.accept()

    def accept_selection(self):
        """Accept the selected prompt."""
        current_tab = self.tab_widget.currentIndex()

        if current_tab == 0:  # Generate tab
            # Check if any prompts have been generated
            if self.results_list.count() == 0:
                QMessageBox.warning(
                    self,
                    "No Prompts Generated",
                    "Please generate a prompt first.\n\nClick 'Generate Prompts' to create prompts, or press Esc or click Cancel to close this dialog."
                )
                return

            current_item = self.results_list.currentItem()
            if current_item:
                prompt = current_item.data(Qt.UserRole)
                self.promptSelected.emit(prompt)
                self.accept()
            else:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select a prompt from the list.\n\nDouble-click a prompt or select one and click OK."
                )
        else:  # History tab
            current_item = self.history_list.currentItem()
            if current_item:
                # Check if it's an error entry
                prompt = current_item.data(Qt.UserRole)
                if prompt and prompt.startswith("Error:"):
                    QMessageBox.warning(
                        self,
                        "Error Entry Selected",
                        "You've selected an error entry. Please select a valid prompt from the history."
                    )
                    return
                self.promptSelected.emit(prompt)
                self.accept()
            else:
                QMessageBox.warning(
                    self,
                    "No Selection",
                    "Please select a prompt from the history.\n\nDouble-click a prompt or select one and click OK."
                )

    def save_to_history(self, input_text: str, prompts: List[str], error: str = None):
        """Save generated prompts to history."""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "input": input_text,
            "prompts": prompts,
            "provider": self.llm_provider_combo.currentText(),
            "model": self.llm_model_combo.currentText(),
            "error": error  # Track if there was an error
        }
        self.prompt_history.append(entry)
        self.save_history()

    def load_history(self) -> List[Dict]:
        """Load prompt history from file."""
        if self.config:
            history_file = Path(self.config.config_dir) / "prompt_history.json"
            if history_file.exists():
                try:
                    with open(history_file, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load prompt history: {e}")
        return []

    def save_history(self):
        """Save prompt history to file."""
        if self.config:
            history_file = Path(self.config.config_dir) / "prompt_history.json"
            try:
                with open(history_file, 'w') as f:
                    json.dump(self.prompt_history, f, indent=2)
            except Exception as e:
                logger.error(f"Failed to save prompt history: {e}")

    def update_history_list(self):
        """Update the history list widget."""
        self.history_list.clear()
        for entry in reversed(self.prompt_history):  # Show newest first
            timestamp = entry.get("timestamp", "")
            input_text = entry.get("input", "")[:50]
            prompts = entry.get("prompts", [])
            error = entry.get("error")

            if error:
                # Show error entry
                display_text = f"[{timestamp[:10]}] ❌ ERROR: {input_text}... - {error[:50]}..."
                item = QListWidgetItem(display_text)
                item.setData(Qt.UserRole, f"Error: {error}")
                item.setForeground(Qt.red)
                self.history_list.addItem(item)
            else:
                # Show successful entries
                for prompt in prompts:
                    display_text = f"[{timestamp[:10]}] {input_text}... → {prompt[:80]}..."
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.UserRole, prompt)
                    self.history_list.addItem(item)

    def clear_history(self):
        """Clear the prompt history."""
        reply = QMessageBox.question(
            self, "Clear History",
            "Are you sure you want to clear all prompt history?",
            QMessageBox.Yes | QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            self.prompt_history.clear()
            self.save_history()
            self.update_history_list()

    def save_last_session(self):
        """Save the current session state."""
        if self.config:
            # Save LLM settings to config (application-wide)
            self.config.set('llm_provider', self.llm_provider_combo.currentText())
            self.config.set('llm_model', self.llm_model_combo.currentText())

            # Save all settings to QSettings for persistence
            self.settings.setValue("temperature", self.temperature_spin.value())
            self.settings.setValue("max_tokens", self.max_tokens_spin.value())
            self.settings.setValue("reasoning_effort", self.reasoning_combo.currentText())
            self.settings.setValue("verbosity", self.verbosity_combo.currentText())

            session = {
                "input_text": self.input_text.toPlainText(),
                "num_variations": self.num_variations_spin.value(),
                "llm_provider": self.llm_provider_combo.currentText(),
                "llm_model": self.llm_model_combo.currentText(),
                "temperature": self.temperature_spin.value(),
                "max_tokens": self.max_tokens_spin.value(),
                "reasoning_effort": self.reasoning_combo.currentText(),
                "verbosity": self.verbosity_combo.currentText()
            }
            session_file = Path(self.config.config_dir) / "prompt_gen_session.json"
            try:
                with open(session_file, 'w') as f:
                    json.dump(session, f, indent=2)
            except Exception as e:
                self.logger.error(f"Failed to save session: {e}")

    def load_last_session(self) -> Dict:
        """Load the last session state."""
        if self.config:
            session_file = Path(self.config.config_dir) / "prompt_gen_session.json"
            if session_file.exists():
                try:
                    with open(session_file, 'r') as f:
                        return json.load(f)
                except Exception as e:
                    logger.error(f"Failed to load session: {e}")
        return {}

    def restore_last_session(self):
        """Restore the last session state."""
        # First restore from QSettings
        temperature = self.settings.value("temperature", type=float)
        if temperature is not None:
            self.temperature_spin.setValue(temperature)

        max_tokens = self.settings.value("max_tokens", type=int)
        if max_tokens is not None:
            # Enforce minimum of 200 tokens (old sessions may have had 100)
            if max_tokens < 200:
                max_tokens = 1500  # Reset to default if too low
            self.max_tokens_spin.setValue(max_tokens)

        reasoning = self.settings.value("reasoning_effort", "medium")
        index = self.reasoning_combo.findText(reasoning)
        if index >= 0:
            self.reasoning_combo.setCurrentIndex(index)

        verbosity = self.settings.value("verbosity", "medium")
        index = self.verbosity_combo.findText(verbosity)
        if index >= 0:
            self.verbosity_combo.setCurrentIndex(index)

        # Then restore from session file
        if self.last_session:
            # Restore input text
            if "input_text" in self.last_session:
                self.input_text.setPlainText(self.last_session["input_text"])

            # Restore num variations
            if "num_variations" in self.last_session:
                self.num_variations_spin.setValue(self.last_session["num_variations"])

            # Restore LLM provider
            if "llm_provider" in self.last_session:
                index = self.llm_provider_combo.findText(self.last_session["llm_provider"])
                if index >= 0:
                    self.llm_provider_combo.setCurrentIndex(index)

            # Restore LLM model
            if "llm_model" in self.last_session:
                index = self.llm_model_combo.findText(self.last_session["llm_model"])
                if index >= 0:
                    self.llm_model_combo.setCurrentIndex(index)

            # Restore temperature if in session
            if "temperature" in self.last_session:
                self.temperature_spin.setValue(self.last_session["temperature"])

            # Restore max tokens if in session
            if "max_tokens" in self.last_session:
                max_tokens_session = self.last_session["max_tokens"]
                # Enforce minimum of 200 tokens (old sessions may have had 100)
                if max_tokens_session < 200:
                    max_tokens_session = 1500  # Reset to default if too low
                self.max_tokens_spin.setValue(max_tokens_session)

            # Restore GPT-5 settings if in session
            if "reasoning_effort" in self.last_session:
                index = self.reasoning_combo.findText(self.last_session["reasoning_effort"])
                if index >= 0:
                    self.reasoning_combo.setCurrentIndex(index)

            if "verbosity" in self.last_session:
                index = self.verbosity_combo.findText(self.last_session["verbosity"])
                if index >= 0:
                    self.verbosity_combo.setCurrentIndex(index)

    def save_settings(self):
        """Save window geometry and splitter state."""
        self.settings.setValue("geometry", self.saveGeometry())
        # Find and save splitter state
        splitters = self.findChildren(QSplitter)
        if splitters:
            self.settings.setValue("splitter_state", splitters[0].saveState())
        # Save tab index
        if hasattr(self, 'tab_widget'):
            self.settings.setValue("tab_index", self.tab_widget.currentIndex())

    def restore_settings(self):
        """Restore window geometry and splitter state."""
        geometry = self.settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def reject(self):
        """Override reject to save settings before closing."""
        self.save_last_session()
        self.save_settings()
        super().reject()

    def closeEvent(self, event):
        """Handle close event."""
        # Stop any running worker
        if self.worker and self.thread and self.thread.isRunning():
            self.worker.stop()
            self.thread.quit()
            self.thread.wait()

        # Save session state
        self.save_last_session()
        # Save window settings
        self.save_settings()
        super().closeEvent(event)