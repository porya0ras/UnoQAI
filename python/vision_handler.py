import threading
import time
import socket
import numpy as np
import base64

# Patterned after VideoObjectDetection.py imports
from arduino.app_peripherals.camera import Camera
from arduino.app_utils.image.adjustments import compress_to_jpeg

class VisionHandler:
    """
    A class to handle both the vision processing loop and the camera streaming loop
    in separate threads, following the pattern used in VideoObjectDetection.
    """
    def __init__(self, agent_id_getter, send_message_func, host="127.0.0.1"):
        """
        Initialize the VisionHandler.
        
        Args:
            agent_id_getter (callable): A function that returns the vision_agent_id.
            send_message_func (callable): A function to send messages to the agent.
            host (str): The host address for TCP camera streaming.
        """
        self.agent_id_getter = agent_id_getter
        self.send_message_func = send_message_func
        self._host = host
        
        self._camera = Camera()
        self._is_running = threading.Event()
        
        self._vision_thread = None
        self._camera_thread = None

    def start(self):
        """Starts both the vision and camera processing loops in background threads."""
        if self._is_running.is_set():
            print("VisionHandler is already running.")
            return
            
        self._is_running.set()
        self._camera.start()
        
        # Start the Vision Processing Loop
        self._vision_thread = threading.Thread(target=self._vision_loop, daemon=True)
        self._vision_thread.start()
        
        # Start the Camera Streaming Loop
        self._camera_thread = threading.Thread(target=self._camera_loop, daemon=True)
        self._camera_thread.start()
        
        print("VisionHandler: Vision and Camera threads started.")

    def stop(self):
        """Stops all vision and camera processing loops."""
        self._is_running.clear()
        self._camera.stop()
        
        if self._vision_thread:
            self._vision_thread.join(timeout=2)
        if self._camera_thread:
            self._camera_thread.join(timeout=2)
            
        print("VisionHandler: All threads stopped.")

    def _vision_loop(self):
        """
        Background loop for high-level vision tasks and agent communication.
        """
        print("VisionHandler: Vision loop entered.")
        while self._is_running.is_set():
            try:
                # Simulate analysis interval
                time.sleep(10) 
                
                if not self._is_running.is_set():
                    break

                vision_agent_id = self.agent_id_getter()
                if not vision_agent_id:
                    continue

                event_message = "Vision System Update: Continuous monitoring active."
                print(f"[VisionHandler] Analyzing: {event_message}")

                response = self.send_message_func(vision_agent_id, event_message)
                print(f"[VisionHandler] Agent response: {response}")

            except Exception as e:
                print(f"VisionHandler Vision Loop Error: {e}")
                time.sleep(5)

    def _camera_loop(self):
        """
        Camera main loop.
        Captures images and forwards them over a TCP connection to the model runner,
        matching the logic in VideoObjectDetection.camera_loop.
        """
        print("VisionHandler: Camera loop entered.")
        while self._is_running.is_set():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as tcp_socket:
                    tcp_socket.connect((self._host, 5050))
                    print(f"VisionHandler: TCP connection established to {self._host}:5050")

                    # Priming frame logic if needed (optional for basic stream)
                    res = (self._camera.resolution[1], self._camera.resolution[0], 3)
                    frame = np.zeros(res, dtype=np.uint8)
                    jpeg_frame = compress_to_jpeg(frame)
                    if jpeg_frame is not None:
                        tcp_socket.sendall(jpeg_frame.tobytes())

                    while self._is_running.is_set():
                        try:
                            # Capture from camera
                            frame = self._camera.capture()
                            if frame is None:
                                time.sleep(0.01)
                                continue

                            # Compress and stream
                            jpeg_frame = compress_to_jpeg(frame)
                            if jpeg_frame is not None:
                                tcp_socket.sendall(jpeg_frame.tobytes())

                        except (BrokenPipeError, ConnectionResetError, OSError) as e:
                            print(f"VisionHandler: TCP connection lost: {e}. Retrying...")
                            break
                        except Exception as e:
                            print(f"VisionHandler Camera Capture Error: {e}")
                            time.sleep(1)

            except (ConnectionRefusedError, OSError) as e:
                if self._is_running.is_set():
                    print(f"VisionHandler: TCP connection failed: {e}. Retrying in 2s...")
                    time.sleep(2)
            except Exception as e:
                if self._is_running.is_set():
                    print(f"VisionHandler Camera Loop Unexpected Error: {e}")
                    time.sleep(2)
        
        print("VisionHandler: Camera loop exited.")
