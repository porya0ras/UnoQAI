from arduino.app_bricks.web_ui import WebUI

ui = WebUI()

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
