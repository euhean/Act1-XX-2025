from xarxes2025.helpers import RTSPResponseBuilder
from loguru import logger

import threading
import random


class ClientSessionManager:
    INIT, READY, PLAYING = "INIT", "READY", "PLAYING"

    def __init__(self, client_socket):
        self.client_socket = client_socket
        self.session_id = "N/A"
        self.state = self.INIT
        self._lock = threading.Lock()

    def _start_session(self):
        with self._lock:
            self.session_id = f"XARXES_{random.randint(0, 9999999999):010d}"
            logger.info(f"[Session {self.session_id}] Session started")
            self._transition_state(self.READY)

    def _transition_state(self, command):
        with self._lock:
            old_state = self.state
            match command:
                case "SETUP": self.state = self.READY
                case "PLAY": self.state = self.PLAYING
                case "PAUSE": self.state = self.READY
                case "TEARDOWN":
                    self.state = self.INIT
                    logger.info(f"[Session {self.session_id}] Session ended")
                case _: logger.error(f"[Session {self.session_id}] Invalid command: {command}")
            
            logger.info(f"[Session {self.session_id}] Transition: {old_state} -> {self.state}")

    def _validate_session(self, headers, cseq):
        with self._lock:
            if headers.get("Session") != self.session_id:
                self._send_response(cseq, 400, "Invalid Session")
                return False
            return True

    def _send_response(self, cseq, code=200, status="OK"):
        with self._lock:
            response = RTSPResponseBuilder.build(cseq, code, status, self.session_id)
            try:
                self.client_socket.send(response.encode())
            except (BrokenPipeError, OSError) as e:
                logger.error(f"[Session {self.session_id}] Failed to send response: {e}")