from xarxes2025.udpdatagram import UDPDatagram
from xarxes2025.videoprocessor import VideoProcessor

from loguru import logger

import socket
import sys
import random


class Server(object):
    def __init__(self, port):
        self.HOST = "127.0.0.1"
        self.PORT = port if port else 4321
        self.server_address = (self.HOST, self.PORT)
        self.frame_number = 0

        self.client_address = None 
        self.filename = None
        self.session_id = None
        self.video: VideoProcessor = None

        try:
            self._setup_sockets()
        except OSError as e:
            logger.error(f"Failed to bind sockets - {e}")
            sys.exit(1)

    def _setup_sockets(self):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(self.server_address)
        self.tcp_socket.listen(1)
        logger.success(f"RTSP TCP socket listening at {self.HOST}:{self.PORT}")

        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.settimeout(0.5)

    def accept_client(self):
        logger.info("Waiting for RTSP client connection...")
        self.tcp_client_socket, client_tcp_addr = self.tcp_socket.accept()
        logger.success(f"RTSP connection established with {client_tcp_addr}")

    def listen_rtsp_request(self):
        logger.info("Waiting for RTSP request from client...")
        try:
            request = self.tcp_client_socket.recv(1024).decode()
            logger.debug(f"Received RTSP request:\n{request}")

            lines = request.strip().split('\n')
            if not lines:
                return

            method, filename = lines[0].split(' ')[:2]
            headers = self._parse_headers(lines[1:])

            match method:
                case "SETUP":
                    self._handle_setup(filename, headers)
                case "PLAY":
                    self._handle_simple_session_command("PLAY", headers)
                case "PAUSE":
                    self._handle_simple_session_command("PAUSE", headers)
                case "TEARDOWN":
                    self._handle_teardown(headers)
                case _:
                    self._send_rtsp_response(headers.get("CSeq", "0"), 501, "Not Implemented")

        except Exception as e:
            logger.error(f"Error reading RTSP request: {e}")

    def _parse_headers(self, header_lines):
        headers = {}
        for line in header_lines:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
        return headers

    def _extract_client_port(self, transport):
        for part in transport.split(';'):
            if part.strip().startswith("client_port"):
                return int(part.split('=')[1])
        return None

    def _is_valid_session(self, session):
        return session == self.session_id

    def _handle_setup(self, filename, headers):
        self.filename = filename
        self.session_id = f"XARXES_{random.randint(0, 99999999):010d}"
        self.video = VideoProcessor(self.filename)

        transport = headers.get("Transport")
        if transport:
            udp_port = self._extract_client_port(transport)
            if udp_port:
                self.client_address = ("127.0.0.1", udp_port)
                logger.success(f"Client UDP port set to {udp_port}")

        cseq = headers.get("CSeq", "0")
        self._send_rtsp_response(cseq, session=self.session_id)

    def _handle_simple_session_command(self, method, headers):
        cseq = headers.get("CSeq", "0")
        session = headers.get("Session")
        if self._is_valid_session(session):
            logger.info(f"Received valid {method} request.")
            self._send_rtsp_response(cseq, session=session)
        else: self._send_rtsp_response(cseq, 400, "Invalid Session")

    def _handle_teardown(self, headers):
        cseq = headers.get("CSeq", "0")
        session = headers.get("Session")
        if self._is_valid_session(session):
            self._send_rtsp_response(cseq, session=session)
            self.udp_socket.close()
            self.session_id = None
            self.video = None
            self.client_address = None
        else: self._send_rtsp_response(cseq, 400, "Invalid Session")

    def send_udp_frame(self):
        if not self.video:
            logger.warning("No video processor assigned to server.")
            return
        if not self.client_address:
            logger.warning("No client UDP address available.")
            return

        data = self.video.next_frame()
        if data:
            udp_datagram = UDPDatagram(self.frame_number, data).get_datagram()
            self.udp_socket.sendto(udp_datagram, self.client_address)
            logger.info(f"Sent frame {self.frame_number} to {self.client_address[0]}:{self.client_address[1]}")
            self.frame_number += 1

    def _send_rtsp_response(self, cseq, code=200, status="OK", session=None):
        response = f"RTSP/1.0 {code} {status}\nCSeq: {cseq}\n"
        if session: response += f"Session: {session}\n"
        response += "\n"
        self.tcp_client_socket.send(response.encode())