"""Filings Research Copilot: cited answers from SEC filings and XBRL financial facts."""

import os

# Configure LiteLLM before anything imports it:
# - use the model price map bundled with the package instead of downloading it at import,
#   so startup and tests never depend on network access;
# - skip LiteLLM's own implicit `.env` loading; settings come only from `copilot.config`.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
os.environ.setdefault("LITELLM_MODE", "PRODUCTION")

__version__ = "0.1.0"
