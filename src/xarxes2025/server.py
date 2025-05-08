import socket
import threading
import random
import time
from enum import Enum, auto
import re
from loguru import logger
from xarxes2025.udpdatagram import UDPDatagram
from xarxes2025.videoprocessor import VideoProcessor

class State(Enum):
    INIT = auto()
    READY = auto()
    PLAYING = auto()

class Server(object):
    def __init__(self, port, host, max_frames, frame_rate, loss_rate, error):
        self.port = port
        self.server_ip = host
        self.max_frames = max_frames  
        self.frame_rate = frame_rate  
        self.loss_rate = loss_rate    
        self.error = error            
        self.run_server()

    def run_server(self):
        try:
            server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.server_ip, self.port))
            server.listen()
            print(f"Listening on {self.server_ip}:{self.port}")
            if self.error > 0:
                print(f"Error simulation mode: {self.error}")

            while True:
                client_socket, client_address = server.accept()
                print(f"Accepted connection from {client_address[0]}:{client_address[1]}")
                thread = threading.Thread(target=self.handle_client, args=(client_socket, client_address))
                thread.start()

        except Exception as e:
            print(f"Error: {e}")

    def send_rtsp_response(self, client_socket, code, cseq, session_id=None):
        messages = {
            200: "OK",
            400: "Bad Request",
            404: "File Not Found",
            500: "Internal Server Error",
            501: "Not Implemented"
        }
        
        # Simulación de error: CSeq incorrecto (error 101)
        if self.error == 101:
            cseq = "-1"
            
        # Simulación de error: CSeq como texto (error 102)
        if self.error == 102:
            cseq = "ERROR"
            
        # Simulación de error: ID de sesión incorrecto (error 100)
        if self.error == 100 and session_id:
            session_id = "ERROR"
            
        reason = messages.get(code, "Unknown")
        response = f"RTSP/1.0 {code} {reason}\r\nCSeq: {cseq}\r\n"
        if session_id:
            response += f"Session: {session_id}\r\n"
        client_socket.send(response.encode("utf-8"))
        logger.debug(f"Sent response: {response.strip()}")

    def handle_client(self, client_socket, client_address):
        try:
            local_state = State.INIT
            local_session_id = None
            local_video = None
            local_udp_address = None
            local_udp_socket = None  

            while True:
                request = client_socket.recv(1024)
                if not request:
                    break

                ordersTokenizer = re.split(b'[ \r\n]+', request)

                cseq = ordersTokenizer[4].decode()

                if len(ordersTokenizer) < 3 or b'RTSP/1.0' not in ordersTokenizer:
                    self.send_rtsp_response(client_socket, 400, cseq)
                    continue

                match ordersTokenizer[0]:
                    case b'SETUP':
                        # Rechazar SETUP si ya hay una sesión activa (READY o PLAYING)
                        if local_state == State.READY or local_state == State.PLAYING:
                            logger.warning("Client attempted SETUP with existing session")
                            self.send_rtsp_response(client_socket, 400, cseq, local_session_id)
                            continue
                            
                        # Simulación de error: Responder con 400 a todas las peticiones SETUP (error 1)
                        if self.error == 1:
                            self.send_rtsp_response(client_socket, 400, cseq)
                            continue
                            
                        # Simulación de error: Responder con 500 a todas las peticiones SETUP (error 2)
                        if self.error == 2:
                            self.send_rtsp_response(client_socket, 500, cseq)
                            continue
                            
                        local_session_id = "XARXES_0000" + str(random.randint(1000, 9999))

                        video_file = ordersTokenizer[1].decode()

                        if video_file:
                            try:
                                local_video = VideoProcessor(video_file)
                                logger.debug(f"Loaded video: {video_file}")
                            except Exception as e:
                                logger.error(f"Error loading video: {e}")
                                self.send_rtsp_response(client_socket, 404, cseq)
                                continue
                        else:
                            self.send_rtsp_response(client_socket, 400, cseq)
                            continue

                        client_port = int(ordersTokenizer[8].decode())
                        if client_port:
                            local_udp_address = (client_address[0], client_port)
                            logger.debug(f"Set client UDP address to {local_udp_address}")
                        else:
                            self.send_rtsp_response(client_socket, 400, cseq)
                            continue

                        local_udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                        self.send_rtsp_response(client_socket, 200, cseq, local_session_id)
                        local_state = State.READY

                    case b'PLAY':
                        if local_state == State.READY:
                            # Simulación de error: Responder con 400 a PLAY (error 3)
                            if self.error == 3:
                                self.send_rtsp_response(client_socket, 400, cseq)
                                continue
                                
                            # Simulación de error: Responder con 500 a PLAY (error 4)
                            if self.error == 4:
                                self.send_rtsp_response(client_socket, 500, cseq)
                                continue
                                
                            if local_video and local_udp_address and local_udp_socket:
                                self.send_rtsp_response(client_socket, 200, cseq, local_session_id)
                                local_state = State.PLAYING
                                threading.Thread(
                                    target=self.send_udp_frames,
                                    args=(local_video, local_udp_socket, local_udp_address, lambda: local_state == State.PLAYING),
                                    daemon=True
                                ).start()
                        else:
                            self.send_rtsp_response(client_socket, 400, cseq)

                    case b'PAUSE':
                        if local_state == State.PLAYING:
                            # Simulación de error: Responder con 400 a PAUSE (error 5)
                            if self.error == 5:
                                self.send_rtsp_response(client_socket, 400, cseq)
                                continue
                                
                            # Simulación de error: Responder con 500 a PAUSE (error 6)
                            if self.error == 6:
                                self.send_rtsp_response(client_socket, 500, cseq)
                                continue
                                
                            local_state = State.READY
                            self.send_rtsp_response(client_socket, 200, cseq, local_session_id)
                        else:
                            self.send_rtsp_response(client_socket, 400, cseq)

                    case b'TEARDOWN':
                        if local_state == State.READY or local_state == State.PLAYING:
                            # Simulación de error: Responder con 400 a TEARDOWN (error 3)
                            if self.error == 3 or self.error == 5:
                                self.send_rtsp_response(client_socket, 400, cseq)
                                continue
                                
                            # Simulación de error: Responder con 500 a TEARDOWN (error 4)
                            if self.error == 4 or self.error == 6:
                                self.send_rtsp_response(client_socket, 500, cseq)
                                continue
                        
                        self.send_rtsp_response(client_socket, 200, cseq, local_session_id)
                        logger.info(f"Session with {client_address} torn down.")
                        
                        local_state = State.INIT

                        if local_udp_socket:
                            local_udp_socket.close()
                            logger.debug("Closed client UDP socket.")

                        local_video = None
                        local_session_id = None
                        local_udp_address = None
                        local_udp_socket = None

                    case b'CLOSE':
                        local_state = State.INIT
                        
                        time.sleep(0.1)
                        
                        if local_udp_socket:
                            local_udp_socket.close()
                            logger.debug("Closed client UDP socket.")
                        client_socket.close()
                        logger.info(f"Connection closed with {client_address}")
                        break

                    case _:
                        self.send_rtsp_response(client_socket, 501, cseq)

        except Exception as e:
            logger.error(f"Error when handling client: {e}")
            try:
                self.send_rtsp_response(client_socket, 500, "0")
            except:
                pass
        finally:
            local_state = State.INIT
            client_socket.close()
            print(f"Connection to client ({client_address[0]}:{client_address[1]}) closed")

    def send_udp_frames(self, video, udp_socket, client_udp_address, is_active):
        frame_interval = 1.0 / self.frame_rate
        sent_frames = 0

        while is_active():
            # Comprobamos si hemos alcanzado el límite de frames
            if self.max_frames > 0 and sent_frames >= self.max_frames:
                break
                
            data = video.next_frame()
            if data is None:
                print("No more frames available.")
                break
                
            frame_number = video.get_frame_number()
            
            # Aplicamos la simulación de pérdida de paquetes
            if random.randint(1, 100) > self.loss_rate:
                try:
                    packet = UDPDatagram(frame_number, data).get_datagram()
                    udp_socket.sendto(packet, client_udp_address)
                    sent_frames += 1
                except Exception as e:
                    print(f"Error sending UDP packet: {e} - socket might be closed")
                    break
            
            # Esperamos según los fps configurados
            time.sleep(frame_interval)