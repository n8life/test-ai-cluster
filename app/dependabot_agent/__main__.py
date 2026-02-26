"""Allow running as: python -m app.dependabot_agent"""

import sys

from app.dependabot_agent.agent import run_agent

sys.exit(run_agent())
