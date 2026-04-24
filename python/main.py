import os
import json
import time
from pathlib import Path
from socketserver import ThreadingMixIn
from urllib.parse import urlparse
from wsgiref import simple_server
from letta_client import Letta

import socketio


ROOT_DIR = Path(__file__).resolve().parent.parent
ASSETS_DIR = ROOT_DIR / "assets"
AGENT_FILE = ROOT_DIR / "agent_state.json"

LETTA_BASE_URL = os.getenv("LETTA_BASE_URL", "http://192.168.1.80:8283")
LETTA_API_KEY = os.getenv("LETTA_API_KEY", "test")

MODEL = os.getenv("LETTA_MODEL", "openai/gpt-4o-mini")
EMBEDDING = os.getenv("LETTA_EMBEDDING", "openai/text-embedding-3-small")

WEBUI_URL = os.getenv("WEBUI_URL", "http://localhost:7000")
WEBUI_MODE = os.getenv("WEBUI_MODE", "auto").lower()
WEBUI_HOST = os.getenv("WEBUI_HOST", "0.0.0.0")
WEBUI_PORT = int(os.getenv("WEBUI_PORT", urlparse(WEBUI_URL).port or 7000))


class ThreadingWSGIServer(ThreadingMixIn, simple_server.WSGIServer):
    daemon_threads = True


letta_client = Letta(
    base_url=LETTA_BASE_URL,
    api_key=LETTA_API_KEY,
)


def load_agent_id():
    if AGENT_FILE.exists():
        data = json.loads(AGENT_FILE.read_text())
        return data.get("agent_id")
    return None


def save_agent_id(agent_id):
    AGENT_FILE.write_text(json.dumps({"agent_id": agent_id}, indent=2))


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
    agent_id = load_agent_id()

    if agent_id:
        try:
            letta_client.agents.retrieve(agent_id=agent_id)
            print(f"Using existing agent: {agent_id}")
            return agent_id
        except Exception:
            print("Existing agent_id invalid. Creating new agent...")

    return create_agent()


AGENT_ID = None


def extract_response(response):
    try:
        for msg in response.messages:
            if hasattr(msg, "message_type") and msg.message_type == "assistant_message":
                return msg.content

            if hasattr(msg, "content") and msg.content:
                return msg.content

        return str(response)

    except Exception:
        return str(response)


def ask_letta(message: str) -> str:
    global AGENT_ID

    if AGENT_ID is None:
        AGENT_ID = get_or_create_agent()

    response = letta_client.agents.messages.create(
        agent_id=AGENT_ID,
        messages=[
            {
                "role": "user",
                "content": message,
            }
        ],
    )

    return extract_response(response)


def get_agent_response_payload(data):
    message = data.get("message", "").strip()

    if not message:
        return {"error": "Message is empty"}, 400

    print(f"User: {message}")

    answer = ask_letta(message)

    print(f"Agent: {answer}")

    return {"response": answer}, 200


def handle_chat_message(data, emit):
    try:
        payload, status = get_agent_response_payload(data)

        if status == 200:
            emit("agent_response", payload)
        else:
            emit("agent_error", payload)

    except Exception as e:
        print(f"Error: {e}")
        emit("agent_error", {
            "error": str(e)
        })


def run_with_webui_brick(max_attempts=None):
    sio = socketio.Client()

    @sio.event
    def connect():
        print("Connected to WebUI Brick")

    @sio.event
    def disconnect():
        print("Disconnected from WebUI Brick")

    @sio.on("chat_message")
    def on_chat_message(data):
        handle_chat_message(data, sio.emit)

    attempts = 0

    while True:
        try:
            sio.connect(WEBUI_URL)
            break
        except Exception as e:
            attempts += 1
            print(f"Waiting for WebUI Brick... {e}")

            if max_attempts is not None and attempts >= max_attempts:
                return False

            time.sleep(2)

    sio.wait()
    return True


def run_local_webui():
    local_sio = socketio.Server(
        async_mode="threading",
        cors_allowed_origins="*",
    )

    @local_sio.event
    def connect(sid, environ):
        print(f"Browser connected: {sid}")

    @local_sio.event
    def disconnect(sid):
        print(f"Browser disconnected: {sid}")

    @local_sio.on("chat_message")
    def on_chat_message(sid, data):
        handle_chat_message(
            data,
            lambda event, payload: local_sio.emit(event, payload, to=sid),
        )

    socket_app = socketio.WSGIApp(
        local_sio,
        static_files={
            "/": str(ASSETS_DIR / "index.html"),
            "/index.html": str(ASSETS_DIR / "index.html"),
        },
    )

    def app(environ, start_response):
        if environ.get("PATH_INFO") == "/chat":
            if environ.get("REQUEST_METHOD") != "POST":
                start_response(
                    "405 Method Not Allowed",
                    [("Content-Type", "application/json")],
                )
                return [json.dumps({"error": "Method not allowed"}).encode()]

            try:
                length = int(environ.get("CONTENT_LENGTH") or 0)
                body = environ["wsgi.input"].read(length).decode("utf-8")
                data = json.loads(body or "{}")
                payload, status_code = get_agent_response_payload(data)
                status = "200 OK" if status_code == 200 else "400 Bad Request"
            except Exception as e:
                print(f"Error: {e}")
                payload = {"error": str(e)}
                status = "500 Internal Server Error"

            start_response(
                status,
                [("Content-Type", "application/json")],
            )
            return [json.dumps(payload).encode()]

        return socket_app(environ, start_response)

    httpd = simple_server.make_server(
        WEBUI_HOST,
        WEBUI_PORT,
        app,
        server_class=ThreadingWSGIServer,
    )
    print(f"Local WebUI running at http://localhost:{WEBUI_PORT}")
    httpd.serve_forever()


def main():
    print("Starting UNO Q WebUI Letta app...")
    print(f"Letta URL: {LETTA_BASE_URL}")
    print(f"WebUI URL: {WEBUI_URL}")
    print(f"WebUI mode: {WEBUI_MODE}")

    if WEBUI_MODE == "brick":
        run_with_webui_brick()
        return

    if WEBUI_MODE == "local":
        run_local_webui()
        return

    if run_with_webui_brick(max_attempts=1):
        return

    print("WebUI Brick is not available; starting local WebUI server instead.")
    run_local_webui()


if __name__ == "__main__":
    main()
