import sounddevice as sd
import numpy as np
import tkinter as tk
from tkinter import scrolledtext

class AudioProcessor:
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

class AudioAmplitudeGUI:
    def __init__(self, audio_processor):
        self.audio_processor = audio_processor
        self.audio_input_dropdown = None
        # create the main window
        self.root = tk.Tk() 
        self.root.title("Audio Amplitude GUI")
        self.create_widgets()

    def create_widgets(self):
        # audio input selection
        audio_input_label = tk.Label(self.root, text="Select Audio Input")
        audio_input_label.grid(row=0, column=0, padx=10, pady=10)

        # dropdown for audio input
        self.create_device_dropdown()

        # refresh button to update device list
        refresh_button = tk.Button(self.root, text="Refresh Device List", command=self.refresh_device_dropdown)
        refresh_button.grid(row=0, column=2, padx=10, pady=10)

        # start/stop capture button
        self.capture_button = tk.Button(self.root, text="Start Capture", command=self.toggle_capture)
        self.capture_button.grid(row=0, column=3, padx=10, pady=10)

        # transcribed text label
        transcribed_text_label = tk.Label(self.root, text="Amplitude Log:")
        transcribed_text_label.grid(row=1, column=0, padx=10, pady=10)

        # transcribed text box with scrollbar
        self.transcribed_text_box = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=10, width=40)
        self.transcribed_text_box.grid(row=1, column=1, padx=10, pady=10)
        self.transcribed_text_box.configure(state='disabled')

    def find_devices(self):
        # query and map audio devices
        device_list = sd.query_devices()
        self.device_map = {f"{str(device['index'])}. {device['name']}": device['index'] for device in device_list}
        device_names = [f"{str(device['index'])}. {device['name']}" for device in device_list]
        return device_names

    def create_device_dropdown(self):
        # creates dropdown for selecting audio input device
        if self.audio_input_dropdown is not None:
            return
        self.selected_option = tk.StringVar(self.root)
        device_names = self.find_devices()
        self.selected_option.set(device_names[0] if device_names else "")
        self.selected_option.trace('w', self.device_changed)
        self.audio_input_dropdown = tk.OptionMenu(self.root, self.selected_option, *device_names)
        self.audio_input_dropdown.grid(row=0, column=1, padx=10, pady=10)
            

    def refresh_device_dropdown(self):
        # refreshes the dropdown device list
        current_selection = self.selected_option.get() if self.selected_option else None
        device_names = self.find_devices()
        self.audio_input_dropdown['menu'].delete(0, 'end')
        for name in device_names:
            self.audio_input_dropdown['menu'].add_command(label=name, command=lambda value=name: self.selected_option.set(value))
        self.selected_option.set(current_selection if current_selection in device_names else device_names[0] if device_names else "")
        self.device_changed()

    def device_changed(self, *args):
        # handle selected device change
        if self.audio_processor.stream is not None:
            self.stop_audio_stream()
            self.start_audio_stream()

    def start_audio_stream(self):
        # start the audio stream with the selected device
        device_id = self.device_map[self.selected_option.get()]
        self.audio_processor.start_audio_stream(device_id, self.audio_callback)

    def stop_audio_stream(self):
        self.audio_processor.stop_audio_stream()

    def toggle_capture(self):
        # toggle capture button logic
        if self.audio_processor.stream is None:
            self.start_audio_stream()
            self.capture_button.config(text="Stop Capture")
        else:
            self.stop_audio_stream()
            self.capture_button.config(text="Start Capture")

    def audio_callback(self, indata, frames, time, status):
        # callback function for audio stream
        if status:
            self.update_log(str(status))
        amplitude = self.audio_processor.compute_amplitude(indata)
        log_message = f"Current amplitude: {amplitude:.2f}"
        self.update_log(log_message)


    def update_log(self, message):
        # update the scrolled text widget with a new message
        def task():
            self.transcribed_text_box.configure(state='normal')
            self.transcribed_text_box.insert(tk.END, message + "\n")
            self.transcribed_text_box.configure(state='disabled')
            self.transcribed_text_box.see(tk.END)
        self.root.after(0, task)

    def run(self):
        self.root.mainloop()

audio_processor = AudioProcessor()
app = AudioAmplitudeGUI(audio_processor)
app.run()
