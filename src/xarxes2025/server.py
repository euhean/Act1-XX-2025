from loguru import logger
from xarxes2025.clienthandler import ClientHandler

import socket
import sys
import threading
import time


class Server:
    """
    RTSP server implementation that handles multiple client connections.
    
    This class manages the TCP socket for RTSP signaling and spawns
    ClientHandler threads for each incoming connection.
    """
    
    def __init__(self, port, host):
        """
        Initialize the RTSP server.
        
        Args:
            port (int): The port number to listen on for RTSP connections
            host (str): The hostname or IP address to bind to
        """
        self.host = host
        self.port = port
        self.server_socket = None
        self.client_threads = []
        self.running = False
        self.cleanup_thread = None
        self.lock = threading.Lock()  # For thread-safe operations on client_threads
    
    def initialize_socket(self):
        """
        Initialize the server socket with appropriate options.
        
        This method creates a TCP socket, sets the necessary options,
        binds it to the specified host and port, and starts listening.
        
        Raises: SystemExit: If socket initialization fails
        """
        try:
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            # Allow socket reuse to avoid "address already in use" errors
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            # Set TCP keep-alive options
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            # Set a reasonable timeout
            self.server_socket.settimeout(1.0) 
            # Bind and listen
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(10)  # Increased backlog for high-load scenarios
            logger.info(f"RTSP server listening on {self.host}:{self.port}")
        except Exception as e:
            logger.exception(f"Failed during socket initialization: {e}")
            sys.exit(1)
    
    def run(self):
        """
        Main server loop that accepts incoming connections.
        
        This method runs indefinitely, accepting new client connections
        and spawning a ClientHandler thread for each one. It also starts
        a cleanup thread to manage terminated connections.
        """
        self.initialize_socket()
        self.running = True
        
        # Start cleanup thread for dead connections
        self.cleanup_thread = threading.Thread(target=self._cleanup_dead_threads, daemon=True)
        self.cleanup_thread.start()
        
        try:
            while self.running:
                try:
                    client_socket, addr = self.server_socket.accept()
                    logger.info(f"Accepted connection from {addr}")
                    # Set TCP_NODELAY to minimize latency
                    client_socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                    # Create and start client handler
                    handler = ClientHandler(client_socket, addr)
                    with self.lock: self.client_threads.append(handler)
                    handler.start()
                except socket.timeout: continue
                except Exception as e:
                    if self.running:  # Only log if we're supposed to be running
                        logger.error(f"Error accepting connection: {e}")
        except KeyboardInterrupt: logger.info("Server shutdown requested via KeyboardInterrupt")
        except Exception as e: logger.exception(f"Server crashed: {e}")
        finally: self.shutdown()
    
    def _cleanup_dead_threads(self):
        """
        Periodically clean up terminated client threads.
        
        This background thread removes dead client handler threads
        from the client_threads list to prevent memory leaks.
        """
        while self.running:
            try:
                with self.lock:
                    # Filter out dead threads
                    active_threads = [t for t in self.client_threads if t.is_alive()]
                    if len(active_threads) < len(self.client_threads):
                        logger.debug(f"Cleaned up {len(self.client_threads) - len(active_threads)} dead threads")
                        self.client_threads = active_threads
                # Sleep to avoid high CPU usage
                time.sleep(5)
            except Exception as e: logger.error(f"Error in cleanup thread: {e}")
    
    def shutdown(self):
        """
        Gracefully shutdown the server and all client connections.
        
        This method stops the accept loop, terminates all client handler
        threads, and closes the server socket. It ensures resources are
        properly released.
        """
        logger.info("Shutting down server...")
        self.running = False
        
        try:
            # Close server socket first to stop accepting new connections
            if self.server_socket:
                self.server_socket.close()
                self.server_socket = None
                logger.info("Server socket closed")
            
            # Shutdown all client threads with a timeout
            logger.info("Shutting down all client threads...")
            with self.lock: active_threads = list(self.client_threads)
                
            for thread in active_threads:
                try:
                    if thread.is_alive():
                        thread.shutdown()
                        thread.join(timeout=1) 
                        if thread.is_alive(): logger.warning(f"[Session {thread.session.session_id}] ClientHandler thread did not terminate in time")
                        else: logger.info(f"[Session {thread.session.session_id}] ClientHandler thread joined")
                except Exception as e: logger.warning(f"Error shutting down thread: {e}")
                
            # Wait for cleanup thread to finish
            if self.cleanup_thread and self.cleanup_thread.is_alive(): self.cleanup_thread.join(timeout=1)
        except Exception as e: logger.warning(f"Error during shutdown: {e}")
        finally:
            logger.info("Server shutdown complete")
            sys.exit(0)