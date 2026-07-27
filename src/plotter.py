#!/usr/bin/env python3

"""
plotter.py

plot data from LSL inlet to confirm it is working correctly
"""


import sys
import numpy as np
import pyqtgraph as pg
from PySide6 import QtWidgets, QtCore
from pylsl import StreamInlet, resolve_streams

class LSLPlotter(QtWidgets.QMainWindow):
    def __init__(self, time_window=5.0):
        super().__init__()
        self.setWindowTitle("LSL Real-Time Stream Plotter")
        self.resize(1100, 600)

        # 1. Resolve Stream
        print("Searching for active LSL streams on local network...")
        streams = resolve_streams(wait_time=3.0)
        if not streams:
            raise RuntimeError("No active LSL streams found!")

        self.inlet = StreamInlet(streams[0])
        info = self.inlet.info()
        
        self.n_channels = info.channel_count()
        # Fallback to 250Hz if nominal_srate is irregular/unspecified
        self.srate = int(info.nominal_srate()) if info.nominal_srate() > 0 else 250
        self.time_window = time_window
        
        print(f"Connected to '{info.name()}' ({self.n_channels} channels @ {self.srate} Hz)")

        # 2. Data Buffers
        self.buffer_len = int(self.srate * self.time_window)
        self.data_buffer = np.zeros((self.buffer_len, self.n_channels))
        # Time axis relative to present (e.g., -5.0s to 0.0s)
        self.time_axis = np.linspace(-self.time_window, 0, self.buffer_len)

        # 3. Setup PyQT Plot Canvas
        self.plot_widget = pg.PlotWidget()
        self.setCentralWidget(self.plot_widget)
        
        self.plot_widget.setLabel('bottom', 'Time', units='s')
        self.plot_widget.setLabel('left', 'Channels / Amplitude')
        self.plot_widget.showGrid(x=True, y=True, alpha=0.3)
        self.plot_widget.setXRange(-self.time_window, 0)

        # Channel spacing offset (adjust vertical spread based on signal magnitude)
        self.channel_spacing = 2.0  
        self.plot_widget.setYRange(-1, self.n_channels * self.channel_spacing)

        # 4. Create Line Curves for Each Channel
        self.curves = []
        colors = [(0, 200, 255), (255, 100, 100), (100, 255, 100), (255, 200, 0)]
        
        for ch in range(self.n_channels):
            color = colors[ch % len(colors)]
            curve = self.plot_widget.plot(pen=pg.mkPen(color=color, width=1.5))
            self.curves.append(curve)

        # 5. Timer for Real-Time UI Redraw (60 FPS)
        self.timer = QtCore.QTimer()
        self.timer.timeout.connect(self.update_plot)
        self.timer.start(16)

    def update_plot(self):
        # Fetch chunk of available samples from network socket
        samples, _ = self.inlet.pull_chunk(max_samples=200)
        
        if samples:
            samples = np.array(samples)
            num_samples = len(samples)

            # Roll circular buffer and append new data at the end
            self.data_buffer = np.roll(self.data_buffer, -num_samples, axis=0)
            self.data_buffer[-num_samples:, :] = samples

            # Render curves with channel stacking offset
            for ch in range(self.n_channels):
                offset = ch * self.channel_spacing
                stacked_signal = self.data_buffer[:, ch] + offset
                self.curves[ch].setData(self.time_axis, stacked_signal)

if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)
    viewer = LSLPlotter(time_window=5.0)
    viewer.show()
    sys.exit(app.exec_())