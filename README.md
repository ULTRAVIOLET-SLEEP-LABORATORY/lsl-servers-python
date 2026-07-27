# lsl-servers-python
Rebroadcast udp biosensor streams over LSL (lab streaming layer).


lsl-servers-python is a Python-based framework designed to bridge raw UDP hardware communication and the Lab Streaming Layer (LSL) for biosensor data ingestion and streaming.

It decouples the low-level network transport from device-specific data parsing, allowing rapid integration of new biopotential or sensor hardware (EEG, ECG, EMG, IMUs, etc.).

It is designed so that much of the functionality is defined in a .yaml file (and overwriting methods of the BaseDriver).



# Core Architecture
The framework relies on an Engine–Driver architecture to separate networking mechanics from device payload logic:

+-----------------------------------------------------------------------+
|                                Driver                                 |
|  - Configured by YAML file                                            |
|  - Holds device-specific logic, payload parsing, & control commands  |
+-----------------------------------+-----------------------------------+
                                    | owns
                                    v
+-----------------------------------------------------------------------+
|                                Engine                                 |
|  - Manages low-level UDP socket binding & LSL StreamOutlets/Inlets    |
|  - Handles async thread/queue processing for incoming/outgoing packets|
+-----------------------------------------------------------------------+
        ^                                                   ^
        | UDP Packets                                       | LSL Outlets
        v                                                   v
   [ Biosensor ]                                   [ LSL Network / Apps ]



## 1. The Engine
Role: Network & Stream Transport Interface.

Responsibilities:

Manages UDP socket lifecycle (binding, listening, writing).

Enqueues incoming UDP payloads and dequeues outgoing command packets via thread-safe queues.

Interfacing with pylsl to create and push data to LSL StreamOutlet instances (or pull from StreamInlet).

### Engine
The engine is structured around 2 websockets and 4 queues. One socket is for data and the other is for
control/telemetry. The control socket has two queues associated with it: one for sending commands and the other
for storing received commands. The data socket has one queue to store received data. Finally, there is a queue
for storing parsed data that is ready to be streamed over LSL. Each queue is monitored by a thread, and 
awakens to process data whenever there is any in the queue.

It is possible that this project is not robust enough for some setups. Perhaps some projects require the ability 
to send data to the biosensors which this currently cannot do. However, most of this could be done with a little
more thought and code i.e. adding another queue and passing callback function around.



## 2. The Driver
Role: Device Logic & Controller.

Responsibilities:

Owns the Engine instance.

Configured via .yaml files (e.g., sample rates, channel names, IP/Port settings, chunk sizes).

Translates raw binary/UDP packets into structured numeric samples (and vice versa).

Provides extensible hook methods (parse_packet, on_start, send_command, etc.) that can be overridden per device.

### Driver
The Driver implements the high level logic about what command to send to the biosensors, and how to process 
received data. The Driver spawns three threads. One to monitor telemetry sent from devices, one to send the 
"heartbeat" keep alive control signals, and one to process received data. Some of the Driver methods are intended 
to be overwritten, especially _parse_packet(), since this changes on a per-device basis.

I also want to add functionality for direct communication of devices from the terminal.