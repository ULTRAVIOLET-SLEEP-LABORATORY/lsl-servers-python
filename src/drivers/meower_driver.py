from .driver import BaseDriver
from pylsl import StreamInfo, StreamOutlet, local_clock
import numpy as np




class MeowerLSLDriver(BaseDriver):

    def __init__(self, config_file):
        '''Driver that manages a Meower EEG device and implements LSL streaming'''

        super().__init__(config_file)

        # load some parameters for parsing packets
        self.batt_len = self.params["protocol_settings"]["packet"]["battery"]["length"]            # no. bytes for reporting battery voltage
        self.battery_dtype = self.params["protocol_settings"]["packet"]["battery"]["format"]
        self.timestamp_tick = self.params["protocol_settings"]["packet"]["body"]["timestamp"]["scale_factor"]
        self.data_scale = self.params["protocol_settings"]["packet"]["body"]["scale_factor"]


        # initialize some variables for the LSL stream
        self._lsl_time_offset = None                     # Track anchor time offset if mapping hardware timestamps
        self.data_info = StreamInfo(
            name=self.params["lsl_stream_eeg"]["name"],
            type=self.params["lsl_stream_eeg"]["type"],
            channel_count=self.params["lsl_stream_eeg"]["channel_count"],
            nominal_srate=self.params["lsl_stream_eeg"]["nominal_srate"],
            channel_format=self.params["lsl_stream_eeg"]["channel_format"],
            source_id=self.params["lsl_stream_eeg"]["source_id"]
        )


        # Dedicated Battery Stream (1 channel @ Irregular rate)
        self.batt_info = StreamInfo(
            name=self.params["lsl_stream_battery"]["name"],
            type=self.params["lsl_stream_battery"]["type"],
            channel_count=self.params["lsl_stream_battery"]["channel_count"],
            nominal_srate=self.params["lsl_stream_battery"]["nominal_srate"],  # 0.0 indicates irregular / chunked sample rate
            channel_format=self.params["lsl_stream_battery"]["channel_format"],
            source_id=self.params["lsl_stream_battery"]["source_id"]
        )


        # Create the outlet that broadcasts the stream on the local network
        self.data_outlet = StreamOutlet(self.data_info)
        self.battery_outlet = StreamOutlet(self.batt_info)
        print(f"LSL Stream '{self.data_info.name()}' initialized and broadcasting...")
        print(f"LSL Stream '{self.batt_info.name()}' initialized and broadcasting...")

        self.engine.ostream.append(self._publish_lsl)       # bind the streamer as a callback for the Engine to push parsed data to lsl




    def _parse_packet(self, packet_bytes: bytes) -> dict:
            """Parses a UDP packet with N x 52-byte frames + 4-byte float32 battery trailer.

            :param packet_bytes: Raw bytes received from the socket.
            :param endianness: Byte order of the payload ('little' or 'big'). Default is 'little'.
            :return: tuple containing 'channels' (N, 16), 'timestamps' (N,), and 'battery' (float).
            """

            # Validation
            total_len = len(packet_bytes)
            if total_len < 4 or (total_len - 4) % 52 != 0:
                raise ValueError(
                    f"Invalid packet length ({total_len} bytes). Must be (N * 52) + 4."
                )

            # 1. Zero-copy wrapper as an array of bytes
            buffer = np.frombuffer(packet_bytes, dtype=np.uint8)

            # 2. Extract 4-byte float32 Battery Trailer
            battery_bytes = buffer[-1*self.batt_len:]
            battery_val = float(battery_bytes.view(self.battery_dtype)[0])

            # 3. Reshape frame buffer into [N_frames, 52]
            num_frames = (total_len - self.batt_len) // 52
            frames = buffer[:-4].reshape(num_frames, 52)

            # 4. Extract Timestamps (Last 4 bytes of each frame: columns 48..51)
            # Reinterpret columns directly as uint32 using strided memory views
            timestamp_bytes = frames[:, 48:52].ravel()
            ts_dtype = "<I"
            timestamps = timestamp_bytes.view(ts_dtype) * self.timestamp_tick

            # 5. Extract & Sign-Extend 24-bit 2's Complement Channels
            # Shape raw channels to [N_frames, 16_channels, 3_bytes]
            raw_channels = frames[:, :48].reshape(num_frames, 16, 3)

            # Cast to uint32 for bitwise manipulation
            b0 = raw_channels[:, :, 0].astype(np.uint32)
            b1 = raw_channels[:, :, 1].astype(np.uint32)
            b2 = raw_channels[:, :, 2].astype(np.uint32)

            # Big endian data
            # b0 is MSB, b2 is LSB
            raw_24 = (b0 << 24) | (b1 << 16) | (b2 << 8)

            # Cast container to SIGNED int32, then arithmetic right-shift by 8 bits
            # This automatically propagates the 24th bit (sign bit) across the top byte
            channels = (raw_24.astype(np.int32) >> 8) * self.data_scale

            return {
                "timestamps": timestamps,  # Shape: (N,)    - uint32
                "channels": channels,  # Shape: (N, 16) - int32
                "battery": battery_val,  # Scalar      - float
            }

    
    def _publish_lsl(self, parsed_data: dict) -> None:
        """Pushes parsed channels and timestamps to the LSL outlet.

        Anchors the 8 µs hardware clock to pylsl.local_clock().
        """
        channels = parsed_data.get("channels")  # Shape: (N, 16)
        hw_timestamps = parsed_data.get("timestamps")  # Shape: (N,) in seconds

        # Guard against empty packets or corrupted frames
        if channels is None or channels.size == 0:
            return

        # 1. Anchor Hardware Clock to LSL Clock on the very first packet
        if self._lsl_time_offset is None:
            self._lsl_time_offset = local_clock() - hw_timestamps[0]             # local_clock() gets current LSL time in seconds. Subtract initial hardware timestamp to get relative offset

        # 2. Synchronize all hardware timestamps to LSL time
        lsl_timestamps = hw_timestamps + self._lsl_time_offset

        # 3. Vectorized push to LSL Outlet
        # outlet.push_chunk expects:
        #   x: 2D numpy array (num_samples, num_channels)
        #   timestamps: list of floats matching each sample's LSL timestamp
        self.data_outlet.push_chunk(x=channels, timestamp=lsl_timestamps.tolist())

        # 4. Push battery voltage to LSL battery stream.
        battery = parsed_data.get("battery")
        if battery is not None:
            latest_timestamp = lsl_timestamps[-1]
            self.battery_outlet.push_sample([battery], timestamp=latest_timestamp)