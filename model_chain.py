
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
def query_qwen(prompt: str) -> Dict[str, str]:
    """Query Qwen model through API"""
    try:
        import dashscope
        from dashscope.common.error import DashScopeError
        
        logger.debug("Attempting Qwen API call")
        response = dashscope.Generation.call(
            model='qwen-max',
            prompt=prompt,
            temperature=0.3,
            max_tokens=2048
        )
        
        if response.status_code == 200:
            return {"content": response.output.text}
        else:
            raise Exception(f"Qwen API error: {response.code} - {response.message}")
    except ImportError:
        logger.warning("dashscope not installed, falling back to OpenAI")
        return query_gpt(prompt)
    except Exception as e:
        logger.error(f"Qwen API call failed: {str(e)}")
        raise

@retry()
def query_gpt(prompt: str) -> Dict[str, str]:
    """Query OpenAI GPT models"""
    try:
        import openai
        
        logger.debug("Attempting GPT API call")
        response = openai.ChatCompletion.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048
        )
        
        return {"content": response.choices[0].message.content.strip()}
    except Exception as e:
        logger.error(f"GPT API call failed: {str(e)}")
        raise

@retry()
def query_claude(prompt: str) -> Dict[str, str]:
    """Query Anthropic Claude models"""
    try:
        import anthropic
        
        logger.debug("Attempting Claude API call")
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-3-opus-20240229",
            max_tokens=2048,
            temperature=0.3,
            system="You are an expert legal document analyzer. Extract key information from legal documents.",
            messages=[{"role": "user", "content": prompt}]
        )
        
        return {"content": response.content[0].text}
    except Exception as e:
        logger.error(f"Claude API call failed: {str(e)}")
        raise

@retry()
def query_deepseek(prompt: str) -> Dict[str, str]:
    """Query DeepSeek models"""
    try:
        import deepseek
        
        logger.debug("Attempting DeepSeek API call")
        client = deepseek.DeepSeekClient()
        response = client.chat.completions.create(
            model="deepseek-chat",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=2048
        )
        
        return {"content": response.choices[0].message.content}
    except ImportError:
        logger.warning("deepseek package not available, falling back to OpenAI")
        return query_gpt(prompt)
    except Exception as e:
        logger.error(f"DeepSeek API call failed: {str(e)}")
        raise

def run_model_chain(prompt: str) -> Tuple[str, str]:
    """
    Run prompt through a chain of LLM models, trying each until success.
    
    Args:
        prompt: Text prompt to send to models
        
    Returns:
        Tuple of (response_text, model_name)
    """
    logger.info("Starting model chain execution")
    models = [
        ("Qwen", query_qwen),
        ("GPT-4", query_gpt),
        ("Claude", query_claude),
        ("DeepSeek", query_deepseek)
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
