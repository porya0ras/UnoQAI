

import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
AGENT_FILE = ROOT_DIR / "agent_state.json"
SKILLS_ROOT = Path(__file__).parent / ".agents" / "skills"

LETTA_BASE_URL = os.getenv("LETTA_BASE_URL", "http://192.168.1.80:8283")
LETTA_API_KEY = os.getenv("LETTA_API_KEY", "test")

MODEL = os.getenv("LETTA_MODEL", "openai/gpt-4o-mini")
EMBEDDING = os.getenv("LETTA_EMBEDDING", "openai/text-embedding-3-small")
SHARED_MEMORY_LIMIT = int(os.getenv("LETTA_SHARED_MEMORY_LIMIT", "5000"))
MEMORY_MANAGER_IDLE_SECONDS = int(os.getenv("MEMORY_MANAGER_IDLE_SECONDS", "90"))