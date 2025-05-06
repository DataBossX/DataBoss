
"""
Model Chain Module for Legal Document Extraction

Implements fallback chain logic with retry handling and response validation.
"""

import logging
import time
import random
from typing import Tuple, Optional, Callable, Dict
from functools import wraps

# Configure module logger
logger = logging.getLogger("legal_extractor.model_chain")
logging.basicConfig(level=logging.INFO)

# Configuration constants
MAX_RETRIES = 3
RETRY_DELAY = 2  # Seconds between retries
TIMEOUT = 10      # Operation timeout in seconds
MIN_RESPONSE_LENGTH = 10  # Minimum valid response length

def setup_logging(level=logging.INFO):
    logger.setLevel(level)
    handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

def is_valid(response: str) -> bool:
    if not response:
        logger.debug("Validation failed: Empty response")
        return False
    if len(response.strip()) < MIN_RESPONSE_LENGTH:
        logger.debug(f"Validation failed: Response too short ({len(response.strip())} chars)")
        return False
    return True

def retry(max_retries: int = MAX_RETRIES, delay: int = RETRY_DELAY):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    logger.warning(f"{func.__name__} attempt {attempt+1} failed: {str(e)}")
                    if attempt < max_retries - 1:
                        time.sleep(delay * (attempt + 1))
            logger.error(f"All retries failed for {func.__name__}: {str(last_error)}")
            return {"error": str(last_error)}
        return wrapper
    return decorator

def simulate_failure(probability: float = 0.3) -> bool:
    return random.random() < probability

@retry()
def query_qwen3(prompt: str) -> Dict[str, str]:
    logger.debug("Attempting Qwen3 API call")
    if simulate_failure(0.3):
        raise Exception("Qwen3 timeout")
    time.sleep(0.5)
    return {"content": f"Qwen3 response: {prompt[:50]}..."} if not simulate_failure(0.2) else {"content": "Short"}

@retry()
def query_gpt(prompt: str) -> Dict[str, str]:
    logger.debug("Attempting GPT API call")
    if simulate_failure(0.2):
        raise Exception("GPT rate limit exceeded")
    time.sleep(0.7)
    return {"content": f"GPT response: {prompt[:50]}..."} if not simulate_failure(0.1) else {"content": "Short"}

@retry()
def query_claude(prompt: str) -> Dict[str, str]:
    logger.debug("Attempting Claude API call")
    if simulate_failure(0.1):
        raise Exception("Claude connection error")
    time.sleep(0.9)
    return {"content": f"Claude response: {prompt[:50]}..."} if not simulate_failure(0.15) else {"content": "Short"}

def run_model_chain(prompt: str) -> Tuple[str, str]:
    logger.info("Starting model chain execution")
    models = [
        ("Qwen3", query_qwen3),
        ("GPT-4", query_gpt),
        ("Claude", query_claude)
    ]
    for model_name, query_func in models:
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Attempting {model_name} (attempt {attempt+1}/{MAX_RETRIES})")
                start_time = time.time()
                response = query_func(prompt)
                elapsed = time.time() - start_time
                if elapsed > TIMEOUT:
                    logger.warning(f"{model_name} exceeded timeout ({elapsed:.2f}s)")
                    continue
                if "error" in response:
                    logger.warning(f"{model_name} returned error: {response['error']}")
                    continue
                content = response.get("content", "")
                if is_valid(content):
                    logger.info(f"{model_name} succeeded with valid response")
                    return content, model_name
                logger.warning(f"{model_name} returned invalid response")
            except Exception as e:
                logger.error(f"Critical error with {model_name}: {str(e)}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY * (attempt + 1))
        logger.info(f"Moving to next model after {MAX_RETRIES} {model_name} attempts")
    logger.error("All models failed")
    return "All models failed", "None"

if __name__ == "__main__":
    setup_logging(logging.DEBUG)
    test_prompt = "This is a test prompt for legal document extraction."
    result, model = run_model_chain(test_prompt)
    print(f"Used model: {model}\nResponse: {result}")
