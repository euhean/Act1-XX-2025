from loguru import logger
from xarxes2025.clienthandler import ClientHandler

import socket
import sys


class Server:
    def __init__(self, port, host):
        self.host = host or "127.0.0.1"
        self.port = port or 4321
        self.server_socket = None
        self.client_threads = []

    def initialize_socket(self):
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            logger.info(f"RTSP server listening on {self.host}:{self.port}")
        except Exception as e:
            logger.exception(f"Failed during server initialization: {e}")
            sys.exit(1)

    def run(self):
        self.initialize_socket()
        try:
            while True:
                client_socket, addr = self.server_socket.accept()
                logger.info(f"Accepted connection from {addr}")
                handler = ClientHandler(client_socket, addr)
                handler.start()
        except KeyboardInterrupt:
            logger.info("Server shutdown requested via KeyboardInterrupt")
        except Exception as e:
            logger.exception(f"Server crashed: {e}")
        finally:
            self.shutdown()

    def shutdown(self):
        try:
            logger.info("Shutting down all client threads...")
            for thread in self.client_threads:
                if thread.is_alive():
                    thread.shutdown()
                    thread.join(timeout=2)
                    logger.info(f"[Session {thread.session_id or 'N/A'}] ClientHandler thread joined")
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
                logger.info("Server socket closed")
        except Exception as e:
            logger.warning(f"Error during shutdown: {e}")
        finally:
            sys.exit(0)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RTSP Server")
    parser.add_argument("--port", type=int, default=4321)
    parser.add_argument("--host", type=str, default="127.0.0.1")
    args = parser.parse_args()
    server = Server(args.port)
    server.run()


if __name__ == "__main__":
    main()