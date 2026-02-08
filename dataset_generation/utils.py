import os
import json
import re
import logging
import time
from typing import Any, Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor
from openai import OpenAI
from json_repair import repair_json
import config
from datetime import datetime
import threading

# --- Logging Setup ---
def setup_logger(name: str = "agents_new", log_file: str = "agents.log", level=logging.INFO):
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove any existing handlers to avoid duplicates
    logger.handlers.clear()

    # Log to both console and file
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

logger = setup_logger()

# --- OpenAI Client ---
_client: Optional[OpenAI] = None

def get_openai_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=config.API_KEY,
            base_url=config.BASE_URL,
            timeout=config.LLM_TIMEOUT
        )
    return _client

# --- Global Executor for LLM Calls ---
# This ensures we don't exceed MAX_CONCURRENT_REQUESTS globally
llm_executor = ThreadPoolExecutor(max_workers=config.MAX_CONCURRENT_REQUESTS)

def call_llm(messages: List[Dict[str, str]], model: str = config.PLANNER_MODEL, json_mode: bool = False) -> str:
    """
    Wrapper to call OpenAI API with retry logic.
    """
    client = get_openai_client()
    retries = 0

    while retries < config.LLM_MAX_RETRIES:
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "extra_body": {
                    "reasoning": {
                        "effort": "high",
                        "enabled": True
                    }
                },
                "stream": False,
            }
            if json_mode:
                kwargs["response_format"] = {"type": "json_object"}

            response = client.chat.completions.create(**kwargs)
            response_content = response.choices[0].message.content

            return response_content
        except Exception as e:
            retries += 1
            logger.warning(f"LLM Call Failed (Attempt {retries}/{config.LLM_MAX_RETRIES}): {e}")
            if retries >= config.LLM_MAX_RETRIES:
                logger.error("Max retries reached. Raising exception.")
                raise
            time.sleep(2 ** retries) # Exponential backoff


def parse_json(text: str) -> Any:
    """
    Parse JSON from LLM response. First tries direct parsing,
    then uses json_repair library to fix malformed JSON.
    """
    # First, extract content between first '{' and last '}'
    start_brace = text.find('{')
    if start_brace == -1:
        raise json.JSONDecodeError("No opening brace '{' found", text, 0)

    end_brace = text.rfind('}')
    if end_brace == -1 or end_brace < start_brace:
        raise json.JSONDecodeError("No closing brace '}' found after opening brace", text, 0)

    extracted = text[start_brace:end_brace + 1]

    # Try direct parsing on extracted content
    try:
        return json.loads(extracted)
    except json.JSONDecodeError:
        pass

    # Try json_repair on extracted content
    try:
        repaired = repair_json(extracted)
        return json.loads(repaired)
    except Exception as e:
        logger.warning(f"json_repair failed on extracted content: {e}")

    raise json.JSONDecodeError("Failed to parse JSON after all attempts", text, 0)


# --- File I/O ---
def safe_filename(text: str, max_length: int = 100) -> str:
    """Converts a string into a safe format for a filename."""
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    text = text.replace(' ', '_')
    return text[:max_length]

def read_json(path: str) -> Any:
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def write_json(path: str, data: Any):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
