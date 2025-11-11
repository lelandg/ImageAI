#!/usr/bin/env python3
"""Generate semantic tags for all prompt builder items using LLM.

This script generates metadata (tags, descriptions, relationships) for all
items in the prompt builder (artists, styles, mediums, colors, lighting, moods).

It uses a single LLM pass to generate comprehensive metadata that enables
semantic search and smart filtering.

Usage:
    python scripts/generate_tags.py [--test] [--limit N] [--provider PROVIDER]

Options:
    --test          Test mode: only process first 10 items from each category
    --limit N       Process only N items from each category (default: all)
    --provider      LLM provider to use (default: google, options: google, openai)
    --model         Model to use (default: gemini-2.0-flash-exp for google)
"""

import json
import logging
import sys
import time
import signal
from pathlib import Path
from typing import Dict, List, Optional
import argparse
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    from tqdm import tqdm
except ImportError:
    print("Error: tqdm not installed. Install with: pip install tqdm")
    sys.exit(1)

try:
    import litellm
except ImportError:
    print("Error: litellm not installed. Install with: pip install litellm")
    sys.exit(1)

from core.prompt_data_loader import PromptDataLoader
from core.config import ConfigManager

# Setup logging to both file and console
log_filename = f"generate_tags_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
log_filepath = Path.cwd() / log_filename

# Configure root logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filepath, encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Disable litellm's verbose logging
litellm.set_verbose = False

# Global flag for clean shutdown
shutdown_requested = False


def signal_handler(signum, frame):
    """Handle interrupt signals (Ctrl+C)."""
    global shutdown_requested
    shutdown_requested = True
    logger.warning("\n\n⚠️  Interrupt received! Saving progress and shutting down gracefully...")
    logger.warning(f"Log file saved to: {log_filepath}")


# Register signal handler
signal.signal(signal.SIGINT, signal_handler)
if hasattr(signal, 'SIGTERM'):
    signal.signal(signal.SIGTERM, signal_handler)


