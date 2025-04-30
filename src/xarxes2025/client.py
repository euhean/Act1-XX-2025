from tkinter import Tk, Label, Button, W, E, N, S
from tkinter import messagebox
import tkinter as tk

from PIL import Image, ImageTk

from loguru import logger

import socket
import sys
import io


class Client(object):        
    def __init__(self, server_port, filename):
        self.HOST: str = "127.0.0.1"
        self.PORT: int = server_port if server_port else 25000
        self.server_address: tuple[str, int] = (self.HOST, self.PORT)

        self.filename = filename

        self.socket = None
        self.running = False

        self.create_ui()

    def create_ui(self):
        """
        Create the user interface for the client.

        This function creates the window for the client and its
        buttons and labels. It also sets up the window to call the
        close window function when the window is closed.

        :returns: The root of the window.
        """
        self.root = Tk()

        # Set the window title
        self.root.wm_title("RTP Client")

        # On closing window go to close window function
        self.root.protocol("WM_DELETE_WINDOW", self.ui_close_window)

        # Create Buttons
        self.setup = self._create_button("Setup", self.ui_setup_event, 0, 0)
        self.start = self._create_button("Play", self.ui_play_event, 0, 1)
        self.pause = self._create_button("Pause", self.ui_pause_event, 0, 2)
        self.teardown = self._create_button("Teardown", self.ui_teardown_event, 0, 3)

        # Create a label to display the movie
        self.movie = Label(self.root, height=29)
        self.movie.grid(row=1, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 

        # Create a label to display text messages
        self.text = Label(self.root, height=3)
        self.text.grid(row=2, column=0, columnspan=4, sticky=W+E+N+S, padx=5, pady=5) 

        return self.root

    def _create_button(self, text, command, row=0, column=0, width=20, padx=3, pady=3):
        """
        Create a button widget with the given text, command, and layout options.

        :param str text: The text to display on the button.
        :param callable command: The function to call when the button is clicked.
        :param int row: The row number of the button in the grid.
        :param int column: The column number of the button in the grid.
        :param int width: The width of the button.
        :param int padx: The horizontal padding of the button.
        :param int pady: The vertical padding of the button.
        :return: The button widget.
        """
        button = Button(self.root, width=width, padx=padx, pady=pady)
        button["text"] = text
        button["command"] = command
        button.grid(row=row, column=column, padx=2, pady=2)
        
        return button

    def ui_close_window(self):
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None

        self.root.destroy()
        logger.debug("Window closed")
        sys.exit(0)

    def ui_setup_event(self):
        logger.debug("Setup button clicked")
        self.text["text"] = "Setup button clicked"
        if self.socket is None:
            try:
                self.socket = socket.socket(
                    family=socket.AF_INET, 
                    type=socket.SOCK_DGRAM, 
                    proto=socket.IPPROTO_UDP
                )
                self.socket.settimeout(0.5)
            except OSError as e:
                logger.error(f"Failed to create socket - {e}")
                sys.exit(1)

            self.socket.sendto(self.filename.encode(), self.server_address)
            logger.success(f"Filename '{self.filename}' sent to {self.server_address}")              

        self.updateMovie(None)

    def ui_play_event(self):
        logger.debug("Play button clicked")
        self.text["text"] = "Play button clicked"
        if self.socket is None:
            logger.error("Socket not set up! Press Setup first.")
            return
        
        self.running = True
        self.receive_frame()

    def ui_pause_event(self):
        logger.debug("Pause button clicked")
        self.text["text"] = "Pause button clicked"
        self.running = False

    def ui_teardown_event(self):
        logger.debug("Teardown button clicked")
        self.text["text"] = "Teardown button clicked"
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None

        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            self.ui_close_window()

    def receive_frame(self):
        if not self.running:
            return
        try:
            data, _ = self.socket.recvfrom(65536) # 64KB buffer
            if data:
                payload = data[12:] # Skip RTP header
                self.updateMovie(payload)
        except socket.timeout: pass
        except OSError as e:
            logger.error(f"Socket error: {e}")
            self.running = False
            messagebox.showerror("Socket Error", f"Socket error: {e}")
            return
            
        self.root.after(30, self.receive_frame)

    def updateMovie(self, data):
        image_source = 'rick.webp' if data is None else io.BytesIO(data)
        try:
            photo = ImageTk.PhotoImage(Image.open(image_source))
            self.movie.configure(image=photo, height=380)
            self.movie.photo_image = photo
        except Exception as e:
            logger.error(f"Failed to update movie: {e}")