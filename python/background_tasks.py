import threading
from config import MEMORY_MANAGER_IDLE_SECONDS
from letta_messaging import send_message_to_agent, get_agents
from ui_instance import send_agent_response

idle_timer = None
idle_timer_lock = threading.Lock()

def update_memory_in_background(user_message, assistant_response):
    _, memory_manager_agent_id = get_agents()
    prompt = (
        "Review this conversation turn and update shared_user_memory if useful.\n\n"
        f"User message:\n{user_message}\n\n"
        f"Main agent response:\n{assistant_response}\n\n"
        "If nothing durable should be saved, make no memory changes."
    )
    send_message_to_agent(memory_manager_agent_id, prompt)

def run_memory_manager_idle_check():
    main_agent_id, memory_manager_agent_id = get_agents()
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
