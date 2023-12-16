import time
import tkinter as tk
from tkinter import scrolledtext
from live_transcriber import TranscriptionController
import asyncio # used to run transcription_controller coroutines from tkinter thread using asyncio.run_coroutine_threadsafe
import queue

class AppGUI:
    def __init__(self, transcription_controller: TranscriptionController, asyncio_loop: asyncio.BaseEventLoop, terminate_event: asyncio.Event):
        self.transcription_controller = transcription_controller
        self.asyncio_loop = asyncio_loop
        self.terminate_event = terminate_event
        self.audio_input_dropdowns = []
        self.device_map = {}
        
        # create the main window
        self.root = tk.Tk() 
        self.root.title("My Live Guru")
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.create_widgets()

    def run_mainloop(self):
        self.check_queue()
        self.root.mainloop()
    
    def on_closing(self):
        print("performing cleanup...")
        self.stop_audio_streams()
        
        # terminate asyncio main loop
        self.asyncio_loop.call_soon_threadsafe(self.terminate_event.set)
        
        print("destroying GUI...")
        self.root.destroy()

    def check_queue(self):
        try:
            while True:
                msg_type, msg = self.transcription_controller.results.get_nowait()
                if msg_type == "transcription_msg":
                    self.update_log(msg)
                else:
                    print(f"unknown message type {msg_type}")
                # custom commands:
                if msg.lower().startswith("user: close program"):
                    self.update_log('closing...')
                    self.root.after(1000, self.on_closing)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.check_queue)

    def create_widgets(self):
        # audio input selection
        audio_input_label = tk.Label(self.root, text="User Audio Input")
        audio_input_label.grid(row=0, column=0, padx=10, pady=10)

        audio_input_label = tk.Label(self.root, text="System Audio Input")
        audio_input_label.grid(row=1, column=0, padx=10, pady=10)

        # dropdown for audio input
        self.find_devices()
        device_names = list(self.device_map.keys())
        self.audio_input_dropdowns.append(DeviceSelectDropdown(self.root, 0, 1, device_names, self.stop_audio_streams))
        self.audio_input_dropdowns.append(DeviceSelectDropdown(self.root, 1, 1, device_names, self.stop_audio_streams))

        # start/stop capture button
        self.capture_button = tk.Button(self.root, text="Start Capture", command=self.toggle_capture)
        self.capture_button.grid(row=0, column=3, padx=10, pady=10)

        # transcribed text label
        label_textbox_left = tk.Label(self.root, text="Input Log:", justify='left')
        label_textbox_left.grid(row=2, column=0, padx=10, pady=10)

        label_textbox_right = tk.Label(self.root, text="Guru:", justify='left')
        label_textbox_right.grid(row=2, column=3, padx=10, pady=10)

        # transcribed text box with scrollbar
        self.textbox = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=25, width=60)
        self.textbox.grid(row=3, column=0, padx=10, pady=10, columnspan=3)
        self.textbox.configure(state='disabled')

    def find_devices(self):
        # query and map audio devices
        num_devices = self.transcription_controller.p.get_device_count()
        for i in range(num_devices):
            device_info = self.transcription_controller.p.get_device_info_by_index(i)
            # check for input channels
            if device_info['maxInputChannels'] > 0:
                device_name = f"{str(device_info['index'])}. {device_info['name']}"
                self.device_map[device_name] = device_info['index']
   
    def start_audio_streams(self):
        device_ids = [self.device_map[dropdown.selected_option.get()] for dropdown in self.audio_input_dropdowns]
        asyncio.run_coroutine_threadsafe(self.transcription_controller.start(device_ids), self.asyncio_loop)

    def stop_audio_streams(self):
        future = asyncio.run_coroutine_threadsafe(self.transcription_controller.stop(), self.asyncio_loop)
        future.result() # make UI hang while stopping

    def toggle_capture(self):
        # toggle capture button logic
        if self.transcription_controller.audio_stream_user is None:
            self.start_audio_streams()
            self.capture_button.config(text="Stop Capture")
        else:
            self.stop_audio_streams()
            self.capture_button.config(text="Start Capture")

    def update_log(self, message):
        # update the scrolled text widget with a new message
        def task():
            self.textbox.configure(state='normal')
            self.textbox.insert(tk.END, message + "\n")
            self.textbox.configure(state='disabled')
            self.textbox.see(tk.END)
        self.root.after(0, task)

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
