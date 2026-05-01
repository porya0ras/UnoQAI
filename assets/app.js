const socket = io();
const composer = document.getElementById("composer");
const input = document.getElementById("chatInput");
const messages = document.getElementById("messages");
const emptyState = document.getElementById("emptyState");
const sendButton = document.getElementById("sendButton");
const status = document.getElementById("status");
const statusText = document.getElementById("statusText");
const qrCodeContainer = document.getElementById('qrCodeContainer');
const qrSecretText = document.getElementById('qrSecretText');
const dynamicIframe = document.getElementById('dynamicIframe');
const qrPlaceholder = document.getElementById('qrPlaceholder');

const currentHostname = window.location.hostname;
const streamUrl = `http://${currentHostname}:4912/embed`;

let webcamState = {
    clientName: "",
    status: "disconnected",
    secret: null,
    protocol: "",
    ip: "",
    port: 0
};

function generateQRCode(secret, protocol, ip, port) {
    qrCodeContainer.innerHTML = '';
    new QRCode(qrCodeContainer, {
        text: `https://cloud.arduino.cc/installmobileapp?otp=${secret}&protocol=${protocol}&ip=${ip}&port=${port}`,
        width: 128,
        height: 128,
        colorDark: "#000000",
        colorLight: "#ffffff",
        correctLevel: QRCode.CorrectLevel.L,
    });
    qrSecretText.textContent = `Password: ${secret}`;
}

function updateCameraDisplay() {
    if (webcamState.status === "streaming" || webcamState.status === "connected") {
        qrPlaceholder.style.display = 'none';
        dynamicIframe.style.display = 'block';
        if (webcamState.status === "streaming" && !dynamicIframe.src) {
            const port = webcamState.port || 4912;
            dynamicIframe.src = `http://${currentHostname}:${port}/embed`;
        }
    } else {
        qrPlaceholder.style.display = 'flex';
        dynamicIframe.style.display = 'none';
        dynamicIframe.removeAttribute('src');
        if (webcamState.secret && typeof QRCode !== 'undefined') {
            generateQRCode(webcamState.secret, webcamState.protocol, webcamState.ip, webcamState.port);
        }
    }
}

function updateCameraStatus(state, data = {}) {
    webcamState.status = state;
    if (data.secret) webcamState.secret = data.secret;
    if (data.protocol) webcamState.protocol = data.protocol;
    if (data.ip) webcamState.ip = data.ip;
    if (data.port) webcamState.port = data.port;
    updateCameraDisplay();
}

function setStatus(text, state) {
    statusText.innerText = text;
    status.className = `status ${state || ""}`.trim();
}

function addMessage(role, text) {
    if (emptyState) {
        emptyState.remove();
    }

    const row = document.createElement("div");
    row.className = `message ${role}`;

    const bubble = document.createElement("div");
    bubble.className = "bubble";
    bubble.innerText = text;

    row.appendChild(bubble);
    messages.appendChild(row);
    messages.scrollTop = messages.scrollHeight;
}

function sendMessage() {
    const text = input.value.trim();

    if (!text || sendButton.disabled) {
        return;
    }

    addMessage("user", text);
    input.value = "";
    sendButton.disabled = true;
    sendButton.innerText = "Sending";

    socket.emit("chat_message", {
        message: text
    });
}

composer.addEventListener("submit", function (event) {
    event.preventDefault();
    sendMessage();
});

input.addEventListener("keydown", function (event) {
    if (event.key === "Enter" && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
});

socket.on("connect", function () {
    setStatus("Connected", "connected");
});

socket.on("disconnect", function () {
    setStatus("Disconnected", "error");
});

socket.on('welcome', (data) => updateCameraStatus(data.status || 'disconnected', data));
socket.on('connected', (data) => updateCameraStatus('connected', data));
socket.on('streaming', (data) => updateCameraStatus('streaming', data));
socket.on('paused', (data) => updateCameraStatus('paused', data));
socket.on('disconnected', (data) => updateCameraStatus('disconnected', data));

socket.on("agent_response", function (data) {
    addMessage("agent", data.response);
    sendButton.disabled = false;
    sendButton.innerText = "Send";
    input.focus();
});

socket.on("agent_error", function (data) {
    addMessage("error", data.error);
    sendButton.disabled = false;
    sendButton.innerText = "Send";
});

socket.on("connect_error", function (error) {
    setStatus("Connection error", "error");
    addMessage("error", "Socket error: " + error.message);
    sendButton.disabled = false;
    sendButton.innerText = "Send";
});
