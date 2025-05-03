from xarxes2025.udpdatagram import UDPDatagram
from xarxes2025.videoprocessor import VideoProcessor

from loguru import logger

import threading
import socket
import sys
import random
import time


class Server:
    def __init__(self, port):
        self.HOST = "127.0.0.1"
        self.PORT = port if port else 4321
        self.server_address = (self.HOST, self.PORT)
        self.frame_number = 0
        self.client_address = None 
        self.filename = None
        self.session_id = None
        self.video = None
        self.streaming = False
        self._setup_sockets()

    def _setup_sockets(self):
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp_socket.bind(self.server_address)
        self.tcp_socket.listen(1)
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def accept_client(self):
        self.tcp_client_socket, client_tcp_addr = self.tcp_socket.accept()
        logger.info(f"Client connected: {client_tcp_addr}")

    def listen_rtsp_request(self):
        request = self.tcp_client_socket.recv(1024).decode()
        lines = request.strip().split('\n')
        if not lines: return
        method, filename = lines[0].split(' ')[:2]
        headers = self._parse_headers(lines[1:])
        if method == "SETUP":
            self._handle_setup(filename, headers)
        elif method in ["PLAY", "PAUSE"]:
            self._handle_session_command(method, headers)
        elif method == "TEARDOWN":
            self._handle_teardown(headers)

    def _parse_headers(self, header_lines):
        headers = {}
        for line in header_lines:
            if ":" in line:
                key, value = line.split(":", 1)
                headers[key.strip()] = value.strip()
        return headers

    def _handle_setup(self, filename, headers):
        self.filename = filename
        self.session_id = f"XARXES_{random.randint(0,99999999):010d}"
        udp_port = int(headers["Transport"].split('=')[1])
        client_ip = self.tcp_client_socket.getpeername()[0]
        self.client_address = (client_ip, udp_port)
        self.video = VideoProcessor(self.filename)
        self._send_rtsp_response(headers["CSeq"], session=self.session_id)

    def _handle_session_command(self, method, headers):
        if headers["Session"] != self.session_id:
            self._send_rtsp_response(headers["CSeq"], 400, "Invalid Session")
            return
        self._send_rtsp_response(headers["CSeq"], session=self.session_id)
        if method == "PLAY":
            self.streaming = True
            threading.Thread(target=self.stream_frames, daemon=True).start()
        elif method == "PAUSE":
            self.streaming = False

    def stream_frames(self):
        while self.streaming:
            frame_data = self.video.next_frame()
            if frame_data:
                udp_datagram = UDPDatagram(self.frame_number, frame_data).get_datagram()
                self.udp_socket.sendto(udp_datagram, self.client_address)
                self.frame_number += 1
            time.sleep(0.033)

    def _handle_teardown(self, headers):
        if headers["Session"] != self.session_id:
            self._send_rtsp_response(headers["CSeq"], 400, "Invalid Session")
            return
        self.streaming = False
        self._send_rtsp_response(headers["CSeq"], session=self.session_id)
        self.udp_socket.close()
        self.tcp_client_socket.close()
        self.video = None

    def _send_rtsp_response(self, cseq, code=200, status="OK", session=None):
        response = f"RTSP/1.0 {code} {status}\r\nCSeq: {cseq}\r\n"
        if session: response += f"Session: {session}\r\n"
        response += "\r\n"
        self.tcp_client_socket.send(response.encode())

def main():
    import argparse
    parser = argparse.ArgumentParser(description="RTSP Server")
    parser.add_argument("--port", type=int, default=4321)
    args = parser.parse_args()
    server = Server(args.port)
    server.accept_client()
    try:
        while True:
            server.listen_rtsp_request()
    except KeyboardInterrupt:
        sys.exit(0)

if __name__ == "__main__":
    main()