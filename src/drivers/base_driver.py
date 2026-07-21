import queue
import socket
from abc import ABC, abstractmethod

class BaseUDPDriver(ABC):
    """
    Abstract Base Class defining the mandatory interface for all 
    UDP hardware drivers in the LSL Server Architecture.
    """
    
    @abstractmethod
    def __init__(self, config: dict, data_queue: queue.Queue):
        """Configure instance variables, pre-allocate buffers, and store queue reference."""
        self.config = config
        self.data_queue = data_queue
        self.is_running = False
        super().__init__()

    @abstractmethod
    def start(self):
        """Bind sockets, spin up worker threads, and start ingesting data."""
        pass

    @abstractmethod
    def stop(self):
        """Safely wind down threads, close sockets, and alert external hardware if needed."""
        pass

    @abstractmethod
    def parse_packet(self, raw_bytes: bytes) -> list or None:
        """
        Core translation engine. 
        Takes raw network bytes, extracts values, applies calibration, 
        and returns a clean, flat list of numbers matching the LSL channels.
        """
        pass

    @abstractmethod
    def process_heartbeat(self, sock: socket.socket):
        """Sends keep-alive commands or state inquiries directly to the target hardware."""
        pass
        
    def get_status(self) -> dict:
        """Default diagnostic reporting hook. Override if extra telemetry is needed."""
        return {"driver_active": self.is_running}