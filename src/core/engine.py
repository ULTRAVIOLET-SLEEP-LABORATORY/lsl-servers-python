



import socket
import threading
from collections import deque


class Engine:
    '''Engine for network operations and data structures.
    Manages queues.'''

    def __init__(self, device_ip, device_control_port, device_data_port, local_ip, local_control_port, local_data_port):
        '''Initialize all of the networking sockets and queues'''

        self.MAX_UDP_SIZE = 65535
        self.device_ip = device_ip
        self.device_control_port = device_control_port
        self.device_data_prot = device_data_port
        self.local_ip = local_ip
        self.local_control_port = local_control_port
        self.local_data_port = local_data_port

        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)          # create control socket
        self.control_socket.bind((local_ip, local_control_port))                                          # set control socket address
        self.control_rx_queue = BlockingDeque(maxlen=100)                                           # create control receive queue
        self.control_tx_queue = BlockingDeque(maxlen=100)                                           # create control send queue

        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)             # create data socket
        self.data_socket.bind((local_ip, local_data_port))                                               # set data socket address
        self.data_rx_queue = BlockingDeque(maxlen=100)                                              # create data receive queue
        self.out_tx_queue = BlockingDeque(maxlen=100)                                               # create generic out queue

        # placeholder — swap for a real pylsl StreamOutlet before this is used
        self.lsl_socket = None

        self._stop_event = threading.Event()
        self._recv_timeout = 0.5  # seconds; lets loops check _stop_event periodically
        self.control_socket.settimeout(self._recv_timeout)
        self.data_socket.settimeout(self._recv_timeout)


    def start(self):
        '''start all of the threads'''
        self._stop_event.clear()

        self.control_rx_thread = threading.Thread(target=self._run_control_rx_queue, daemon=True)
        self.control_tx_thread = threading.Thread(target=self._run_control_tx_queue, daemon=True)
        self.data_rx_thread = threading.Thread(target=self._run_data_rx_queue, daemon=True)
        self.out_tx_thread = threading.Thread(target=self._run_out_tx_queue, daemon=True)

        self.control_rx_thread.start()
        self.control_tx_thread.start()
        self.data_rx_thread.start()
        self.out_tx_thread.start()

    def stop(self):
        self._stop_event.set()

        for t in (self.control_rx_thread, self.control_tx_thread, self.data_rx_thread, self.out_tx_thread):
            t.join(timeout=2.0)

        self.control_socket.close()
        self.data_socket.close()

    def _run_control_rx_queue(self):
        '''listen to the control socket and push to the control queue'''

        while not self._stop_event.is_set():
            try:
                received_command, _addr = self.control_socket.recvfrom(self.MAX_UDP_SIZE)
            except socket.timeout:
                continue
            self.control_rx_queue.append(received_command)


    def _run_control_tx_queue(self):
        '''listen to the control queue and send commands to board via socket'''

        while not self._stop_event.is_set():
            try:
                command = self.control_tx_queue.popleft(timeout=self._recv_timeout)
            except TimeoutError:
                continue
            self.control_socket.sendto(command, (self.device_ip, self.device_control_port))


    def _run_data_rx_queue(self):
        '''listen to data socket and push data asap to data queue for processing'''

        while not self._stop_event.is_set():
            try:
                received_data, _addr = self.data_socket.recvfrom(self.MAX_UDP_SIZE)
            except socket.timeout:
                continue
            self.data_rx_queue.append(received_data)


    def _run_out_tx_queue(self):
        '''listen to the out queue and send data out via lsl'''

        while not self._stop_event.is_set():
            try:
                data = self.out_tx_queue.popleft(timeout=self._recv_timeout)
            except TimeoutError:
                continue
            self.lsl_socket.send(data)







class BlockingDeque:
    '''Deque that blocks read on empty'''

    def __init__(self, maxlen=None):
        self._buffer = deque(maxlen=maxlen)
        self._cond = threading.Condition()

    def append(self, item):
        with self._cond:
            self._buffer.append(item)
            self._cond.notify()          # wake one waiting reader

    def popleft(self, timeout=None):
        with self._cond:
            # wait_for re-checks the condition each time notify() fires,
            # and releases the lock while waiting so append() can proceed
            if not self._cond.wait_for(lambda: len(self._buffer) > 0, timeout=timeout):
                raise TimeoutError
            return self._buffer.popleft()