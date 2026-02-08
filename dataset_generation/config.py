import os

# --- Paths ---
INPUT_PATH = "table"
OUTPUT_PATH = "document"

# --- Concurrency ---
# Maximum number of tables to process in parallel
MAX_PARALLEL_TASK = 100
# Maximum number of concurrent LLM requests globally
MAX_CONCURRENT_REQUESTS = 1000

# --- LLM Configuration ---
API_KEY = ""
BASE_URL = "https://openrouter.ai/api/v1"

LLM_TIMEOUT = 600  # Seconds
LLM_MAX_RETRIES = 3

# Model Configuration
PLANNER_MODEL = "google/gemini-3-pro-preview"
REFINER_MODEL = "x-ai/grok-4.1-fast"
WRITER_MODEL = "x-ai/grok-4.1-fast"
VERIFIER_MODEL = "x-ai/grok-4.1-fast"

CELL_GUIDANCE_VERIFY_MODEL = "x-ai/grok-4.1-fast"
FACT_GUIDANCE_VERIFY_MODEL = "x-ai/grok-4.1-fast"

# --- Agents Configuration ---
ENABLE_STRATEGY_ASSIGNMENT = True

FACTS_PER_SECTION_MIN = 0.5
FACTS_PER_SECTION_MAX = 3

MIN_SECTIONS = 80
MAX_SECTIONS = 160

REFINE_MAX_RETRIES = 3
PLAN_MAX_RETRIES = 3
VERIFY_AND_REPAIR_MAX_RETRIES = 4  # Max retries for verify & repair cycle