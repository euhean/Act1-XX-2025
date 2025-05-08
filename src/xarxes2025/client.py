import sys 
import socket
import threading
import io
import re
from enum import Enum, auto
from tkinter import Tk, Label, Button, W, E, N, S
from tkinter import messagebox
from loguru import logger
from PIL import Image, ImageTk
from xarxes2025.udpdatagram import UDPDatagram

class State(Enum):
    INIT = auto()
    READY = auto()
    PLAYING = auto()

class Client(object): 
    def __init__(self, server_port, server_host, udp_port, filename):
        logger.debug(f"Client created")
        self.server_port = server_port
        self.server_host = server_host
        self.fileName = filename
        self.udp_port = udp_port
        self.CSeq = 0
        self.state = State.INIT
        self.session_id = None 
        self.udp_socket = None
        self.udp_listening = False
        self.create_ui()
        self.run_client()

    def create_ui(self):
        self.root = Tk()
        self.root.wm_title("RTP Client")
        self.root.protocol("WM_DELETE_WINDOW", self.ui_close_window)

        self.setup = self._create_button("Setup", self.ui_setup_event, 0, 0)
        self.start = self._create_button("Play", self.ui_play_event, 0, 1)
        self.pause = self._create_button("Pause", self.ui_pause_event, 0, 2)
        self.teardown = self._create_button("Teardown", self.ui_teardown_event, 0, 3)

        self.movie = Label(self.root, height=29)
        self.movie.grid(row=1, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

        self.text = Label(self.root, height=3)
        self.text.grid(row=2, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5)

        return self.root
    
    def _create_button(self, text, command, row=0, column=0, width=20, padx=3, pady=3):
        button = Button(self.root, width=width, padx=padx, pady=pady)
        button["text"] = text
        button["command"] = command
        button.grid(row=row, column=column, padx=2, pady=2)
        return button

    def ui_close_window(self):
        if not messagebox.askyesno("Quit?", "Close application?"):
            return

        self.teardown_udp_socket()
        self.root.destroy()
        logger.debug("Window closed")
        sys.exit(0)

    def ui_setup_event(self):
        if self.state == State.INIT:
            self.CSeq += 1
            request = (
                f"SETUP {self.fileName} RTSP/1.0\r\n"
                f"CSeq: {self.CSeq}\r\n"
                f"Transport: RTP/UDP; client_port= {self.udp_port}\r\n\r\n"  
            )
            self.send_request(request)
        else:
            self.text["text"] = "Error: already setup"

    def ui_play_event(self):
        if self.state == State.READY and self.session_id:
            self.CSeq += 1
            request = (
                f"PLAY {self.fileName} RTSP/1.0\r\n"
                f"CSeq: {self.CSeq}\r\n"
                f"Session: {self.session_id}\r\n\r\n"  
            )
            self.send_request(request)
        else:
            self.text["text"] = "Error: not ready to play"

    def ui_pause_event(self):
        if self.state == State.PLAYING and self.session_id:
            self.CSeq += 1
            request = (
                f"PAUSE {self.fileName} RTSP/1.0\r\n"
                f"CSeq: {self.CSeq}\r\n"
                f"Session: {self.session_id}\r\n\r\n"  
            )
            self.send_request(request)
        else:
            self.text["text"] = "Error: not playing"

    def ui_teardown_event(self):
        if self.state != State.INIT and self.session_id:
            self.CSeq += 1
            request = (
                f"TEARDOWN {self.fileName} RTSP/1.0\r\n"
                f"CSeq: {self.CSeq}\r\n"
                f"Session: {self.session_id}\r\n\r\n"  
            )
            self.udp_listening = False
            self.send_request(request)
        else:
            self.text["text"] = "Error: not in session"

    def run_client(self):
        try:
            self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client.connect((self.server_host, self.server_port))
            logger.debug("Connected to server")
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            messagebox.showerror("Connection Error", f"Could not connect to server: {e}")
            sys.exit(1)

    def send_request(self, request):
        try:
            self.client.send(request.encode("utf-8"))
            logger.debug(f"Sent request:\n{request}")
            response = self.client.recv(2068).decode("utf-8")
            logger.debug(f"Received response:\n{response}")
            self.handle_response(response, request)
            self.text["text"] = response
        except Exception as e:
            logger.error(f"Error sending command '{request}': {e}")
            messagebox.showerror("Error", f"Failed to send command: {e}")

    def handle_response(self, response, request):
        lines = re.split(r'\r\n|\r|\n', response)
        lines = [line for line in lines if line.strip()]  # Elimina líneas vacías
        
        if not lines:
            logger.error("Respuesta vacía del servidor")
            return
            
        status_line = lines[0]
        logger.debug(f"Status line: {status_line}")
        
        status_match = re.search(r'RTSP/1.0 (\d+)', status_line)
        if not status_match:
            logger.error(f"No se pudo extraer el código de estado de: {status_line}")
            return
            
        status_code = int(status_match.group(1))
        logger.debug(f"Status code: {status_code}")
        
        session_id = None
        for line in lines[1:]:  
            logger.debug(f"Processing header line: {line}")
            if line.lower().startswith("session:"):
                parts = line.split(":", 1)
                if len(parts) > 1:
                    session_id = parts[1].strip()
                    if ";" in session_id:
                        session_id = session_id.split(";")[0].strip()
                    logger.debug(f"Found session ID: {session_id}")
        
        if session_id:
            self.session_id = session_id
            logger.debug(f"Session recibida y guardada: {self.session_id}")

        request_type = request.split()[0] if request else ""
        
        if status_code == 200:
            if request_type == "SETUP":
                if self.session_id:  
                    self.state = State.READY
                    logger.debug("Estado cambiado a READY")
                    self.start_udp_listener()
                else:
                    logger.error("SETUP exitoso pero no se recibió ID de sesión")
                    self.text["text"] = "Error: No session ID received"

            elif request_type == "PLAY":
                self.state = State.PLAYING
                logger.debug("Estado cambiado a PLAYING")
                self.text["text"] = "Playing"

            elif request_type == "PAUSE":
                self.state = State.READY
                logger.debug("Estado cambiado a READY desde PAUSE")
                self.text["text"] = "Paused"

            elif request_type == "TEARDOWN":
                self.teardown_udp_socket()
                self.state = State.INIT
                self.session_id = None
                logger.debug("Estado cambiado a INIT y socket UDP destruido")
                self.text["text"] = "Session closed, ready to setup again"
        
        elif status_code == 400:
            logger.warning("Bad Request")
            self.text["text"] = "Error 400: Bad Request"
        elif status_code == 404:
            logger.warning("File Not Found")
            self.text["text"] = "Error 404: File Not Found"
        elif status_code == 500:
            logger.warning("Internal Server Error")
            self.text["text"] = "Error 500: Internal Server Error"
        elif status_code == 501:
            logger.warning("Not Implemented")
            self.text["text"] = "Error 501: Not Implemented"
        else:
            logger.warning(f"Unknown status code: {status_code}")
            self.text["text"] = f"Error: Unknown status code {status_code}"

    def start_udp_listener(self):
        self.teardown_udp_socket()

        try:
            self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.udp_socket.bind(('', self.udp_port))
            self.udp_listening = True
            logger.debug(f"UDP socket listening on port {self.udp_port}")

            def listen():
                while self.udp_listening:
                    try:
                        data, addr = self.udp_socket.recvfrom(65536)
                        logger.debug(f"Received UDP data from {addr}, size: {len(data)} bytes")
                        datagram = UDPDatagram(0, b"")
                        datagram.decode(data)
                        payload = datagram.get_payload()
                        self.updateMovie(payload)
                    except Exception as e:
                        if self.udp_listening:  
                            logger.warning(f"UDP Listener error: {e}")
            
            threading.Thread(target=listen, daemon=True).start()
            logger.debug("UDP listener thread started")
        except Exception as e:
            logger.error(f"Failed to start UDP listener: {e}")
            self.text["text"] = f"Error starting UDP: {e}"

    def teardown_udp_socket(self):
        if self.udp_socket:
            try:
                self.udp_listening = False  
                self.udp_socket.close()
                self.udp_socket = None
                logger.debug("UDP socket cerrado correctamente")
            except Exception as e:
                logger.warning(f"Error al cerrar el socket UDP: {e}")

    def updateMovie(self, data):
        try:
            image = Image.open(io.BytesIO(data))
            photo = ImageTk.PhotoImage(image)
            self.movie.configure(image=photo, height=380)
            self.movie.photo_image = photo  
        except Exception as e:
            logger.warning(f"Could not update image: {e}")