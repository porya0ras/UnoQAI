# Drone 03 — App & Block Flow Diagram

## High-Level Architecture

```mermaid
graph TB
    subgraph Browser["🌐 Browser (index.html)"]
        UI["WebUI Chat Interface"]
    end

    subgraph PythonApp["🐍 Python App (main.py)"]
        WebUI["WebUI Brick<br/>(arduino:web_ui)"]
        MainLogic["on_chat_message handler"]
        AskLetta["ask_letta()"]
        MemBG["update_memory_in_background()"]
        IdleCheck["run_memory_manager_idle_check()"]
        LEDLogic["led_matrix module"]
    end

    subgraph LettaServer["🧠 Letta Server"]
        MainAgent["Main Agent<br/>(uno-q-webui-agent)"]
        MemAgent["Memory Manager Agent<br/>(uno-q-memory-manager)"]
    end

    subgraph Arduino["🔌 Arduino UNO Q (sketch.ino)"]
        MCU["LED Matrix Controller"]
    end

    UI -- "Socket.IO: chat_message" --> WebUI
    WebUI --> MainLogic
    MainLogic --> AskLetta
    AskLetta -- "Letta API" --> MainAgent
    MainAgent -- "response" --> AskLetta
    AskLetta --> MainLogic
    MainLogic -- "Socket.IO: agent_response" --> UI

    MainLogic -- "background thread" --> MemBG
    MemBG -- "Letta API" --> MemAgent

    MainLogic -- "timer thread" --> IdleCheck
    IdleCheck -- "Letta API" --> MemAgent
    IdleCheck -- "Letta API" --> MainAgent

    MainLogic --> LEDLogic
    AskLetta -- "client tool callback" --> LEDLogic
    LEDLogic -- "Bridge.notify" --> MCU
```

---

## Memory Blocks & Agent Ownership

```mermaid
graph LR
    subgraph SharedBlock["🔗 Shared Block"]
        SUM["shared_user_memory<br/>(block-xxx)"]
    end

    subgraph MainBlocks["Main Agent Blocks"]
        P1["persona"]
        HP["human_profile"]
        AG["active_goals"]
        MP1["memory_policy"]
    end

    subgraph MemBlocks["Memory Manager Blocks"]
        P2["persona"]
        MP2["memory_policy"]
    end

    MainAgent["Main Agent"] --> P1
    MainAgent --> HP
    MainAgent --> AG
    MainAgent --> MP1
    MainAgent --> SUM

    MemAgent["Memory Manager"] --> P2
    MemAgent --> MP2
    MemAgent --> SUM
```

> [!IMPORTANT]
> Both agents share the **same** `shared_user_memory` block (by `block_id`). Writes from either agent are visible to the other.

---

## Chat Message Flow (step by step)

```mermaid
sequenceDiagram
    actor User
    participant UI as Browser WebUI
    participant WS as Socket.IO Server
    participant ML as Main Logic
    participant LA as Letta API
    participant MA as Main Agent
    participant LED as LED Matrix
    participant MM as Memory Manager

    User->>UI: Types message & clicks Send
    UI->>WS: emit("chat_message", {message})
    WS->>ML: on_chat_message(_sid, data)

    alt Direct LED command detected
        ML->>LED: led_matrix.write_text(text)
        LED-->>ML: rendered text
        ML->>WS: send("agent_response", answer)
    else Normal chat
        ML->>LA: agents.messages.create(main_agent_id, msg, client_tools)
        LA->>MA: Forward to Main Agent

        alt Agent requests LED client tool
            MA-->>LA: approval_request_message
            LA-->>ML: response with tool_call
            ML->>LED: execute_led_client_tool()
            LED-->>ML: result
            ML->>LA: agents.messages.create(approval)
            LA->>MA: Tool result
            MA-->>LA: Final response
        end

        LA-->>ML: assistant_message
        ML->>WS: send("agent_response", response)
    end

    WS->>UI: emit("agent_response", {response})
    UI->>User: Displays agent bubble

    Note over ML,MM: Background thread starts
    ML->>LA: agents.messages.create(memory_manager_id, prompt)
    LA->>MM: Review conversation turn
    MM-->>LA: Updates shared_user_memory if needed
```