class TagGenerator:
    """Generates semantic tags and metadata for prompt builder items."""

    def __init__(self, provider: str = "google", model: Optional[str] = None):
        """Initialize the tag generator.

        Args:
            provider: LLM provider to use (google, openai)
            model: Optional model override
        """
        self.provider = provider
        self.config = ConfigManager()

        # Set default models by provider
        if model:
            self.model = model
        elif provider == "google":
            # Check auth mode to determine which endpoint to use
            auth_mode = self.config.get_auth_mode("google")
            if auth_mode == "gcloud":
                # Use Vertex AI endpoint for gcloud auth (supports OAuth2 tokens)
                # Use stable 1.5 Flash instead of experimental 2.0 to avoid quota issues
                self.model = "vertex_ai/gemini-1.5-flash"
                logger.info("Using Vertex AI endpoint (supports gcloud OAuth2 tokens)")
                logger.info("Using gemini-1.5-flash (stable model with higher quotas)")
            else:
                # Use Gemini API endpoint for API keys
                self.model = "gemini/gemini-2.0-flash-exp"
        elif provider == "openai":
            # Use gpt-5-chat-latest (best available GPT-5 model)
            self.model = "gpt-5-chat-latest"
        else:
            self.model = "gemini/gemini-2.0-flash-exp"

        # Get API key (handles both API key and gcloud auth)
        # _get_api_key will log detailed auth information
        self.api_key = self._get_api_key()
        if not self.api_key:
            logger.error(f"\n{'='*60}")
            logger.error("AUTHENTICATION FAILED")
            logger.error(f"{'='*60}")
            logger.error(f"No API key or access token found for provider: {provider}")
            logger.error("")
            if provider == "google":
                auth_mode = self.config.get_auth_mode("google")
                if auth_mode == "gcloud":
                    logger.error("You are using Google Cloud authentication mode.")
                    logger.error("Please run: gcloud auth application-default login")
                else:
                    logger.error("You are using API key authentication mode.")
                    logger.error("Please set a Google API key in the ImageAI Settings.")
            logger.error(f"{'='*60}\n")
            raise ValueError(f"No API key found for provider: {provider}")

        logger.info(f"✓ Authentication successful")
        logger.info(f"Initialized TagGenerator with provider={provider}, model={self.model}")

        # Log project ID for Vertex AI
        if self.model.startswith("vertex_ai/"):
            project_id = self.config.get_gcloud_project_id()
            if project_id:
                logger.info(f"Google Cloud Project ID: {project_id}")
            else:
                logger.warning("⚠️  No Google Cloud project ID configured")
                logger.warning("   Set with: gcloud config set project YOUR_PROJECT_ID")
                logger.warning("   Or the script will use your default project")

    def _get_api_key(self) -> Optional[str]:
        """Get API key for the configured provider."""
        if self.provider == "google":
            # Check auth mode first
            auth_mode = self.config.get_auth_mode("google")
            logger.info(f"Google auth mode: {auth_mode}")

            # If using gcloud, try to get token with detailed logging
            if auth_mode == "gcloud":
                logger.info("Attempting to get gcloud access token...")
                try:
                    from core.gcloud_utils import find_gcloud_command
                    import subprocess
                    import platform

                    gcloud_cmd = find_gcloud_command()
                    if not gcloud_cmd:
                        logger.error("gcloud command not found. Make sure Google Cloud SDK is installed.")
                        logger.error("Install from: https://cloud.google.com/sdk/docs/install")
                        logger.error("After installing, run: gcloud auth application-default login")
                        return None

                    logger.info(f"Found gcloud command: {gcloud_cmd}")
                    logger.info(f"Executing: {gcloud_cmd} auth application-default print-access-token")
                    logger.info(f"This may take 10-15 seconds on Windows...")

                    result = subprocess.run(
                        [gcloud_cmd, "auth", "application-default", "print-access-token"],
                        capture_output=True,
                        text=True,
                        timeout=30,  # Increased from 5 to 30 seconds for Windows .cmd files
                        shell=(platform.system() == "Windows")
                    )

                    logger.debug(f"gcloud command completed with exit code: {result.returncode}")

                    if result.returncode == 0:
                        token = result.stdout.strip()
                        if token:
                            logger.info("Successfully obtained gcloud access token")
                            logger.debug(f"Token length: {len(token)} chars")
                            return token
                        else:
                            logger.error("gcloud returned empty token")
                            return None
                    else:
                        logger.error(f"gcloud command failed with exit code: {result.returncode}")
                        if result.stderr:
                            logger.error(f"Error output: {result.stderr}")
                        logger.error("Run: gcloud auth application-default login")
                        return None

                except subprocess.TimeoutExpired:
                    logger.error("Timeout getting gcloud token (>30 seconds)")
                    logger.error("gcloud command is taking too long to respond.")
                    logger.error("")
                    logger.error("Workarounds:")
                    logger.error("1. Try running the script again (first run is often slower)")
                    logger.error("2. Use OpenAI instead: python scripts/generate_tags.py --test --provider openai")
                    logger.error("3. Set a Google API key in ImageAI Settings and use API key auth mode")
                    return None
                except Exception as e:
                    logger.error(f"Error getting gcloud token: {type(e).__name__}: {e}")
                    return None

            # Fall through to regular API key lookup
            return self.config.get_api_key('google')

        elif self.provider == "openai":
            return self.config.get_api_key('openai')
        return None

    def generate_metadata(self, item: str, category: str, retry_count: int = 3) -> Optional[Dict]:
        """Generate metadata for a single item.

        Args:
            item: The item name (e.g., "Al Jaffee", "Comic Art")
            category: The category (e.g., "artists", "styles")
            retry_count: Number of retries on failure

        Returns:
            Dictionary with metadata, or None on failure
        """
        prompt = self._build_prompt(item, category)

        for attempt in range(retry_count):
            try:
                # Build completion parameters
                # GPT-5 and O1 models require temperature=1.0
                temperature = 1.0 if any(x in self.model.lower() for x in ["gpt-5", "o1", "o3"]) else 0.3

                completion_params = {
                    "model": self.model,
                    "messages": [{"role": "user", "content": prompt}],
                    "api_key": self.api_key,
                    "temperature": temperature,
                    "max_tokens": 500
                }

                # Add vertex_project for Vertex AI models
                if self.model.startswith("vertex_ai/"):
                    project_id = self.config.get_gcloud_project_id()
                    if project_id:
                        completion_params["vertex_project"] = project_id
                        completion_params["vertex_location"] = "us-central1"  # Default location
                    else:
                        logger.warning("No Google Cloud project ID found. Set with: gcloud config set project PROJECT_ID")

                # Call LLM
                response = litellm.completion(**completion_params)

                # Extract response
                content = response.choices[0].message.content.strip()

                # Parse JSON
                metadata = self._parse_json_response(content)

                if metadata:
                    return metadata
                else:
                    logger.warning(f"Failed to parse JSON for {item} (attempt {attempt + 1}/{retry_count})")

            except Exception as e:
                error_msg = str(e)
                logger.warning(f"Error generating metadata for {item} (attempt {attempt + 1}/{retry_count}): {e}")

                if attempt < retry_count - 1:
                    # Check if it's a rate limit error
                    if "429" in error_msg or "RESOURCE_EXHAUSTED" in error_msg or "Quota exceeded" in error_msg:
                        # Exponential backoff for rate limits: 5s, 10s, 20s
                        backoff_time = 5 * (2 ** attempt)
                        logger.warning(f"Rate limit hit. Waiting {backoff_time}s before retry...")
                        time.sleep(backoff_time)
                    else:
                        # Regular retry delay
                        time.sleep(1)

        # Return minimal metadata if all attempts fail
        logger.error(f"Failed to generate metadata for {item} after {retry_count} attempts")
        return self._create_fallback_metadata(item, category)

    def _build_prompt(self, item: str, category: str) -> str:
        """Build the LLM prompt for generating metadata.

        Args:
            item: The item name
            category: The category

        Returns:
            Formatted prompt string
        """
        if category == "artists":
            return f"""Generate semantic metadata for the artist "{item}" to enable search and discovery in an AI image generation tool.

Return JSON with these fields:
- tags: List of 5-8 lowercase tags (e.g., ["mad_magazine", "caricature", "satire", "1960s", "comics"])
- related_styles: List of 2-4 art styles that match this artist (e.g., ["Comic Art", "Cartoon Art"])
- related_moods: List of 2-4 moods associated with this artist (e.g., ["Satirical", "Humorous"])
- cultural_keywords: List of 3-6 search keywords people might use (e.g., ["MAD Magazine", "fold-in", "satirical cartoons"])
- description: Brief 1-sentence description (e.g., "Legendary MAD Magazine cartoonist")
- era: Time period active (e.g., "1960s-2010s")
- popularity: Estimated popularity score 1-10 (10 = household name)

Return ONLY valid JSON, no markdown formatting."""

        elif category == "styles":
            return f"""Generate semantic metadata for the art style "{item}" to enable search and discovery in an AI image generation tool.

Return JSON with these fields:
- tags: List of 5-8 lowercase tags (e.g., ["comic", "cartoon", "satirical", "vintage"])
- related_artists: List of 2-4 artists known for this style (e.g., ["Al Jaffee", "Mort Drucker"])
- related_moods: List of 2-4 moods that fit this style (e.g., ["Satirical", "Humorous"])
- cultural_keywords: List of 3-6 search keywords (e.g., ["comic book art", "sequential art"])
- description: Brief 1-sentence description
- era: When this style was most popular (e.g., "1960s-1980s")
- popularity: Estimated popularity score 1-10

Return ONLY valid JSON, no markdown formatting."""

        elif category == "mediums":
            return f"""Generate semantic metadata for the art medium "{item}" to enable search and discovery.

Return JSON with these fields:
- tags: List of 4-6 lowercase tags describing the medium
- related_styles: List of 2-3 art styles commonly using this medium
- cultural_keywords: List of 2-4 search keywords
- description: Brief 1-sentence description
- popularity: Estimated popularity score 1-10

Return ONLY valid JSON, no markdown formatting."""

        elif category == "colors":
            return f"""Generate semantic metadata for the color scheme "{item}" to enable search and discovery.

Return JSON with these fields:
- tags: List of 3-5 lowercase tags describing the color palette
- related_moods: List of 2-3 moods associated with these colors
- cultural_keywords: List of 2-4 search keywords
- description: Brief 1-sentence description
- popularity: Estimated popularity score 1-10

Return ONLY valid JSON, no markdown formatting."""

        elif category == "lighting":
            return f"""Generate semantic metadata for the lighting type "{item}" to enable search and discovery.

Return JSON with these fields:
- tags: List of 3-5 lowercase tags describing the lighting
- related_moods: List of 2-3 moods created by this lighting
- cultural_keywords: List of 2-4 search keywords
- description: Brief 1-sentence description
- popularity: Estimated popularity score 1-10

Return ONLY valid JSON, no markdown formatting."""

        elif category == "moods":
            return f"""Generate semantic metadata for the mood "{item}" to enable search and discovery.

Return JSON with these fields:
- tags: List of 3-5 lowercase tags describing this mood
- related_styles: List of 2-3 art styles that evoke this mood
- related_colors: List of 2-3 color schemes that match this mood
- cultural_keywords: List of 2-4 search keywords
- description: Brief 1-sentence description
- popularity: Estimated popularity score 1-10

Return ONLY valid JSON, no markdown formatting."""

        else:
            # Generic fallback
            return f"""Generate semantic metadata for "{item}" (category: {category}) to enable search and discovery.

Return JSON with these fields:
- tags: List of 3-5 lowercase tags
- cultural_keywords: List of 2-4 search keywords
- description: Brief 1-sentence description
- popularity: Estimated popularity score 1-10

Return ONLY valid JSON, no markdown formatting."""

    def _parse_json_response(self, content: str) -> Optional[Dict]:
        """Parse JSON from LLM response, handling markdown formatting.

        Args:
            content: Raw response content

        Returns:
            Parsed JSON dict, or None if parsing fails
        """
        # Remove markdown code fences if present
        if content.startswith("```"):
            # Find the first and last code fence
            lines = content.split('\n')
            start_idx = 0
            end_idx = len(lines)

            for i, line in enumerate(lines):
                if line.startswith("```"):
                    if start_idx == 0:
                        start_idx = i + 1
                    else:
                        end_idx = i
                        break

            content = '\n'.join(lines[start_idx:end_idx])

        # Try to parse JSON
        try:
            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"JSON parse error: {e}")
            logger.debug(f"Content: {content}")
            return None

    def _create_fallback_metadata(self, item: str, category: str) -> Dict:
        """Create minimal fallback metadata when LLM fails.

        Args:
            item: The item name
            category: The category

        Returns:
            Basic metadata dictionary
        """
        # Create basic tags from the item name
        tags = [word.lower().replace(' ', '_') for word in item.split()][:3]

        return {
            "tags": tags,
            "cultural_keywords": [item],
            "description": f"{item} - {category}",
            "popularity": 5  # Neutral default
        }


