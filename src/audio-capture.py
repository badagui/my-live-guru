import sounddevice as sd
import numpy as np
import tkinter as tk
from tkinter import scrolledtext

class AudioStream:
    def __init__(self):
        self.stream = None

    def start_audio_stream(self, device_id, callback):
        # start the audio stream with the selected device
        self.stop_audio_stream()
        self.stream = sd.InputStream(device=device_id, callback=callback)
        self.stream.start()

    def stop_audio_stream(self):
        # stop the stream if already running
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def compute_amplitude(self, indata):
        # basic amplitude for testing
        return np.linalg.norm(indata) * 10

class DeviceSelectDropdown:
    def __init__(self, master, row, col, device_names, device_changed_callback):
        self.device_changed_callback = device_changed_callback
        # creates dropdown for selecting audio input device
        self.selected_option = tk.StringVar(master)
        self.selected_option.set(device_names[0] if device_names else "")
        self.selected_option.trace('w', self.device_changed)
        self.audio_input_dropdown = tk.OptionMenu(master, self.selected_option, *device_names)
        self.audio_input_dropdown.grid(row=row, column=col, padx=10, pady=10)

    def device_changed(self, *args):
        # handle selected device change
        self.device_changed_callback()

class AppGUI:
    def __init__(self, audio_streams):
        self.audio_streams = audio_streams
        self.audio_input_dropdowns = []
        # create the main window
        self.root = tk.Tk() 
        self.root.title("Audio Amplitude GUI")
        self.create_widgets()

    def create_widgets(self):
        # audio input selection
        audio_input_label = tk.Label(self.root, text="User Audio Input")
        audio_input_label.grid(row=0, column=0, padx=10, pady=10)

        audio_input_label = tk.Label(self.root, text="System Audio Input")
        audio_input_label.grid(row=1, column=0, padx=10, pady=10)

        # dropdown for audio input
        self.find_devices()
        for i, _ in enumerate(self.audio_streams):
            self.audio_input_dropdowns.append(DeviceSelectDropdown(self.root, i, 1, self.device_names, self.device_changed_callback))

        # start/stop capture button
        self.capture_button = tk.Button(self.root, text="Start Capture", command=self.toggle_capture)
        self.capture_button.grid(row=0, column=3, padx=10, pady=10)

        # transcribed text label
        label_textbox_left = tk.Label(self.root, text="User Log:", justify='left')
        label_textbox_left.grid(row=2, column=0, padx=10, pady=10)

        label_textbox_right = tk.Label(self.root, text="System Log:", justify='left')
        label_textbox_right.grid(row=2, column=2, padx=10, pady=10)

        # transcribed text box with scrollbar
        self.textbox_left = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=10, width=40)
        self.textbox_left.grid(row=3, column=0, padx=10, pady=10, columnspan=2)
        self.textbox_left.configure(state='disabled')

        self.textbox_right = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=10, width=40)
        self.textbox_right.grid(row=3, column=2, padx=10, pady=10, columnspan=2)
        self.textbox_right.configure(state='disabled')

    def find_devices(self):
        # query and map audio devices
        device_list = sd.query_devices()
        self.device_map = {f"{str(device['index'])}. {device['name']}": device['index'] for device in device_list if device['max_input_channels'] > 0}
        self.device_names = [name for name in self.device_map]
   
    def start_audio_streams(self):
        # start the audio stream with the selected device
        for i, processor in enumerate(self.audio_streams):
            device_id = self.device_map[self.audio_input_dropdowns[i].selected_option.get()]
            processor.start_audio_stream(device_id, lambda indata, frames, time, status, log_box=i: self.audio_callback(indata, frames, time, status, log_box))

    def stop_audio_streams(self):
        for processor in self.audio_streams:
            processor.stop_audio_stream()

    def toggle_capture(self):
        # toggle capture button logic
        if self.audio_streams[0].stream is None:
            self.start_audio_streams()
            self.capture_button.config(text="Stop Capture")
        else:
            self.stop_audio_streams()
            self.capture_button.config(text="Start Capture")

    def device_changed_callback(self):
        if self.audio_streams[0].stream is not None:
            self.start_audio_streams()

    def audio_callback(self, indata, frames, time, status, log_box):
        # callback function for audio streams
        if status:
            self.update_log(log_box, f"status: {str(status)}")
        prefix = "User:" if log_box == 0 else "System:"
        amplitude = self.audio_streams[0].compute_amplitude(indata)
        log_message = f"{prefix} {amplitude:.2f}"
        self.update_log(log_box, log_message)

    def update_log(self, log_box, message):
        # update the scrolled text widget with a new message
        def task():
            textbox = self.textbox_left if log_box == 0 else self.textbox_right
            textbox.configure(state='normal')
            textbox.insert(tk.END, message + "\n")
            textbox.configure(state='disabled')
            textbox.see(tk.END)

        self.root.after(0, task)

    def run(self):
        self.root.mainloop()

audio_stream_user = AudioStream()
audio_stream_sys = AudioStream()
app = AppGUI((audio_stream_user, audio_stream_sys))
app.run()
