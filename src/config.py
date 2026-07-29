"""
Configuration & Constants

All magic numbers, thresholds, and settings live here.
Single source of truth for the entire pipeline.
"""

from dataclasses import dataclass
from pathlib import Path
import os


# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "crunchbase_data"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
LOG_DIR = PROJECT_ROOT / "logs"
CHECKPOINT_DIR = PROJECT_ROOT / "checkpoints"
CREDENTIALS_DIR = PROJECT_ROOT / "credentials"
PROMPTS_DIR = PROJECT_ROOT / "prompts"

# Stage-specific output directories (all under OUTPUT_DIR; contents are gitignored)
STAGE1_OUTPUT_DIR = OUTPUT_DIR / "stage1"
STAGE1_TAVILY_DIR = STAGE1_OUTPUT_DIR / "tavily"
STAGE1_GPT_DIR = STAGE1_OUTPUT_DIR / "gpt"
STAGE2_OUTPUT_DIR = OUTPUT_DIR / "stage2"
STAGE2_TEST_RUNS_DIR = STAGE2_OUTPUT_DIR / "test_runs"
STAGE2_RUNS_DIR = STAGE2_OUTPUT_DIR / "runs"
STAGE2_MASTER_JSONL = STAGE2_OUTPUT_DIR / "production_results.jsonl"
STAGE2_MASTER_CSV = STAGE2_OUTPUT_DIR / "production_results.csv"
# Stage 2 input dataset (priority=4+5) lives with the Crunchbase source data
STAGE2_INPUT_DATASET_PATH = DATA_DIR / "stage2_input_dataset_p4_p5.jsonl"

# Ensure directories exist
for dir_path in [OUTPUT_DIR, LOG_DIR, CHECKPOINT_DIR,
                 STAGE1_OUTPUT_DIR, STAGE1_TAVILY_DIR, STAGE1_GPT_DIR,
                 STAGE2_OUTPUT_DIR, STAGE2_TEST_RUNS_DIR, STAGE2_RUNS_DIR]:
    dir_path.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# CREDENTIAL LOADING
# ─────────────────────────────────────────────────────────────────────────────

def _load_credential(filename: str) -> str:
    """
    Load an API key from a credential file.
    
    Falls back to environment variable if file doesn't exist.
    
    Args:
        filename: Name of the credential file (e.g., 'tavily_api_key.txt')
    
    Returns:
        The API key string, or empty string if not found.
    """
    # Try loading from file first
    cred_path = CREDENTIALS_DIR / filename
    if cred_path.exists():
        content = cred_path.read_text().strip()
        # Skip comment lines and empty lines
        lines = [line.strip() for line in content.split('\n') 
                 if line.strip() and not line.strip().startswith('#')]
        if lines:
            return lines[0]  # Return first non-comment line
    
    # Fall back to environment variable
    env_var = filename.replace('_api_key.txt', '').upper() + '_API_KEY'
    return os.getenv(env_var, "")


# ─────────────────────────────────────────────────────────────────────────────
# API KEYS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class APIKeys:
    """
    API credentials loaded from credentials folder or environment variables.
    
    Priority:
    1. credentials/<service>_api_key.txt file
    2. Environment variable (e.g., TAVILY_API_KEY)
    """
    tavily: str = ""
    openai: str = ""
    perplexity: str = ""
    
    def __post_init__(self):
        """Load credentials if not already set."""
        if not self.tavily:
            object.__setattr__(self, 'tavily', _load_credential('tavily_api_key.txt'))
        if not self.openai:
            object.__setattr__(self, 'openai', _load_credential('openai_api_key.txt'))
        if not self.perplexity:
            object.__setattr__(self, 'perplexity', _load_credential('perplexity_api_key.txt'))

    def validate(self) -> list[str]:
        """Return list of missing API keys."""
        missing = []
        if not self.tavily:
            missing.append("tavily (credentials/tavily_api_key.txt)")
        if not self.openai:
            missing.append("openai (credentials/openai_api_key.txt)")
        if not self.perplexity:
            missing.append("perplexity (credentials/perplexity_api_key.txt)")
        return missing
    
    def status(self) -> dict[str, bool]:
        """Return status of each API key."""
        return {
            "tavily": bool(self.tavily),
            "openai": bool(self.openai),
            "perplexity": bool(self.perplexity),
        }


# ─────────────────────────────────────────────────────────────────────────────
# PROCESSING SETTINGS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class ProcessingConfig:
    """Settings for batch processing and rate limiting."""
    # Concurrency
    max_concurrent_requests: int = 10
    batch_size: int = 100

    # Timeouts (seconds)
    http_timeout: float = 10.0       # Website health checks
    tavily_timeout: float = 30.0     # Tavily API calls
    openai_timeout: float = 120.0    # GPT-5-nano needs headroom for reasoning tokens

    # Rate limiting (requests per minute) — set to 95% of actual limits for safety
    tavily_rpm: int = 950       # Actual limit: 1000 RPM
    openai_rpm: int = 28500     # Actual limit: 30,000 RPM (gpt-5-nano)
    perplexity_rpm: int = 60

    # Checkpointing
    checkpoint_every: int = 100  # Save progress every N companies

    # Retry policy
    max_retries: int = 3
    retry_delay_base: float = 1.0  # Exponential backoff base


# ─────────────────────────────────────────────────────────────────────────────
# DEFAULT INSTANCES
# ─────────────────────────────────────────────────────────────────────────────

PROCESSING = ProcessingConfig()