def main():
    """Main entry point for tag generation."""
    # Print startup banner
    print("=" * 70)
    print("  ImageAI - Tag Generation Script")
    print("=" * 70)
    print(f"  Log file: {log_filepath}")
    print(f"  Press Ctrl+C to abort (progress will be saved)")
    print("=" * 70)
    print()

    # Parse command-line arguments
    parser = argparse.ArgumentParser(description="Generate semantic tags for prompt builder items")
    parser.add_argument("--test", action="store_true", help="Test mode: process only first 10 items")
    parser.add_argument("--limit", type=int, help="Limit number of items per category")
    parser.add_argument("--provider", default="google", choices=["google", "openai"],
                       help="LLM provider to use")
    parser.add_argument("--model", help="Model to use (overrides default)")
    args = parser.parse_args()

    # Apply test mode limit
    if args.test:
        args.limit = 10
        logger.info("Test mode: processing only first 10 items per category")

    # Initialize
    try:
        generator = TagGenerator(provider=args.provider, model=args.model)
    except ValueError as e:
        logger.error(f"Initialization failed: {e}")
        logger.info("Make sure you have set up API keys in Settings or environment variables")
        return 1

    data_loader = PromptDataLoader()

    # Load all items
    logger.info("Loading prompt builder items...")
    all_categories = data_loader.get_all_categories()

    # Count total items
    total_items = sum(len(items) for items in all_categories.values())
    if args.limit:
        total_items = min(total_items, args.limit * len(all_categories))

    logger.info(f"Processing {total_items} items across {len(all_categories)} categories")
    logger.info(f"Log file: {log_filepath}")

    # Load existing metadata if it exists (for resume capability)
    output_path = Path(__file__).parent.parent / "data" / "prompts" / "metadata.json"
    existing_metadata = {}
    if output_path.exists():
        try:
            with open(output_path, 'r', encoding='utf-8') as f:
                existing_metadata = json.load(f)
            existing_count = sum(len(cat) for cat in existing_metadata.values())
            logger.info(f"Found existing metadata file with {existing_count} items")
            logger.info(f"Will skip already-processed items and only generate missing ones")
        except Exception as e:
            logger.warning(f"Could not load existing metadata: {e}")
            existing_metadata = {}

    # Generate metadata
    metadata = existing_metadata.copy()  # Start with existing data
    interrupted = False

    try:
        with tqdm(total=total_items, desc="Generating metadata") as pbar:
            for category, items in all_categories.items():
                # Check for shutdown request
                if shutdown_requested:
                    interrupted = True
                    break

                # Apply limit if specified
                if args.limit:
                    items = items[:args.limit]

                # Get existing category data or create new
                category_metadata = metadata.get(category, {})

                # Ensure category_metadata is a dict (handle malformed data)
                if not isinstance(category_metadata, dict):
                    logger.warning(f"Invalid metadata format for {category}, resetting to empty dict")
                    category_metadata = {}
                    metadata[category] = category_metadata

                items_to_process = []
                items_skipped = 0

                # Determine which items need processing
                for item in items:
                    # Handle dict items (e.g., colors.json has {name: "", colors: []})
                    if isinstance(item, dict):
                        # Extract 'name' field if present
                        if 'name' in item and item['name']:
                            item = item['name']
                        else:
                            logger.warning(f"Skipping dict item without 'name' in {category}")
                            pbar.update(1)
                            continue

                    # Skip non-string items after extraction
                    if not isinstance(item, str):
                        logger.warning(f"Skipping invalid item in {category}: {type(item).__name__}")
                        pbar.update(1)
                        continue

                    if item in category_metadata:
                        items_skipped += 1
                        pbar.update(1)  # Count skipped items toward progress
                    else:
                        items_to_process.append(item)

                if items_skipped > 0:
                    logger.info(f"Skipping {items_skipped} already-processed items in {category}")

                # Process only new items
                for item in items_to_process:
                    # Check for shutdown request
                    if shutdown_requested:
                        interrupted = True
                        break

                    # Update progress bar description
                    pbar.set_description(f"Processing {category}: {item[:30]}")

                    # Generate metadata
                    item_metadata = generator.generate_metadata(item, category)

                    if item_metadata:
                        category_metadata[item] = item_metadata

                    pbar.update(1)

                    # Delay to avoid rate limits
                    # Vertex AI free tier: 60 requests/minute = 1 per second
                    time.sleep(1.5)  # 1.5s = ~40 requests/minute (safe margin)

                metadata[category] = category_metadata

                # SAVE AFTER EACH CATEGORY (incremental save to prevent data loss on crash)
                try:
                    with open(output_path, 'w', encoding='utf-8') as f:
                        json.dump(metadata, f, indent=2, ensure_ascii=False)
                    logger.info(f"✓ Saved progress: {sum(len(v) for v in metadata.values())} items total")
                except Exception as e:
                    logger.error(f"Failed to save progress: {e}")

                if not interrupted:
                    logger.info(f"Completed {category}: {len(category_metadata)} items")
                else:
                    logger.warning(f"Interrupted during {category}: saved {len(category_metadata)} items")
                    break

    except KeyboardInterrupt:
        interrupted = True
        logger.warning("\n⚠️  Keyboard interrupt detected!")

    # Save results (even if interrupted)
    # Note: output_path already defined earlier when loading existing metadata
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Always save to metadata.json (resume-capable)
    if interrupted:
        logger.warning(f"Saving progress to: {output_path}")

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    total_generated = sum(len(cat) for cat in metadata.values())
    logger.info(f"Metadata saved to: {output_path}")
    logger.info(f"Generated metadata for {total_generated} items")
    logger.info(f"Log file saved to: {log_filepath}")

    # Print sample
    if metadata:
        logger.info("\n" + "="*60)
        logger.info("Sample metadata (first item):")
        logger.info("="*60)
        for cat_name, cat_data in metadata.items():
            if cat_data:
                first_item = list(cat_data.keys())[0]
                print(f"\n{cat_name} - {first_item}:")
                print(json.dumps(cat_data[first_item], indent=2))
                break

    if interrupted:
        logger.warning("\n⚠️  Process was interrupted. Progress saved.")
        logger.warning(f"   Run the script again to resume from where you left off.")
        logger.warning(f"   Already-processed items will be skipped automatically.")
        return 130  # Standard exit code for SIGINT

    return 0


if __name__ == "__main__":
    sys.exit(main())
