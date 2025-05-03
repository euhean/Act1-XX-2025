from xarxes2025.clienthandler import ClientHandler

from loguru import logger

import socket
import sys


class Server:
    def __init__(self, port):
        self.host = "127.0.0.1"
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        logger.info(f"RTSP server listening on {self.host}:{self.port}")

    def run(self):
        try:
            while True:
                client_socket, addr = self.server_socket.accept()
                handler = ClientHandler(client_socket, addr)
                handler.start()
        except KeyboardInterrupt:
            logger.info("Server shutdown requested.")
            self.shutdown()

    def shutdown(self):
        try:
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
        except Exception as e:
            logger.warning(f"Error during server shutdown: {e}")
        sys.exit(0)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="RTSP Server")
    parser.add_argument("--port", type=int, default=4321)
    args = parser.parse_args()
    server = Server(args.port)
    server.run()

if __name__ == "__main__":
    main()