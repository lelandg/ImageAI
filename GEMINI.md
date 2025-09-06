# GEMINI.md

## Project Overview

This project, "ImageAI," is a Python-based desktop application that provides a graphical user interface (GUI) and a command-line interface (CLI) for generating images using Google's Gemini and OpenAI's DALL-E models. The application is built using the PySide6 framework for the GUI and Python's `argparse` library for the CLI. It allows users to securely store their API keys and manage image generation from different providers.

The application supports:
-   Generating images from text prompts using multiple AI providers
-   Switching between Google Gemini and OpenAI DALL·E models
-   Two authentication methods for Google: API Keys and Google Cloud ADC
-   A modern GUI with tabs for generation, settings, templates, and help
-   A powerful CLI for scripting and automation
-   Secure, cross-platform storage of API keys and credentials
-   Auto-saving of generated images with JSON metadata sidecars
-   Template system with placeholder substitution
-   In-session history tracking and management
-   Enterprise-ready Google Cloud authentication support

## Building and Running

To build and run this project, you need Python 3.9+ and the dependencies listed in `requirements.txt`.

1.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

2.  **Run the application:**

    *   **GUI Mode:**
        ```bash
        python main.py
        ```

    *   **CLI Mode (with an example prompt):**
        ```bash
        python main.py -p "A futuristic cityscape at sunset"
        ```

## Development Conventions

-   **GUI:** The graphical user interface is built with **PySide6**. The main window and its components are defined in the `MainWindow` class in `main.py`.
-   **CLI:** The command-line interface is handled using Python's `argparse` module. CLI logic is in the `run_cli` function in `main.py`.
-   **Dependencies:** Project dependencies are managed in the `requirements.txt` file. Key libraries include `google-genai`, `openai`, and `PySide6`.
-   **Configuration:** User-specific configuration, such as API keys, is stored in a `config.json` file in the user's application data directory.
-   **Code Structure:** The main application logic is contained within `main.py`. The file is organized into sections for CLI, UI, API key handling, and helper functions.
