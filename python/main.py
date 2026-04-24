import json
import os
from pathlib import Path

from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App
from letta_client import Letta


ROOT_DIR = Path(__file__).resolve().parent.parent
AGENT_FILE = ROOT_DIR / "agent_state.json"

LETTA_BASE_URL = os.getenv("LETTA_BASE_URL", "http://192.168.1.80:8283")
LETTA_API_KEY = os.getenv("LETTA_API_KEY", "test")

MODEL = os.getenv("LETTA_MODEL", "openai/gpt-4o-mini")
EMBEDDING = os.getenv("LETTA_EMBEDDING", "openai/text-embedding-3-small")

ui = WebUI()
letta_client = Letta(
    base_url=LETTA_BASE_URL,
    api_key=LETTA_API_KEY,
)
agent_id = None


def load_agent_id():
    if AGENT_FILE.exists():
        data = json.loads(AGENT_FILE.read_text())
        return data.get("agent_id")
    return None


def save_agent_id(created_agent_id):
    AGENT_FILE.write_text(json.dumps({"agent_id": created_agent_id}, indent=2))


def create_agent():
    agent = letta_client.agents.create(
        name="uno-q-webui-agent",
        model=MODEL,
        embedding=EMBEDDING,
        memory_blocks=[
            {
                "label": "persona",
                "value": (
                    "You are a small personal AI assistant running on Arduino UNO Q. "
                    "Answer clearly and briefly. Ask one short question if needed."
                ),
            },
            {
                "label": "human_profile",
                "value": "The user is building a personal AI assistant with Letta and UNO Q.",
            },
            {
                "label": "active_goals",
                "value": "Current goal: test Web UI chat box connected to Letta.",
            },
            {
                "label": "memory_policy",
                "value": (
                    "Remember only useful durable information. "
                    "Do not store secrets unless the user explicitly asks."
                ),
            },
        ],
        tools=[
            "conversation_search",
        ],
    )

    save_agent_id(agent.id)
    print(f"Created agent: {agent.id}")
    return agent.id


def get_or_create_agent():
    saved_agent_id = load_agent_id()

    if saved_agent_id:
        try:
            letta_client.agents.retrieve(agent_id=saved_agent_id)
            print(f"Using existing agent: {saved_agent_id}")
            return saved_agent_id
        except Exception:
            print("Existing agent_id invalid. Creating new agent...")

    return create_agent()


def extract_response(response):
    try:
        for msg in response.messages:
            if getattr(msg, "message_type", None) == "assistant_message":
                return msg.content

            content = getattr(msg, "content", None)
            if content:
                return content

        return str(response)

    except Exception:
        return str(response)


def ask_letta(message):
    global agent_id

    if agent_id is None:
        agent_id = get_or_create_agent()

    response = letta_client.agents.messages.create(
        agent_id=agent_id,
        messages=[
            {
                "role": "user",
                "content": message,
            }
        ],
    )

    return extract_response(response)


def send_agent_error(error):
    ui.send_message(
        "agent_error",
        message={
            "error": str(error),
        },
    )


def send_agent_response(response):
    ui.send_message(
        "agent_response",
        message={
            "response": response,
        },
    )


def on_chat_message(_sid, data):
    try:
        message = data.get("message", "").strip()

        if not message:
            send_agent_error("Message is empty")
            return

        print(f"User: {message}")

        answer = ask_letta(message)

        print(f"Agent: {answer}")
        send_agent_response(answer)

    except Exception as e:
        print(f"Error: {e}")
        send_agent_error(e)


print("Starting UNO Q WebUI Letta app...")
print(f"Letta URL: {LETTA_BASE_URL}")

ui.on_message("chat_message", on_chat_message)

App.run()
