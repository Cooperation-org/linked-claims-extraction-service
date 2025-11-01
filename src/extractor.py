"""
Shared claim extraction functionality
"""
import logging
import os
from claim_extractor import ClaimExtractor

logger = logging.getLogger(__name__)

def extract_claims(extractor: ClaimExtractor, text: str):
    """
    Extract claims from text using the ClaimExtractor with a shared prompt
    
    Args:
        extractor: Pre-initialized ClaimExtractor instance
        text: The text to extract claims from
        
    Returns:
        List of extracted claims
    """
    # Load prompt from file
    # IMPORTANT: this omits the modular loading of different shemas and metadata from separate files,
    # and just includes them all in one text file
    prompt_file_path = os.path.join(os.path.dirname(__file__), 'prompt_and_examples.txt')
    with open(prompt_file_path, 'r') as f:
        prompt = f.read().strip()

#    print(f"INPUT PROMPT = {prompt}")
    use_prompt = True
    if use_prompt:
        # Pass text and prompt as separate arguments
        claims = extractor.extract_claims(text, prompt=prompt, override_prompt=use_prompt)
    else:
        claims = extractor.extract_claims(text)
    return claims
