"""Stage 3 citation verification: fetch page text, then OpenAI logprob judge.

Production package. Evals may import it later; implementation does not live under evals/.
"""

from citation_verification.runner import verify_finding, verify_findings
from citation_verification.types import VerdictResult, VerifyResult

__all__ = [
    "VerdictResult",
    "VerifyResult",
    "verify_finding",
    "verify_findings",
]
