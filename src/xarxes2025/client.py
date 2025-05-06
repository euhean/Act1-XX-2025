from tkinter import Tk, Label, Button, W, E, N, S, messagebox
from xarxes2025.helpers import RTSPRequestBuilder, RTSPParser
from PIL import Image, ImageTk
from loguru import logger

import threading
import socket
import sys
import io
import random


class Client:
    INIT, READY, PLAYING = "INIT", "READY", "PLAYING"

    def __init__(self, filename, rtsp_port, host, rtp_port):
        self.state = self.INIT
        self.RTSP_PORT = rtsp_port
        self.RTP_PORT = rtp_port
        self.HOST = host
        self.filename = filename
        self.session_id = None
        self.cseq = 1
        self.running = False
        self.tcp_socket = None
        self.udp_socket = None
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
        
        placeholder = Image.new("RGB", (640, 380), color="white")
        photo = ImageTk.PhotoImage(placeholder)

        self.movie = Label(self.root, image=photo)
        self.movie.image = photo
        self.movie.grid(row=1, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

    def ui_close_window(self):
        logger.info("Closing RTP client window.")
        self.running = False
        self._close_sockets()
        self.root.destroy()
        sys.exit(0)

    def _close_sockets(self):
        if self.udp_socket:
            self.udp_socket.close()
            logger.info("UDP socket closed.")
            self.udp_socket = None
        if self.tcp_socket:
            self.tcp_socket.close()
            logger.info("TCP socket closed.")
            self.tcp_socket = None

    def _connect_rtsp_server(self):
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.connect((self.HOST, self.RTSP_PORT))
            logger.info(f"Connected to RTSP server at {self.HOST}:{self.RTSP_PORT}")
        except Exception as e:
            logger.error(f"Couldn't connect to the server: {e}")
            self.running = False
            self._close_sockets()

    def _setup_udp_socket(self):
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.settimeout(0.5)
        self.udp_socket.bind((self.HOST, self.RTP_PORT))
        logger.info(f"UDP socket bound to {self.HOST}:{self.RTP_PORT}")

    def _receive_frame_thread(self):
        logger.info("Started receiving frames thread.")
        while self.running:
            try:
                data, _ = self.udp_socket.recvfrom(65536)
                if data:
                    self.root.after(0, self._update_movie, data[12:])
            except socket.timeout:
                continue
            except Exception as e:
                logger.error(f"Frame receiving error: {e}")
        logger.info("Frame receiving thread terminated.")

    def _handle_state(self, command):
        logger.info(f"[Session {self.session_id or 'N/A'}] Command: {command}")
        self._connect_rtsp_server()
        if self.state == self.INIT and command == "SETUP":
            if not self._connect_rtsp_server(): return
            self._send_rtsp_request_get_response(command)
            self._setup_udp_socket()
            self.state = self.READY
            self._messagebox_logger("Setup completed", command)
        elif self.state == self.READY:
            if command == "PLAY":
                self._send_rtsp_request_get_response(command)
                self.running = True
                self.state = self.PLAYING
                threading.Thread(target=self._receive_frame_thread, daemon=True).start()
                self._messagebox_logger("Playing", command)
            elif command == "TEARDOWN":
                self._send_rtsp_request_get_response(command)
                self.udp_socket.close()
                self.udp_socket = None
                self.state = self.INIT
                self._messagebox_logger("Teardown", command)
        elif self.state == self.PLAYING:
            self.running = False
            if command == "PAUSE":
                self._send_rtsp_request_get_response(command)
                self.state = self.READY
                self._messagebox_logger("Pausing", command)
            elif command == "TEARDOWN":
                self._send_rtsp_request_get_response(command)
                self.udp_socket.close()
                self.udp_socket = None
                self.state = self.INIT
                self._messagebox_logger("Teardown", command)
        else: messagebox.showerror("Invalid state transition")
        self.cseq += 1

    def _messagebox_logger(self, message, command):
        messagebox.showinfo(f"[Session: {self.session_id or 'N/A'}]", 
                            f"Cseq: {self.cseq}, Command {command} {message}")

    def _send_rtsp_request_get_response(self, command):
        try:
            request = RTSPRequestBuilder.build(
                command=command,
                filename=self.filename,
                cseq=self.cseq,
                session_id=self.session_id,
                client_port=self.RTP_PORT
            )
            self.tcp_socket.send(request.encode())
            raw_response = self.tcp_socket.recv(1024).decode().strip()
            parsed = RTSPParser.parse_response(raw_response)

            self._handle_errors(parsed["status_code"])
            self.session_id = parsed["headers"].get("Session", self.session_id)

        except socket.error as e:
            logger.error(f"Socket error: {e}")
            self.running = False
            self._close_sockets()

    def _handle_errors(self, status_code):
        if status_code != "200":
            match status_code:
                case "400": logger.error("400 Bad Request")
                case "404": logger.error("404 File Not Found")
                case "500": logger.error("500 Internal Server Error")
                case "501": logger.error("501 Not Implemented")
                case _: logger.error(f"Unknown error: {status_code}")
            return
        else: logger.info(f"[Session {self.session_id or 'N/A'}] 200 Command successful.")

    def _update_movie(self, data):
        photo = ImageTk.PhotoImage(Image.open(io.BytesIO(data)))
        self.movie.configure(image=photo)
        self.movie.image = photo