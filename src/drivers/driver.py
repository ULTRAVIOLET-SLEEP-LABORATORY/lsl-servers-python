from abc import ABC, abstractmethod
import threading
import yaml
from core.engine import Engine
import numpy as np
import struct


class BaseDriver(ABC):

    def __init__(self, config_file):

        with open(config_file, 'r') as f:
            self.params = yaml.safe_load(f)

        self.engine = Engine(self.params["network"]["device_ip"], self.params["network"]["device_control_port"], self.params["network"]["device_data_port"],
                            self.params["network"]["local_ip"], self.params["network"]["local_control_port"], self.params["network"]["local_data_port"])
        self._stop_event = threading.Event()

    
    def send_command(self, command):
        '''Queue up commands to send to the board'''
        self.engine.control_tx_queue.append(command)


    def start(self):
        '''start the board and all of the listening/processing threads'''

        self.engine.start()
        self._stop_event.clear()

        self.control_tx_monitor_thread = threading.Thread(target=self._monitor_control_rx_queue, daemon=True)           # define the threads
        self.heartbeat_thread = threading.Thread(target=self._heartbeat, daemon=True)
        self.unpack_data_thread = threading.Thread(target=self._unpack_data_rx_queue, daemon=True)

        self.control_tx_monitor_thread.start()          # start all of the threads
        self.heartbeat_thread.start()
        self.unpack_data_thread.start()

        self.send_command(self.params["commands"]["start_stream"].encode('ascii'))      # tell the board to start streaming


    def stop(self):
        '''stop the board from streaming'''

        self.send_command(self.params["commands"]["stop_stream"].encode('ascii'))

        self._stop_event.set()

        for t in (self.control_tx_monitor_thread, self.heartbeat_thread, self.unpack_data_thread):
            t.join(timeout=2.0)


    def _monitor_control_rx_queue(self):
        '''print received control commands from the device'''

        while not self._stop_event.is_set():
            try:
                command = self.engine.control_rx_queue.popleft(timeout=0.5)
            except TimeoutError:
                continue
            print("[Device: Monitor Control RX Queue] Received: ", command)


    def _heartbeat(self):
        '''periodically send heartbeat command to keep device on'''
        
        while not self._stop_event.is_set():
            self.send_command(self.params["commands"]["heartbeat"].encode('ascii'))
            self._stop_event.wait(timeout=self.params["protocol_settings"]["heartbeat"]["interval_sec"])
    
    def _unpack_data_rx_queue(self):
        '''unpack raw bytes from udp packets and convert to numpy datatypes on demand'''

        while not self._stop_event.is_set():
            try:
                data = self.engine.data_rx_queue.popleft(timeout=0.5)
            except TimeoutError:
                continue

            self.engine.out_tx_queue.append(self._parse_packet(data))



    @abstractmethod
    def _parse_packet(self, raw_bytes: bytes) -> dict:
        """Override this in a subclass to implement protocol-specific unpacking.

        Must return a dict with:
          - 'channels': np.ndarray of shape (N, num_channels)
          - 'timestamps': np.ndarray of relative times in seconds (N,)
          - 'metadata': optional dict (battery, packet counter, etc.)
        """
        pass

    


