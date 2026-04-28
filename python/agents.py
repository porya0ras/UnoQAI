import json
from config import AGENT_FILE, letta_client, SHARED_MEMORY_LIMIT, MODEL, EMBEDDING

def load_agent_state():
    if AGENT_FILE.exists():
        state = json.loads(AGENT_FILE.read_text())
        if "agent_id" in state and "main_agent_id" not in state:
            state["main_agent_id"] = state["agent_id"]
        return state
    return {
        "main_agent_id": "agent-5d51ca51-0748-4ca2-8b60-e9fddd63ed1f",
        "memory_manager_agent_id": "agent-710e803d-6b99-4763-966f-1f1e336227a0",
        "shared_memory_block_id": "block-4e2e1613-2336-448b-b974-913840a3f540"
    }

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
                    "Answer clearly and briefly. Ask one short question if needed. "
                    "You can control your LED matrix with client-side tools when "
                    "the user asks you to show text or clear your lights."
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
        tools=["conversation_search"],
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
        tools=["conversation_search"],
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
