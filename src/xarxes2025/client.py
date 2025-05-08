from tkinter import Tk, Label, Button, W, E, N, S, messagebox
from xarxes2025.helpers import RTSPRequestBuilder, RTSPParser
from xarxes2025.session import ClientSessionManager
from PIL import Image, ImageTk
from loguru import logger

import threading
import socket
import sys
import io
import time


class Client:
    """
    RTSP client implementation that provides a GUI for controlling video streaming.
    
    This class handles the user interface for RTSP protocol operations (setup, play, pause, teardown)
    and manages the rendering of video frames received through RTP.
    """
    
    def __init__(self, filename, rtsp_port, host, rtp_port):
        """
        Initialize the RTSP client.
        
        Args:
            filename (str): The name of the video file to request
            rtsp_port (int): The port to connect to for RTSP signaling
            host (str): The hostname or IP address of the server
            rtp_port (int): The port to use for RTP data
        """
        self.RTSP_PORT = rtsp_port
        self.RTP_PORT = rtp_port
        self.HOST = host
        self.filename = filename
        self.cseq = 1  # RTSP sequence number
        self.running = False  # Flag for frame receiving thread
        self.tcp_socket = None  # For RTSP communication
        self.udp_socket = None  # For RTP data
        self.session = None  # Session manager
        self.last_frame_time = 0  # For frame rate control
        
        # Statistics tracking
        self.frames_received = 0
        self.start_time = None
        
        logger.info("Initializing RTP Client...")
        self.create_ui()

    def create_ui(self):
        """Create and configure the user interface."""
        self.root = Tk()
        self.root.wm_title("RTP Client")
        self.root.protocol("WM_DELETE_WINDOW", self.ui_close_window)

        # Control buttons
        Button(self.root, text="Setup", command=lambda: self._handle_state("SETUP"), width=20).grid(row=0, column=0, padx=2, pady=2)
        Button(self.root, text="Play", command=lambda: self._handle_state("PLAY"), width=20).grid(row=0, column=1, padx=2, pady=2)
        Button(self.root, text="Pause", command=lambda: self._handle_state("PAUSE"), width=20).grid(row=0, column=2, padx=2, pady=2)
        Button(self.root, text="Teardown", command=lambda: self._handle_state("TEARDOWN"), width=20).grid(row=0, column=3, padx=2, pady=2)
        
        # Status label
        self.status_label = Label(self.root, text="Not connected", bd=1, relief="sunken", anchor="w")
        self.status_label.grid(row=2, column=0, columnspan=4, sticky=W+E)
        
        # Video display area
        bg_color = self.root.cget("bg")
        placeholder = Image.new("RGB", (640, 380), color=bg_color)
        photo = ImageTk.PhotoImage(placeholder)
        self.movie = Label(self.root, image=photo, bg=bg_color)
        self.movie.image = photo
        self.movie.grid(row=1, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)
        
        # Make video area resizable
        self.root.grid_rowconfigure(1, weight=1)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)
        self.root.grid_columnconfigure(2, weight=1)
        self.root.grid_columnconfigure(3, weight=1)

    def ui_close_window(self):
        """Handle window close event by cleaning up resources."""
        logger.info("Closing RTP client window.")
        if self.session and self.session.state in [self.session.READY, self.session.PLAYING]:
            self._handle_state("TEARDOWN")
        self.running = False
        self._close_sockets()
        self.root.destroy()
        sys.exit(0)

    def _update_status(self, message):
        """Update the status bar with current status."""
        self.status_label.config(text=message)
        logger.info(message)

    def _connect_rtsp_server(self):
        """
        Establish connection to the RTSP server.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.connect((self.HOST, self.RTSP_PORT))
            self.session = ClientSessionManager(self.tcp_socket)
            self._update_status(f"Connected to RTSP server at {self.HOST}:{self.RTSP_PORT}")
            return True
        except Exception as e:
            logger.error(f"Couldn't connect to the server: {e}")
            messagebox.showerror("Connection Error", f"Cannot connect to server: {e}")
            self._close_sockets()
            return False

    def _setup_udp_socket(self):
        """
        Set up the UDP socket for RTP data reception.
        
        Returns:
            bool: True if setup successful, False otherwise
        """
        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Set buffer size to improve performance
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 1024*1024)
            self.udp_socket.settimeout(0.5)
            self.udp_socket.bind((self.HOST, self.RTP_PORT))
            logger.info(f"UDP socket bound to {self.HOST}:{self.RTP_PORT}")
            return True
        except Exception as e:
            logger.error(f"Couldn't set up UDP socket: {e}")
            messagebox.showerror("Socket Error", f"Cannot set up UDP socket: {e}")
            self._close_sockets()
            return False

    def _handle_state(self, command):
        """
        Main state machine handler for RTSP commands.
        
        Args:
            command (str): RTSP command to execute (SETUP, PLAY, PAUSE, TEARDOWN)
        """
        # Dispatch based on current state
        if not self.session: self._handle_no_session(command)
        elif self.session.state == self.session.INIT: self._handle_init_state(command)
        elif self.session.state == self.session.READY: self._handle_ready_state(command)
        elif self.session.state == self.session.PLAYING: self._handle_playing_state(command)
        else: messagebox.showerror("Invalid State", f"Unknown state: {self.session.state}")

    def _handle_no_session(self, command):
        """Handle commands when no session is established."""
        if command == "SETUP" and self._connect_rtsp_server():
            if self._send_rtsp_request(command):
                if not self._setup_udp_socket():
                    messagebox.showerror("Error", "Failed to set up UDP socket")
            else: messagebox.showerror("Error", "Failed to send SETUP request")
        else: messagebox.showwarning("Warning", "No connection to server, press Setup first.")

    def _handle_init_state(self, command):
        """Handle commands while in INIT state."""
        if command == "SETUP": self._send_rtsp_request(command)
        else: messagebox.showwarning("Warning", f"Cannot {command} in INIT state. Press Setup first.")

    def _handle_ready_state(self, command):
        """Handle commands while in READY state."""
        if command == "PLAY":
            if self._send_rtsp_request(command):
                self.running = True
                self.start_time = time.time()
                self.frames_received = 0
                threading.Thread(target=self._receive_frame_thread, daemon=True).start()
        elif command == "TEARDOWN": self._teardown(command)
        elif command == "PAUSE": messagebox.showinfo("Info", "Player is already paused")
        else: messagebox.showwarning("Warning", f"Invalid command {command} in READY state")

    def _handle_playing_state(self, command):
        """Handle commands while in PLAYING state."""
        if command == "PAUSE":
            self.running = False
            self._send_rtsp_request(command)
            self._report_statistics()
        elif command == "TEARDOWN":
            self.running = False
            self._teardown(command)
        elif command == "PLAY": messagebox.showinfo("Info", "Player is already playing")
        else: messagebox.showwarning("Warning", f"Invalid command {command} in PLAYING state")

    def _report_statistics(self):
        """Report playback statistics."""
        if self.start_time and self.frames_received > 0:
            elapsed = time.time() - self.start_time
            fps = self.frames_received / elapsed if elapsed > 0 else 0
            logger.info(f"Playback statistics: {self.frames_received} frames in {elapsed:.2f}s ({fps:.2f} fps)")
            self._update_status(f"Paused. Stats: {fps:.2f} fps")

    def _teardown(self, command):
        """Handle teardown command by closing the session."""
        self._send_rtsp_request(command)
        self._update_status("Session closed")
        self.session = None
        self._close_sockets()

    def _send_rtsp_request(self, command):
        """
        Send an RTSP request to the server.
        
        Args: command (str): RTSP command to send
            
        Returns: bool: True if successful, False otherwise
        """
        try:
            logger.info(f"Sending {command} request, CSeq {self.cseq}")
            request = RTSPRequestBuilder.build(
                command=command,
                filename=self.filename,
                cseq=self.cseq,
                session_id=getattr(self.session, "session_id", None),
                client_port=self.RTP_PORT
            )
            logger.debug(f"Request: {request}")
            self.tcp_socket.send(request.encode())
            raw_response = self.tcp_socket.recv(1024).decode().strip()
            logger.debug(f"Response: {raw_response}")
            parsed = RTSPParser.parse_response(raw_response)

            success = self._handle_response(parsed, command)
            self.cseq += 1
            return success
        except socket.error as e:
            logger.error(f"Socket error: {e}")
            messagebox.showerror("Socket Error", f"Communication error: {e}")
            self._close_sockets()
            return False

    def _handle_response(self, parsed, command):
        """
        Handle the RTSP response from the server.
        
        Args:
            parsed (dict): Parsed RTSP response
            command (str): RTSP command that was sent
            
        Returns: bool: True if successful, False otherwise
        """
        status = parsed["status_code"]
        session_header = parsed["headers"].get("Session")

        if status != "200":
            error_msg = f"{status} Error: {parsed['status_message']}"
            logger.error(error_msg)
            messagebox.showerror("RTSP Error", error_msg)
            return False

        if command == "SETUP" and session_header: self.session.session_id = session_header

        # Update session state
        self.session._transition_state(command)
        
        # Update status in UI
        status_msg = f"Session {self.session.session_id}: {self.session.state}"
        self._update_status(status_msg)
        
        logger.info(f"[Session {self.session.session_id}] {command} acknowledged. State: {self.session.state}")
        return True

    def _receive_frame_thread(self):
        """Background thread to receive and process RTP frames."""
        logger.info("Started receiving frames thread.")
        jitter_buffer = []  # Buffer to smooth out frame delivery
        max_buffer_size = 5  # Maximum frames to buffer
        
        while self.running:
            try:
                data, _ = self.udp_socket.recvfrom(65536)
                if data and len(data) > 12:  # Ensure we have the RTP header plus some data
                    # Extract sequence number from RTP header (bytes 2-3)
                    seq_num = (data[2] << 8) | data[3]
                    
                    # Add to jitter buffer
                    jitter_buffer.append((seq_num, data[12:]))
                    
                    # Process buffer when it reaches threshold or periodically
                    if len(jitter_buffer) >= max_buffer_size:
                        # Sort by sequence number
                        jitter_buffer.sort(key=lambda x: x[0])
                        
                        # Process oldest frame
                        _, frame_data = jitter_buffer.pop(0)
                        
                        # Schedule frame update in main thread
                        self.root.after(0, lambda d=frame_data: self._update_movie(d))
                        
                        # Update statistics
                        self.frames_received += 1
                        
                        # Adjust buffer size based on network conditions
                        if len(jitter_buffer) > max_buffer_size:
                            # If buffer growing too large, process more frames
                            while len(jitter_buffer) > max_buffer_size:
                                _, extra_frame = jitter_buffer.pop(0)
                                self.root.after(0, lambda d=extra_frame: self._update_movie(d))
                                self.frames_received += 1
                    
            except socket.timeout:
                # Process any buffered frames if we haven't received new ones
                if jitter_buffer and self.running:
                    jitter_buffer.sort(key=lambda x: x[0])
                    _, frame_data = jitter_buffer.pop(0)
                    self.root.after(0, lambda d=frame_data: self._update_movie(d))
                    self.frames_received += 1
                continue
            except Exception as e:
                if self.running:  # Only log errors if we're supposed to be running
                    logger.error(f"Frame receiving error: {e}")
        
        # Clear any remaining buffer
        jitter_buffer.clear()
        logger.info("Frame receiving thread terminated.")

    def _update_movie(self, data):
        """
        Update the movie display with a new frame.
        
        Args: data (bytes): JPEG frame data
        """
        try:
            # Throttle frame rate if necessary
            current_time = time.time()
            if current_time - self.last_frame_time < 0.03:  # Limit to ~30 fps
                # Skip frame if we're updating too quickly
                return
                
            self.last_frame_time = current_time
            
            # Create image from JPEG data
            image = Image.open(io.BytesIO(data))
            
            # Get original dimensions of the image
            img_width, img_height = image.size
            
            # Get target dimensions - use the original window dimensions
            # that were set during initialization rather than current dimensions
            # This prevents the runaway growth effect
            width = 640  # Default width from initialization
            height = 380  # Default height from initialization
            
            # Preserve aspect ratio
            ratio = min(width/img_width, height/img_height)
            new_size = (int(img_width*ratio), int(img_height*ratio))
            
            # Optimize image resizing
            if ratio != 1:
                image = image.resize(new_size, Image.LANCZOS)
            
            # Convert to PhotoImage and update display
            photo = ImageTk.PhotoImage(image)
            self.movie.configure(image=photo)
            self.movie.image = photo  # Keep reference to prevent garbage collection
            
        except Exception as e: logger.error(f"Error updating movie frame: {e}")

    def _close_sockets(self):
        """Close all network sockets."""
        if self.udp_socket:
            self.udp_socket.close()
            self.udp_socket = None
            logger.info("UDP socket closed.")
        if self.tcp_socket:
            self.tcp_socket.close()
            self.tcp_socket = None
            logger.info("TCP socket closed.")