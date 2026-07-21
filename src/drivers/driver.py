import threading
import yaml
from core.engine import Engine


class Device:

    def __init__(self, config_file):

        with open(config_file, 'r') as f:
            self.params = yaml.safe_load(f)

        self.engine = Engine(self.params["network"]["device_ip"], self.params["network"]["device_control_port"], self.params["network"]["device_data_port"],
                            self.params["network"]["local_ip"], self.params["network"]["local_control_port"], self.params["network"]["local_data_port"])
        self._stop_event = threading.Event()

    
    def send_command(self, command):
        '''send command to the board'''
        self.engine.control_tx_queue.append(command)


    def start(self):
        '''start the board and all of the listening/processing threads'''

        self.engine.start()
        self._stop_event.clear()

        self.control_tx_monitor_thread = threading.Thread(target=self._monitor_control_tx_queue, daemon=True)           # define the threads
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


    def _monitor_control_tx_queue(self):
        '''print received control commands from the device'''

        while not self._stop_event.is_set():
            try:
                command = self.engine.control_tx_queue.popleft(timeout=0.5)
            except TimeoutError:
                continue
            print(command)


    def _heartbeat(self):
        '''periodically send heartbeat command to keep device on'''
        
        while not self._stop_event.is_set():
            self.send_command(bytes.fromhex(self.params["protocol_settings"]["heartbeat"]["payload_hex"]))
            self._stop_event.wait(timeout=self.params["protocol_settings"]["heartbeat"]["interval_sec"])
    
    def _unpack_data_rx_queue(self):
        '''unpack raw bytes from udp packets and convert to numpy datatypes on demand'''

        while not self._stop_event.is_set():
            try:
                data = self.engine.data_rx_queue.popleft(timeout=0.5)
            except TimeoutError:
                continue

            self.engine.out_tx_queue.append(self._parse_data(data))

    
    def _parse_data(self, data):
        '''convert raw network packets to numpy datatype'''

        return np.frombuffer(data, dtype=self.params["dtype"])


