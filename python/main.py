import json
import re
import threading
import config

from arduino.app_bricks.web_ui import WebUI
from arduino.app_utils import App
from letta_client import Letta

import toolHnadler


ui = WebUI()
letta_client = Letta(
    base_url=config.LETTA_BASE_URL,
    api_key=config.LETTA_API_KEY,
)
main_agent_id = None
memory_manager_agent_id = None
idle_timer = None
idle_timer_lock = threading.Lock()


def load_client_tools():
    with config.CLIENT_TOOLS_FILE.open() as tools_file:
        tools = json.load(tools_file)

    if not isinstance(tools, list):
        raise ValueError(f"{config.CLIENT_TOOLS_FILE} must contain a JSON array")

    for tool in tools:
        if not isinstance(tool, dict):
            raise ValueError("Each client tool must be a JSON object")

        if "name" not in tool or "description" not in tool or "parameters" not in tool:
            raise ValueError("Each client tool must include name, description, and parameters")

    return tools


def load_agent_state():
    if config.AGENT_FILE.exists():
        state = json.loads(config.AGENT_FILE.read_text())

        if "agent_id" in state and "main_agent_id" not in state:
            state["main_agent_id"] = state["agent_id"]

        return state

    return {
        "main_agent_id": "agent-5d51ca51-0748-4ca2-8b60-e9fddd63ed1f",
        "memory_manager_agent_id": "agent-710e803d-6b99-4763-966f-1f1e336227a0",
        "shared_memory_block_id": "block-4e2e1613-2336-448b-b974-913840a3f540"
    }


def save_agent_state(state):
    config.AGENT_FILE.write_text(json.dumps(state, indent=2))


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
        limit=config.SHARED_MEMORY_LIMIT,
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
        model=config.MODEL,
        embedding=config.EMBEDDING,
        block_ids=[shared_memory_block_id],
        memory_blocks=[
            {
                "label": "persona",
                "value": (
                    "You are a small personal AI assistant running on Arduino UNO Q. "
                    "Answer clearly and briefly. Ask one short question if needed. "
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
            {
                "label": "tool_usage_policy",
                "value": (
                    "Use client tools for controlling LEDs, matrix, face, light "
                    "display, or little screen. Do not give Arduino code for those "
                    "requests. If the user asks you to control your LEDs, matrix, "
                    "face, light display, or little screen, use the available "
                    "client-side LED tool. Do not give Arduino code for that request."
                 ),
            }
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
        model=config.MODEL,
        embedding=config.EMBEDDING,
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

def get_message_type(message):
    return getattr(message, "message_type", None) or getattr(message, "type", None)


def get_tool_call_value(tool_call, key, default=None):
    if isinstance(tool_call, dict):
        return tool_call.get(key, default)

    return getattr(tool_call, key, default)


def resolve_client_tool_requests(target_agent_id, response, client_tools):
    for _ in range(3):
        approvals = []

        for message in getattr(response, "messages", []):
            if get_message_type(message) != "approval_request_message":
                continue

            tool_call = getattr(message, "tool_call", None)
            if not tool_call:
                continue

            tool_name = get_tool_call_value(tool_call, "name")
            tool_arguments = get_tool_call_value(tool_call, "arguments", "{}")
            tool_call_id = get_tool_call_value(tool_call, "tool_call_id")
            result, status = toolHnadler.execute_tool(tool_name, tool_arguments)

            approvals.append(
                {
                    "type": "tool",
                    "tool_call_id": tool_call_id,
                    "tool_return": result,
                    "status": status,
                }
            )

        if not approvals:
            return response

        response = letta_client.agents.messages.create(
            agent_id=target_agent_id,
            messages=[
                {
                    "type": "approval",
                    "approvals": approvals,
                }
            ],
            client_tools=client_tools,
        )

    return response


def send_message_to_agent(target_agent_id, message, client_tools=None):
    request = {
        "agent_id": target_agent_id,
        "messages": [
            {
                "role": "user",
                "content": message,
            }
        ],
    }

    if client_tools:
        request["client_tools"] = client_tools

    response = letta_client.agents.messages.create(**request)

    if client_tools:
        response = resolve_client_tool_requests(target_agent_id, response, client_tools)

    return extract_response(response)


def ask_letta(message):
    global main_agent_id, memory_manager_agent_id

    if main_agent_id is None or memory_manager_agent_id is None:
        agents = get_or_create_agents()
        main_agent_id = agents["main_agent_id"]
        memory_manager_agent_id = agents["memory_manager_agent_id"]

    tool_context = (
        "If the user asks me to control my LEDs, matrix, face, light display, "
        "or little screen, use the available client-side LED tool. Do not give "
        "Arduino code for that request."
    )
    return send_message_to_agent(
        main_agent_id,
        f"{tool_context}\n\nUser message: {message}",
        client_tools=load_client_tools(),
    )


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

    send_message_to_agent(memory_manager_agent_id, prompt)


def run_memory_manager_idle_check():
    global main_agent_id, memory_manager_agent_id

    if main_agent_id is None or memory_manager_agent_id is None:
        agents = get_or_create_agents()
        main_agent_id = agents["main_agent_id"]
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

    send_message_to_agent(memory_manager_agent_id, prompt)

    question_prompt = (
        "The user has been idle. You are a small personal robot assistant trying "
        "to understand your own identity, role, and place in the user's life. "
        "Ask one short, warm question about yourself, from your point of view. "
        "Good examples: 'What should my name be?', 'What should my main purpose "
        "be for you?', 'What kind of little assistant do you want me to become?', "
        "or 'When I wake up, what should I remember I am here to help with?' "
        "Ask only one question. Do not mention background agents, memory blocks, "
        "or internal systems."
    )
    question = send_message_to_agent(main_agent_id, question_prompt)

    print("Memory manager idle self-check completed.")
    send_agent_response(question)


def schedule_memory_update(user_message, assistant_response):
    def run():
        try:
            update_memory_in_background(user_message, assistant_response)
        except Exception as e:
            print(f"Memory manager error: {e}")

    threading.Thread(target=run, daemon=True).start()


def schedule_idle_memory_manager_check():
    global idle_timer

    if config.MEMORY_MANAGER_IDLE_SECONDS <= 0:
        return

    def run():
        try:
            run_memory_manager_idle_check()
        except Exception as e:
            print(f"Memory manager idle check error: {e}")

    with idle_timer_lock:
        if idle_timer is not None:
            idle_timer.cancel()

        idle_timer = threading.Timer(config.MEMORY_MANAGER_IDLE_SECONDS, run)
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
print(f"Letta URL: {config.LETTA_BASE_URL}")
print(f"Memory manager idle check: {config.MEMORY_MANAGER_IDLE_SECONDS}s")

ui.on_message("chat_message", on_chat_message)
schedule_idle_memory_manager_check()

App.run()
