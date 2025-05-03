from tkinter import Tk, Label, Button, W, E, N, S, messagebox
from xarxes2025.helpers import RTSPRequestBuilder
from PIL import Image, ImageTk
from loguru import logger

import threading
import socket
import sys
import io
import random


class Client:
    INIT, READY, PLAYING = "INIT", "READY", "PLAYING"

    def __init__(self, server_port, filename):
        self.state = self.INIT
        self.RTSP_PORT = server_port or 25000
        self.RTP_PORT = random.randint(25001, 30000)
        self.HOST = "127.0.0.1"
        self.filename = filename
        self.session_id = None
        self.cseq = 1
        self.running = False
        self.socket = None
        self.tcp_socket = None
        self.create_ui()

    def create_ui(self):
        self.root = Tk()
        self.root.wm_title("RTP Client")
        self.root.protocol("WM_DELETE_WINDOW", self.ui_close_window)
        Button(self.root, text="Setup", command=lambda: self._handle_state("SETUP"), width=20).grid(row=0, column=0, padx=2, pady=2)
        Button(self.root, text="Play", command=lambda: self._handle_state("PLAY"), width=20).grid(row=0, column=1, padx=2, pady=2)
        Button(self.root, text="Pause", command=lambda: self._handle_state("PAUSE"), width=20).grid(row=0, column=2, padx=2, pady=2)
        Button(self.root, text="Teardown", command=lambda: self._handle_state("TEARDOWN"), width=20).grid(row=0, column=3, padx=2, pady=2)
        self.movie = Label(self.root, height=29)
        self.movie.grid(row=1, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

    def ui_close_window(self):
        self.running = False
        self._close_sockets()
        self.root.destroy()
        sys.exit(0)

    def _close_sockets(self):
        if self.socket:
            self.socket.close()
            self.socket = None
        if self.tcp_socket:
            self.tcp_socket.close()
            self.tcp_socket = None

    def _connect_rtsp_server(self):
        try:
            self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.tcp_socket.connect((self.HOST, self.RTSP_PORT))
            return True
        except Exception as e:
            logger.error(f"Couldn't connect to the server: {e}")
            return False

    def _setup_udp_socket(self):
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.settimeout(0.5)
        self.socket.bind((self.HOST, self.RTP_PORT))

    def receive_frame_thread(self):
        while self.running:
            try:
                data, _ = self.socket.recvfrom(65536)
                if data:
                    self.root.after(0, self.update_movie, data[12:])
            except socket.timeout:
                continue

    def _handle_state(self, command):
        if self.state == self.INIT and command == "SETUP":
            self._send_rtsp_command(command)
            self.state = self.READY
        elif self.state == self.READY:
            if command == "PLAY":
                self._send_rtsp_command(command)
                self.state = self.PLAYING
            elif command == "TEARDOWN":
                self._send_rtsp_command(command)
                self.state = self.INIT
        elif self.state == self.PLAYING:
            if command == "PAUSE":
                self._send_rtsp_command(command)
                self.state = self.READY
            elif command == "TEARDOWN":
                self._send_rtsp_command(command)
                self.state = self.INIT
        else: logger.error("Invalid state transition")

    def _send_rtsp_command(self, command):
        try:
            if command == "SETUP" and not self._connect_rtsp_server():
                return

            request = RTSPRequestBuilder.build(
                command=command,
                filename=self.filename,
                cseq=self.cseq,
                session_id=self.session_id,
                client_port=self.RTP_PORT
            )

            self.tcp_socket.send(request.encode())
            response = self.tcp_socket.recv(1024).decode()
            status_code = response.split(" ")[1]

            self.handle_errors(status_code)

            if command == "SETUP":
                self.session_id = self._parse_session_id(response)
                self._setup_udp_socket()
            elif command == "PLAY":
                self.running = True
                threading.Thread(target=self.receive_frame_thread, daemon=True).start()
            elif command in ["PAUSE", "TEARDOWN"]:
                self.running = False
                if command == "TEARDOWN":
                    self.socket.close()
                    self.socket = None
            self.cseq += 1

        except socket.error as e:
            logger.error(f"Socket error: {e}")
            self.running = False
            self._close_sockets()

    def handle_errors(self, status_code):
        if status_code != "200":
            match status_code:
                case "400": logger.error("400 Bad Request")
                case "404": logger.error("404 File Not Found")
                case "500": logger.error("500 Internal Server Error")
                case "501": logger.error("501 Not Implemented")
                case _: logger.error(f"Unknown error: {status_code}")
            return
        else: logger.info("200 OK! RTSP command successful")

    def update_movie(self, data):
        photo = ImageTk.PhotoImage(Image.open(io.BytesIO(data)))
        self.movie.configure(image=photo)
        self.movie.photo_image = photo

    def _parse_session_id(self, response):
        for line in response.splitlines():
            if line.startswith("Session:"):
                return line.split(":", 1)[1].strip()
        return None