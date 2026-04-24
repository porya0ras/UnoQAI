import json
import os
import threading
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
SHARED_MEMORY_LIMIT = int(os.getenv("LETTA_SHARED_MEMORY_LIMIT", "5000"))
MEMORY_MANAGER_IDLE_SECONDS = int(os.getenv("MEMORY_MANAGER_IDLE_SECONDS", "90"))

ui = WebUI()
letta_client = Letta(
    base_url=LETTA_BASE_URL,
    api_key=LETTA_API_KEY,
)
main_agent_id = None
memory_manager_agent_id = None
idle_timer = None
idle_timer_lock = threading.Lock()


def load_agent_state():
    if AGENT_FILE.exists():
        state = json.loads(AGENT_FILE.read_text())

        if "agent_id" in state and "main_agent_id" not in state:
            state["main_agent_id"] = state["agent_id"]

        return state

    return {}


def save_agent_state(state):
    AGENT_FILE.write_text(json.dumps(state, indent=2))


def create_shared_memory_block():
    block = letta_client.blocks.create(
        label="shared_user_memory",
        description=(
            "Shared durable memory for the main chat agent and the background "
            "memory manager. Store stable user preferences, profile facts, "
            "project context, and long-lived goals. Avoid secrets and short-term "
            "conversation details."
        ),
        value=(
            "No durable user memories have been saved yet. Keep this block "
            "concise, factual, and useful for future conversations."
        ),
        limit=SHARED_MEMORY_LIMIT,
    )

    print(f"Created shared memory block: {block.id}")
    return block.id


def get_or_create_shared_memory_block(state):
    block_id = state.get("shared_memory_block_id")

    if block_id:
        try:
            letta_client.blocks.retrieve(block_id)
            return block_id
        except Exception:
            print("Existing shared_memory_block_id invalid. Creating new block...")

    block_id = create_shared_memory_block()
    state["shared_memory_block_id"] = block_id
    save_agent_state(state)
    return block_id


def attach_shared_memory(agent_id, block_id):
    try:
        letta_client.agents.blocks.attach(
            agent_id=agent_id,
            block_id=block_id,
        )
        print(f"Attached shared memory block to agent: {agent_id}")
    except Exception as e:
        message = str(e).lower()
        if "already" not in message and "duplicate" not in message:
            raise