---

## Idle Self-Check Flow

```mermaid
sequenceDiagram
    participant Timer as Idle Timer (90s)
    participant ML as Main Logic
    participant LA as Letta API
    participant MM as Memory Manager
    participant MA as Main Agent
    participant UI as Browser WebUI

    Timer->>ML: run_memory_manager_idle_check()

    ML->>LA: send prompt to Memory Manager
    LA->>MM: "Run internal self-check"
    MM-->>LA: Updates own role/memory if needed

    ML->>LA: send prompt to Main Agent
    LA->>MA: "Ask one warm question"
    MA-->>LA: question text

    ML->>UI: send("agent_response", question)
    Note over UI: Agent proactively asks user a question
```

---

## Startup / Agent Initialization Flow

```mermaid
flowchart TD
    Start["App.run()"] --> LoadState["load_agent_state()<br/>Read agent_state.json"]
    LoadState --> CheckBlock{"shared_memory_block_id<br/>exists & valid?"}

    CheckBlock -- Yes --> UseBlock["Use existing block"]
    CheckBlock -- No --> CreateBlock["create_shared_memory_block()<br/>via Letta API"]

    UseBlock --> CheckMain{"main_agent_id<br/>exists & valid?"}
    CreateBlock --> CheckMain

    CheckMain -- Yes --> AttachMain["attach_shared_memory()<br/>to main agent"]
    CheckMain -- No --> CreateMain["create_main_agent()<br/>with 4 memory blocks<br/>+ shared block"]

    AttachMain --> CheckMem{"memory_manager_agent_id<br/>exists & valid?"}
    CreateMain --> CheckMem

    CheckMem -- Yes --> AttachMem["attach_shared_memory()<br/>to memory manager"]
    CheckMem -- No --> CreateMem["create_memory_manager_agent()<br/>with 2 memory blocks<br/>+ shared block"]

    AttachMem --> Ready["✅ Both agents ready"]
    CreateMem --> Ready

    Ready --> RegisterUI["ui.on_message('chat_message')"]
    RegisterUI --> ScheduleIdle["schedule_idle_memory_manager_check()"]
    ScheduleIdle --> Running["🟢 App Running"]
```

---

## LED Control Path (Bridge)

```mermaid
flowchart LR
    subgraph Python
        LM["led_matrix.py"]
    end

    subgraph Bridge["Arduino Router Bridge"]
        BN["Bridge.notify()"]
    end

    subgraph MCU["Arduino UNO Q"]
        Draw["draw(frame) → matrix.loadFrame()"]
        Clear["clear_matrix() → matrix.clear()"]
    end

    LM -- "notify('draw', frame_words)" --> BN
    LM -- "notify('clear')" --> BN
    BN -- "RPC" --> Draw
    BN -- "RPC" --> Clear
```

---

## File → Component Mapping

| File | Role | Key Components |
|---|---|---|
| [app.yaml](file:///home/haleh/Documents/My%20Projects/letta-local/drone0-03/app.yaml) | App manifest | Declares `arduino:web_ui` brick |
| [main.py](file:///home/haleh/Documents/My%20Projects/letta-local/drone0-03/python/main.py) | Python entry point | Agent lifecycle, chat handler, memory manager, idle timer |
| [config.py](file:///home/haleh/Documents/My%20Projects/letta-local/drone0-03/python/config.py) | Configuration | Letta URL, API key, model, embedding, memory limits |
| [led_matrix.py](file:///home/haleh/Documents/My%20Projects/letta-local/drone0-03/python/led_matrix.py) | LED rendering | 3×5 font, text→pixels→frame, Bridge.notify |
| [index.html](file:///home/haleh/Documents/My%20Projects/letta-local/drone0-03/assets/index.html) | WebUI frontend | Socket.IO chat, message bubbles, status indicator |
| [sketch.ino](file:///home/haleh/Documents/My%20Projects/letta-local/drone0-03/sketch/sketch.ino) | Arduino firmware | Receives `draw`/`clear` via Bridge, drives LED matrix |
