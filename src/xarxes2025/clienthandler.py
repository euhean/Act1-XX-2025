from xarxes2025.udpdatagram import UDPDatagram
from xarxes2025.videoprocessor import VideoProcessor
from xarxes2025.helpers import RTSPResponseBuilder

from loguru import logger

import threading
import socket
import random
import time


class ClientHandler(threading.Thread):
    INIT, READY, PLAYING = "INIT", "READY", "PLAYING"

    def __init__(self, client_socket, address):
        super().__init__(daemon=True)
        self.client_socket = client_socket
        self.client_address = address
        self.state = self.INIT
        self.session_id = None
        self.filename = None
        self.video = None
        self.streaming = False
        self.frame_number = 0
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.frame_interval = 1 / 30
        self.play_event = threading.Event()

    def run(self):
        try:
            while True:
                self.listen_rtsp_request()
        except Exception as e:
            logger.error(f"ClientHandler crashed: {e}")
        finally:
            self.shutdown()

    def transition(self, next_state):
        logger.info(f"[Session {self.session_id}] Transition: {self.state} -> {next_state}")
        self.state = next_state

    def listen_rtsp_request(self):
        request = self.client_socket.recv(1024).decode()
        lines = request.strip().split('\n')
        if not lines:
            self._send_rtsp_response("0", 400, "Bad Request")
            return

        method, filename = lines[0].split(' ')[:2]
        headers = self._parse_headers(lines[1:])
        cseq = headers.get("CSeq", "0")

        logger.info(f"[Session {self.session_id}] {method} request, CSeq {cseq}, State {self.state}")

        self._dispatch_request(method, filename, headers, cseq)

    def _dispatch_request(self, method, filename, headers, cseq):
        match method:
            case "SETUP":
                if self.state == self.INIT:
                    self._handle_setup(filename, headers)
                else:
                    self._send_rtsp_response(cseq, 400, "Unexpected SETUP")
            case "PLAY":
                if self.state == self.READY:
                    self._handle_play(headers)
                else:
                    self._send_rtsp_response(cseq, 400, "Unexpected PLAY")
            case "PAUSE":
                if self.state == self.PLAYING:
                    self._handle_pause(headers)
                else:
                    self._send_rtsp_response(cseq, 400, "Unexpected PAUSE")
            case "TEARDOWN":
                self._handle_teardown(headers)
            case _:
                self._send_rtsp_response(cseq, 501, "Not Implemented")

    def _parse_headers(self, header_lines):
        headers = {}
        for line in header_lines:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
        return headers

    def _handle_setup(self, filename, headers):
        self.filename = filename
        try:
            self.video = VideoProcessor(self.filename)
        except FileNotFoundError:
            logger.error(f"File not found: {filename}")
            self._send_rtsp_response(headers.get("CSeq", "0"), 404, "File Not Found")
            return

        self.session_id = f"XARXES_{random.randint(0,99999999):010d}"
        if "Transport" not in headers:
            self._send_rtsp_response(headers.get("CSeq", "0"), 400, "Missing Transport Header")
            return

        try:
            parts = headers["Transport"].split(';')
            udp_port = next(int(p.split('=')[1]) for p in parts if 'client_port' in p)
            self.client_udp_address = (self.client_address[0], udp_port)
        except Exception:
            self._send_rtsp_response(headers.get("CSeq", "0"), 400, "Invalid Transport Header")
            return

        self._send_rtsp_response(headers["CSeq"], session=self.session_id)
        self.transition(self.READY)

    def _handle_play(self, headers):
        if headers.get("Session") != self.session_id:
            self._send_rtsp_response(headers.get("CSeq", "0"), 400, "Invalid Session")
            return

        self._send_rtsp_response(headers["CSeq"], session=self.session_id)
        self.play_event.set()
        if not self.streaming:
            self.streaming = True
            threading.Thread(target=self.stream_frames, daemon=True).start()
        self.transition(self.PLAYING)

    def _handle_pause(self, headers):
        if headers.get("Session") != self.session_id:
            self._send_rtsp_response(headers.get("CSeq", "0"), 400, "Invalid Session")
            return

        self._send_rtsp_response(headers["CSeq"], session=self.session_id)
        self.play_event.clear()
        self.transition(self.READY)

    def _handle_teardown(self, headers):
        if headers.get("Session") != self.session_id:
            self._send_rtsp_response(headers.get("CSeq", "0"), 400, "Invalid Session")
            return

        self.streaming = False
        self.play_event.clear()
        self._send_rtsp_response(headers["CSeq"], session=self.session_id)
        self.transition(self.INIT)
        self.shutdown()

    def stream_frames(self):
        while self.streaming:
            self.play_event.wait()
            frame_data = self.video.next_frame()
            if frame_data:
                datagram = UDPDatagram(self.frame_number, frame_data).get_datagram()
                self.udp_socket.sendto(datagram, self.client_udp_address)
                self.frame_number += 1
            time.sleep(self.frame_interval)

    def _send_rtsp_response(self, cseq, code=200, status="OK", session=None):
        response = RTSPResponseBuilder.build(cseq, code, status, session)
        self.client_socket.send(response.encode())

    def shutdown(self):
        logger.info(f"Shutting down session {self.session_id}...")
        try:
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None
            if self.udp_socket:
                self.udp_socket.close()
                self.udp_socket = None
        except Exception as e:
            logger.warning(f"Shutdown error: {e}")