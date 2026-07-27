#!/usr/bin/env python3

"""
test.py

print data from LSL inlet to confirm it is working correctly
"""


import time
import numpy as np
from pylsl import StreamInlet, resolve_streams




# 1. Resolve Stream
print("Searching for active LSL streams on local network...")
streams = resolve_streams(wait_time=3.0)

inlet = StreamInlet(streams[0])
print(inlet.info())

print("\nListening for data... Press Ctrl+C to stop.\n")



# Continuous Pull Loop
try:
    while True:
        # Pull chunk with a small timeout to allow network buffer to fill
        samples, timestamps = inlet.pull_chunk(timeout=1.0, max_samples=500)
        
        if timestamps:
            samples_array = np.array(samples)
            print(f"Received {len(timestamps)} samples | Latest: {samples_array[-1]}")
        else:
            print("Waiting for samples...")
            
        # Poll roughly 10 times a second
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nStopped listening.")