def create_main_agent(shared_memory_block_id):
    agent = letta_client.agents.create(
        name="uno-q-webui-agent",
        model=MODEL,
        embedding=EMBEDDING,
        block_ids=[shared_memory_block_id],
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
                "value": (
                    "Use shared_user_memory for durable user facts and project "
                    "context. Ask concise follow-up questions when needed."
                ),
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

    print(f"Created main agent: {agent.id}")
    return agent.id


def create_memory_manager_agent(shared_memory_block_id):
    agent = letta_client.agents.create(
        name="uno-q-memory-manager",
        model=MODEL,
        embedding=EMBEDDING,
        block_ids=[shared_memory_block_id],
        memory_blocks=[
            {
                "label": "persona",
                "value": (
                    "You are a background memory manager. Your job is to inspect "
                    "conversation turns and maintain shared_user_memory. Save only "
                    "durable, useful information. Ignore one-off messages, secrets, "
                    "and temporary wording. Keep memory concise and correct."
                ),
            },
            {
                "label": "memory_policy",
                "value": (
                    "Update shared_user_memory only when the new information is "
                    "likely to help future conversations. Prefer compact bullet "
                    "points. Do not answer the user directly."
                ),
            },
        ],
        tools=[
            "conversation_search",
        ],
    )

    print(f"Created memory manager agent: {agent.id}")
    return agent.id


def get_or_create_main_agent(state, shared_memory_block_id):
    saved_agent_id = state.get("main_agent_id")

    if saved_agent_id:
        try:
            letta_client.agents.retrieve(agent_id=saved_agent_id)
            attach_shared_memory(saved_agent_id, shared_memory_block_id)
            print(f"Using existing agent: {saved_agent_id}")
            return saved_agent_id
        except Exception:
            print("Existing main_agent_id invalid. Creating new agent...")

    created_agent_id = create_main_agent(shared_memory_block_id)
    state["main_agent_id"] = created_agent_id
    save_agent_state(state)
    return created_agent_id


def get_or_create_memory_manager_agent(state, shared_memory_block_id):
    saved_agent_id = state.get("memory_manager_agent_id")

    if saved_agent_id:
        try:
            letta_client.agents.retrieve(agent_id=saved_agent_id)
            attach_shared_memory(saved_agent_id, shared_memory_block_id)
            print(f"Using existing memory manager agent: {saved_agent_id}")
            return saved_agent_id
        except Exception:
            print("Existing memory_manager_agent_id invalid. Creating new agent...")

    created_agent_id = create_memory_manager_agent(shared_memory_block_id)
    state["memory_manager_agent_id"] = created_agent_id
    save_agent_state(state)
    return created_agent_id


def get_or_create_agents():
    state = load_agent_state()
    shared_memory_block_id = get_or_create_shared_memory_block(state)

    return {
        "main_agent_id": get_or_create_main_agent(state, shared_memory_block_id),
        "memory_manager_agent_id": get_or_create_memory_manager_agent(
            state,
            shared_memory_block_id,
        ),
        "shared_memory_block_id": shared_memory_block_id,
    }


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
    global main_agent_id, memory_manager_agent_id

    if main_agent_id is None or memory_manager_agent_id is None:
        agents = get_or_create_agents()
        main_agent_id = agents["main_agent_id"]
        memory_manager_agent_id = agents["memory_manager_agent_id"]

    response = letta_client.agents.messages.create(
        agent_id=main_agent_id,
        messages=[
            {
                "role": "user",
                "content": message,
            }
        ],
    )

    return extract_response(response)


def update_memory_in_background(user_message, assistant_response):
    global memory_manager_agent_id

    if memory_manager_agent_id is None:
        agents = get_or_create_agents()
        memory_manager_agent_id = agents["memory_manager_agent_id"]

    prompt = (
        "Review this conversation turn and update shared_user_memory if useful.\n\n"
        f"User message:\n{user_message}\n\n"
        f"Main agent response:\n{assistant_response}\n\n"
        "If nothing durable should be saved, make no memory changes."
    )

    letta_client.agents.messages.create(
        agent_id=memory_manager_agent_id,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )


def run_memory_manager_idle_check():
    global memory_manager_agent_id

    if memory_manager_agent_id is None:
        agents = get_or_create_agents()
        memory_manager_agent_id = agents["memory_manager_agent_id"]

    prompt = (
        "The main chat agent is currently idle. Run an internal self-check as "
        "the background memory manager.\n\n"
        "Ask yourself:\n"
        "- What is my name?\n"
        "- What is my purpose?\n"
        "- Which shared memory block do I maintain?\n"
        "- Is there anything missing or inconsistent in my memory manager role?\n\n"
        "If your own role memory or shared_user_memory needs a small correction, "
        "update it. If everything is already clear, make no memory changes. "
        "Do not answer the user directly."
    )

    letta_client.agents.messages.create(
        agent_id=memory_manager_agent_id,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
    )
    print("Memory manager idle self-check completed.")


def schedule_memory_update(user_message, assistant_response):
    def run():
        try:
            update_memory_in_background(user_message, assistant_response)
        except Exception as e:
            print(f"Memory manager error: {e}")

    threading.Thread(target=run, daemon=True).start()


def schedule_idle_memory_manager_check():
    global idle_timer

    if MEMORY_MANAGER_IDLE_SECONDS <= 0:
        return

    def run():
        try:
            run_memory_manager_idle_check()
        except Exception as e:
            print(f"Memory manager idle check error: {e}")

    with idle_timer_lock:
        if idle_timer is not None:
            idle_timer.cancel()

        idle_timer = threading.Timer(MEMORY_MANAGER_IDLE_SECONDS, run)
        idle_timer.daemon = True
        idle_timer.start()


def cancel_idle_memory_manager_check():
    global idle_timer

    with idle_timer_lock:
        if idle_timer is not None:
            idle_timer.cancel()
            idle_timer = None


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

        cancel_idle_memory_manager_check()

        print(f"User: {message}")

        answer = ask_letta(message)

        print(f"Agent: {answer}")
        send_agent_response(answer)
        schedule_memory_update(message, answer)
        schedule_idle_memory_manager_check()

    except Exception as e:
        print(f"Error: {e}")
        send_agent_error(e)
        schedule_idle_memory_manager_check()


print("Starting UNO Q WebUI Letta app...")
print(f"Letta URL: {LETTA_BASE_URL}")
print(f"Memory manager idle check: {MEMORY_MANAGER_IDLE_SECONDS}s")

ui.on_message("chat_message", on_chat_message)
schedule_idle_memory_manager_check()

App.run()
