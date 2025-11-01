"""
Application configuration for claim extraction
"""
import os
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Default prompt file (relative to prompts/ directory)
DEFAULT_PROMPT = 'simple'

def load_prompt_file(file_param: str) -> str:
    """Load prompt content from file path or name in prompts/ directory"""
    if not file_param:
        return ""

    # If absolute path (starts with /), use as-is
    if file_param.startswith('/'):
        if os.path.isfile(file_param):
            with open(file_param, 'r') as f:
                return f.read().strip()
        else:
            logger.warning(f"Could not find prompt file at absolute path: {file_param}")
            return ""

    # Relative path - look in src/prompts/ directory
    prompt_path = Path(__file__).parent / "prompts" / f"{file_param}.md"
    if prompt_path.exists():
        with open(prompt_path, 'r') as f:
            return f.read().strip()

    # Try with .md already included
    prompt_path = Path(__file__).parent / "prompts" / file_param
    if prompt_path.exists():
        with open(prompt_path, 'r') as f:
            return f.read().strip()

    logger.warning(f"Could not find prompt file: {file_param} (looked in src/prompts/ directory)")
    return ""


def configure_prompts(app):
    """Configure Flask app with prompt settings"""
    # Load prompt files from environment or use default
    message_file = os.getenv('LT_USE_PROMPT_FILE', DEFAULT_PROMPT)
    extra_file = os.getenv('LT_EXTRA_SYSTEM_PROMPT_FILE')

    # Store loaded prompts in app config
    app.config['LT_MESSAGE_PROMPT'] = load_prompt_file(message_file) if message_file else None
    app.config['LT_EXTRA_SYSTEM_PROMPT'] = load_prompt_file(extra_file) if extra_file else ""

    if app.config['LT_MESSAGE_PROMPT']:
        logger.info(f"Loaded message prompt from '{message_file}' ({len(app.config['LT_MESSAGE_PROMPT'])} chars)")
    if app.config['LT_EXTRA_SYSTEM_PROMPT']:
        logger.info(f"Loaded extra system prompt from '{extra_file}' ({len(app.config['LT_EXTRA_SYSTEM_PROMPT'])} chars)")