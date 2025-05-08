from xarxes2025.helpers import RTSPResponseBuilder
from loguru import logger

import threading
import random


class ClientSessionManager:
    """
    Manages RTSP session state for both client and server components.
    
    This class handles session creation, state transitions, and response generation
    according to the RTSP protocol. It maintains thread safety for concurrent operations.
    
    States:
        INIT: Initial state before setup
        READY: Ready for playback (after SETUP or PAUSE)
        PLAYING: Actively streaming content
    """
    
    # Define state constants
    INIT, READY, PLAYING = "INIT", "READY", "PLAYING"
    
    # Valid state transitions
    VALID_TRANSITIONS = {
        INIT: [READY],
        READY: [PLAYING, INIT],
        PLAYING: [READY, INIT]
    }

    def __init__(self, client_socket):
        """
        Initialize a new session manager.
        
        Args: client_socket (socket): Socket for RTSP communication
        """
        self.client_socket = client_socket
        self.session_id = "N/A"
        self.state = self.INIT
        self._lock = threading.Lock()
        self.creation_time = None

    def _start_session(self):
        """
        Start a new RTSP session with a unique ID.
        
        This method generates a new session ID and transitions to READY state.
        """
        with self._lock:
            # Generate a unique session ID
            self.session_id = f"XARXES_{random.randint(0, 9999999999):010d}"
            logger.info(f"[Session {self.session_id}] Session started")
            
            # Transition to READY state (after successful SETUP)
            self._transition_to_state(self.READY)

    def _transition_state(self, command):
        """
        Handle state transition based on the RTSP command.
        
        Args: command (str): RTSP command that triggers state transition
        """
        with self._lock:
            # Map commands to state transitions
            if command == "SETUP": self._transition_to_state(self.READY)
            elif command == "PLAY": self._transition_to_state(self.PLAYING)
            elif command == "PAUSE": self._transition_to_state(self.READY)
            elif command == "TEARDOWN":
                self._transition_to_state(self.INIT)
                logger.info(f"[Session {self.session_id}] Session ended")
            else: logger.error(f"[Session {self.session_id}] Invalid command: {command}")

    def _transition_to_state(self, new_state):
        """
        Perform the actual state transition with validation.
        
        Args: new_state (str): Target state to transition to
        
        Returns: bool: True if transition was successful, False otherwise
        """
        old_state = self.state
        
        # Validate transition
        if new_state not in self.VALID_TRANSITIONS.get(old_state, []) and old_state != new_state:
            logger.warning(
                f"[Session {self.session_id}] Invalid state transition: {old_state} -> {new_state}"
            )
            return False
            
        self.state = new_state
        logger.info(f"[Session {self.session_id}] Transition: {old_state} -> {new_state}")
        return True

    def _validate_session(self, headers, cseq):
        """
        Validate that the session ID in the request matches the current session.
        
        Args:
            headers (dict): RTSP headers from the request
            cseq (str): Command sequence number for the response
            
        Returns: bool: True if session is valid, False otherwise
        """
        with self._lock:
            if headers.get("Session") != self.session_id:
                self._send_response(cseq, 400, "Invalid Session")
                logger.warning(
                    f"[Session {self.session_id}] Invalid session ID in request: {headers.get('Session')}"
                )
                return False
            return True

    def _send_response(self, cseq, code=200, status="OK"):
        """
        Send an RTSP response to the client.
        
        Args:
            cseq (str): Command sequence number to include in response
            code (int): Status code (default: 200)
            status (str): Status message (default: "OK")
        """
        with self._lock:
            # Build and send the response
            response = RTSPResponseBuilder.build(cseq, code, status, self.session_id)
            try:
                self.client_socket.send(response.encode())
                logger.debug(f"[Session {self.session_id}] Sent response: {code} {status}")
            except (BrokenPipeError, OSError) as e:
                logger.error(f"[Session {self.session_id}] Failed to send response: {e}")
                
    def get_session_info(self):
        """
        Get current session information.
        
        Returns: dict: Session information including ID and state
        """
        with self._lock:
            return {
                "session_id": self.session_id,
                "state": self.state
            }