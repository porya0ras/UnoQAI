# UnoQ-AI: Letta-Powered Drone Vision Assistant

UnoQ-AI is an autonomous agentic system designed for the Arduino UNO Q, powered by the **Letta** agent framework. It integrates high-level reasoning, background memory management, and real-time vision monitoring with hardware-level control of an LED matrix.

## 🚀 Key Features

- **Multi-Agent Architecture**:
  - **Main Agent**: Handles direct user interaction and high-level requests.
  - **Memory Manager**: A background agent that monitors conversations and updates shared durable memory.
  - **Q-Eye (Vision Agent)**: Monitors camera status and analyzes detected objects, filtering for critical events.
- **Hardware Integration**: Direct control of the Arduino UNO Q's built-in LED matrix via `Arduino_RouterBridge`.
- **Custom LED Rendering**: Features a custom 3x5 font engine with support for static and scrolling text on the tiny display.
- **Intelligent Memory**: Uses shared Letta memory blocks to persist user preferences, profile facts, and project context across sessions.
- **Web-Based UI**: A real-time chat interface for interacting with the agents and viewing system status.
- **Client-Side Tooling**: Custom tools allowing the AI to "act" on the physical world (e.g., writing text to the LED matrix).

## 📁 Project Structure

```text
├── python/
│   ├── main.py            # Main application entry point
│   ├── config.py          # Configuration and environment variables
│   ├── toolHnadler.py     # Dispatches Letta tool calls to hardware/logic
│   ├── client_tools.json  # Definitions for Letta client-side tools
│   └── tools/             # Specific implementations (e.g., LED matrix rendering)
├── sketch/
│   ├── sketch.ino         # Arduino code for the UNO Q (Bridge/Matrix)
│   └── sketch.yaml        # Arduino project configuration
├── assets/                # Static assets for the WebUI
└── app.yaml               # Deployment/App configuration
```

## 🛠️ Getting Started

### 1. Prerequisites
- **Python 3.10+**
- **Arduino IDE** (or compatible CLI) with `Arduino_RouterBridge` and `Arduino_LED_Matrix` libraries.
- A running **Letta** server.

### 2. Hardware Setup
1. Open `sketch/sketch.ino` in your Arduino IDE.
2. Upload the sketch to your **Arduino UNO Q**.
3. Ensure the device is connected and accessible via the specified port.

### 3. Software Setup
1. Navigate to the `python` directory:
   ```bash
   cd python
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Configure your Letta server details in `python/config.py` or via environment variables:
   - `LETTA_BASE_URL`: URL of your Letta server (default: `http://192.168.1.80:8283`).
   - `LETTA_API_KEY`: Your Letta API key.

### 4. Running the App
Start the main Python application:
```bash
python python/main.py
```
This will launch the WebUI and initialize the agents.

## 🤖 Agents & Memory

The system utilizes a sophisticated memory architecture where the **Main Agent** and **Memory Manager** share a durable memory block. This allows the Memory Manager to "clean up" and "distill" information from conversations without interrupting the user experience.

- **Shared Memory**: Stores long-term facts like "User name is Porya" or "Project goal is Drone monitoring".
- **Idle Checks**: When the user is inactive, the Memory Manager performs self-reflection to ensure its internal state is consistent.

## 🔧 Tooling
The AI can perform actions through **Client-Side Tools**:
- `write_led_matrix_text(text)`: Displays text on the physical LED matrix.
- `clear_led_matrix()`: Clears the display.
- `get_camera_status()`: Checks vision system health.
- `get_latest_detections()`: Retrieves high-level object detection data.

---
*Built with ❤️ for the Letta and Arduino communities.*
