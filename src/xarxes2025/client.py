from tkinter import Tk, Label, Button, W, E, N, S, messagebox
from xarxes2025.helpers import RTSPRequestBuilder, RTSPParser
from xarxes2025.session import ClientSessionManager
from PIL import Image, ImageTk
from loguru import logger

import threading
import socket
import sys
import io


class Client:
    def __init__(self, filename, rtsp_port, host, rtp_port):
        self.RTSP_PORT = rtsp_port
        self.RTP_PORT = rtp_port
        self.HOST = host
        self.filename = filename
        self.cseq = 1
        self.running = False
        self.tcp_socket = None
        self.udp_socket = None
        self.session = None
        logger.info("Initializing RTP Client...")
        self.create_ui()

    def create_ui(self):
        self.root = Tk()
        self.root.wm_title("RTP Client")
        self.root.protocol("WM_DELETE_WINDOW", self.ui_close_window)

        Button(self.root, text="Setup", command=lambda: self._handle_state("SETUP"), width=20).grid(row=0, column=0, padx=2, pady=2)
        Button(self.root, text="Play", command=lambda: self._handle_state("PLAY"), width=20).grid(row=0, column=1, padx=2, pady=2)
        Button(self.root, text="Pause", command=lambda: self._handle_state("PAUSE"), width=20).grid(row=0, column=2, padx=2, pady=2)
        Button(self.root, text="Teardown", command=lambda: self._handle_state("TEARDOWN"), width=20).grid(row=0, column=3, padx=2, pady=2)
        
        bg_color = self.root.cget("bg")
        placeholder = Image.new("RGB", (640, 380), color=bg_color)
        photo = ImageTk.PhotoImage(placeholder)
        self.movie = Label(self.root, image=photo, bg=bg_color)
        self.movie.image = photo
        self.movie.grid(row=1, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

    def ui_close_window(self):
        logger.info("Closing RTP client window.")
        if self.session and self.session.state in [self.session.READY, self.session.PLAYING]:
            self._handle_state("TEARDOWN")
        self.running = False
        self._close_sockets()
        self.root.destroy()
        sys.exit(0)

    def _connect_rtsp_server(self):
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.connect((self.HOST, self.RTSP_PORT))
            self.session = ClientSessionManager(self.tcp_socket)
            logger.info(f"Connected to RTSP server at {self.HOST}:{self.RTSP_PORT}")
            return True
        except Exception as e:
            logger.error(f"Couldn't connect to the server: {e}")
            self._close_sockets()
            return False

    def _setup_udp_socket(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.settimeout(0.5)
        self.udp_socket.bind((self.HOST, self.RTP_PORT))
        logger.info(f"UDP socket bound to {self.HOST}:{self.RTP_PORT}")

    def _handle_state(self, command):
        if not self.session:
            if command == "SETUP" and self._connect_rtsp_server():
                self._send_rtsp_request(command)
                self._setup_udp_socket()
                return
            logger.warning("Session pending.")
            return
        
        elif self.session.state == "READY":
            if command == "PLAY":
                self._send_rtsp_request(command)
                self.running = True
                threading.Thread(target=self._receive_frame_thread, daemon=True).start()
            elif command == "TEARDOWN":
                self._teardown(command)
        elif self.session.state == "PLAYING":
            self.running = False
            if command == "PAUSE":
                self._send_rtsp_request(command)
            elif command == "TEARDOWN":
                self._teardown(command)
        else: 
            if self.root.winfo_exists():
                messagebox.showerror("Invalid State", 
                                     f"Cannot {command} from {self.session.state}")
        self.cseq += 1

    def _teardown(self, command):
        self._send_rtsp_request(command)
        self.session = None
        self._close_sockets()

    def _send_rtsp_request(self, command):
        try:
            request = RTSPRequestBuilder.build(
                command=command,
                filename=self.filename,
                cseq=self.cseq,
                session_id=getattr(self.session, "session_id", None),
                client_port=self.RTP_PORT
            )
            self.tcp_socket.send(request.encode())
            raw_response = self.tcp_socket.recv(1024).decode().strip()
            parsed = RTSPParser.parse_response(raw_response)

            self._handle_response(parsed, command)
        except socket.error as e:
            logger.error(f"Socket error: {e}")
            self._close_sockets()

    def _handle_response(self, parsed, command):
        status = parsed["status_code"]
        session_header = parsed["headers"].get("Session")

        if status != "200":
            logger.error(f"{status} Error: {parsed['status_message']}")
            return

        if command == "SETUP" and session_header:
            self.session.session_id = session_header

        self.session._transition_state(command)
        logger.info(f"""[Session {self.session.session_id}] {command} acknowledged. 
                    State: {self.session.state}""")
        if self.root.winfo_exists():
            self.root.after(0, lambda: messagebox.showinfo(
                f"""[Session {self.session.session_id}] {command} acknowledged. 
                State: {self.session.state}"""))

    def _receive_frame_thread(self):
        logger.info("Started receiving frames thread.")
        while self.running:
            try:
                data, _ = self.udp_socket.recvfrom(65536)
                if data:
                    self.root.after(0, self._update_movie, data[12:])
            except socket.timeout: continue
            except Exception as e:
                logger.error(f"Frame receiving error: {e}")
        logger.info("Frame receiving thread terminated.")

    def _update_movie(self, data):
        photo = ImageTk.PhotoImage(Image.open(io.BytesIO(data)))
        self.movie.configure(image=photo)
        self.movie.image = photo

    def _close_sockets(self):
        if self.udp_socket:
            self.udp_socket.close()
            self.udp_socket = None
            logger.info("UDP socket closed.")
        if self.tcp_socket:
            self.tcp_socket.close()
            self.tcp_socket = None
            logger.info("TCP socket closed.")