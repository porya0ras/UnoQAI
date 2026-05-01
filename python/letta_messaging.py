from config import letta_client
from led_tools import execute_led_client_tool, LED_CLIENT_TOOLS
from agents import get_or_create_agents

main_agent_id = None
memory_manager_agent_id = None

def get_agents():
    global main_agent_id, memory_manager_agent_id
    if main_agent_id is None or memory_manager_agent_id is None:
        agents = get_or_create_agents()
        main_agent_id = agents["main_agent_id"]
        memory_manager_agent_id = agents["memory_manager_agent_id"]
    return main_agent_id, memory_manager_agent_id

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
            result, status = execute_led_client_tool(tool_name, tool_arguments)
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

def ask_letta(message, vision_context=None):
    main_agent_id_val, _ = get_agents()
    tool_context = (
        "If the user asks me to control my LEDs, matrix, face, light display, "
        "or little screen, use the available client-side LED tool. Do not give "
        "Arduino code for that request."
    )
    if vision_context:
        tool_context += f"\n\n[System Info: The camera currently sees the following: {vision_context}]"
        
    return send_message_to_agent(
        main_agent_id_val,
        f"{tool_context}\n\nUser message: {message}",
        client_tools=LED_CLIENT_TOOLS,
    )
