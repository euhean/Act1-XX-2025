from xarxes2025.udpdatagram import UDPDatagram
from xarxes2025.videoprocessor import VideoProcessor
from xarxes2025.helpers import RTSPParser
from xarxes2025.session import ClientSessionManager

from loguru import logger

import threading
import socket
import time


class ClientHandler(threading.Thread):
    def __init__(self, client_socket, address):
        super().__init__(daemon=True)
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.client_socket = client_socket
        self.client_address = address
        self.session = ClientSessionManager(self.client_socket)
        self.filename = None
        self.video = None
        self.streaming = False
        self.frame_number = 0
        self.frame_interval = 1 / 30
        self.play_event = threading.Event()

    def run(self):
        try:
            while True:
                self._listen_rtsp_request()
        except Exception as e:
            logger.exception(f"ClientHandler crashed: {e}")
        finally:
            self.shutdown()

    def _listen_rtsp_request(self):
        if not self.client_socket:
            return
        try:
            request = self.client_socket.recv(1024).decode()
        except Exception as e:
            logger.exception(f"ClientHandler crashed while reading: {e}")
            self.shutdown()
            return

        parsed = RTSPParser.parse_response(request)
        command_line = request.splitlines()[0] if request else ""
        command_parts = command_line.split(" ")
        command = command_parts[0] if len(command_parts) >= 1 else None
        filename = command_parts[1] if len(command_parts) >= 2 else None

        cseq = parsed["headers"].get("CSeq", "0")
        logger.info(f"[Session {self.session.session_id}] {command} request, CSeq {cseq}, State {self.session.state}")

        if not command or not filename:
            self.session._send_response(cseq, 400, "Bad Request")
            return

        self._dispatch_request(command, filename, parsed["headers"], cseq)

    def _dispatch_request(self, command, filename, headers, cseq):
        if command == "SETUP":
            if self.session.state != "INIT":
                self.session._send_response(cseq, 400, "Unexpected SETUP")
                return
            self._handle_setup(filename, headers, cseq)
        elif command == "PLAY":
            if self.session.state != "READY":
                self.session._send_response(cseq, 400, "Unexpected PLAY")
                return
            self._handle_play(headers, cseq)
        elif command == "PAUSE":
            if self.session.state != "PLAYING":
                self.session._send_response(cseq, 400, "Unexpected PAUSE")
                return
            self._handle_pause(headers, cseq)
        elif command == "TEARDOWN": self._handle_teardown(headers, cseq)
        else: self.session._send_response(cseq, 501, "Not Implemented")

    def _handle_setup(self, filename, headers, cseq):
        self.filename = filename
        try:
            self.video = VideoProcessor(self.filename)
        except FileNotFoundError:
            logger.error(f"File not found: {filename}")
            self.session._send_response(cseq, 404, "File Not Found")
            return

        if "Transport" not in headers:
            self.session._send_response(cseq, 400, "Missing Transport Header")
            return
        else:
            try:
                parts = headers["Transport"].split(';')
                udp_port = next(int(p.split('=')[1]) for p in parts if 'client_port' in p)
                self.client_udp_address = (self.client_address[0], udp_port)
            except Exception:
                self.session._send_response(cseq, 400, "Invalid Transport Header")
                return

        self.session._start_session()
        self.session._send_response(cseq)

    def _handle_play(self, headers, cseq):
        if not self.session._validate_session(headers, cseq):
            return

        self.play_event.set()
        if not self.streaming:
            self.streaming = True
            threading.Thread(target=self._stream_frames, daemon=True).start()

    def _handle_pause(self, headers, cseq):
        if not self.session._validate_session(headers, cseq):
            return

        self.streaming = False
        self.play_event.clear()

    def _handle_teardown(self, headers, cseq):
        if not self.session._validate_session(headers, cseq):
            return

        self.streaming = False
        self.play_event.clear()
        self.session._send_response(cseq)
        self.shutdown()

    def _stream_frames(self):
        while self.streaming:
            self.play_event.wait()
            frame_data = self.video.next_frame()
            if frame_data:
                try:
                    datagram = UDPDatagram(self.frame_number, frame_data).get_datagram()
                    self.udp_socket.sendto(datagram, self.client_udp_address)
                    self.frame_number += 1
                except (OSError, socket.error) as e:
                    logger.warning(f"""[Session {self.session.session_id}] Socket closed or unreachable: {e}""")
                    self.streaming = False
                    break
            time.sleep(self.frame_interval)

    def shutdown(self):
        self.streaming = False
        self.play_event.set()
        try:
            if self.client_socket:
                self.client_socket.close()
                self.client_socket = None
                logger.info(f"[Session {self.session.session_id}] TCP socket closed")
            if self.udp_socket:
                self.udp_socket.close()
                self.udp_socket = None
                logger.info(f"[Session {self.session.session_id}] UDP socket closed")
        except Exception as e:
            logger.warning(f"Shutdown error: {e}")
        finally:
            logger.info(f"[Session {self.session.session_id}] finished")