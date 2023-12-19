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
                msg_type, msg = self.transcription_controller.final_results.get_nowait()
                if msg_type == "user_msg":
                    self.update_log(msg, "#004000")
                elif msg_type == "system_msg":
                    self.update_log(msg, "#000050")
                else:
                    print(f"unknown message type {msg_type}")
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
        device_names = [x for x in self.device_map.keys() if x != 'None']
        device_names.insert(0, 'None') # make 'None' first element
        self.audio_input_dropdowns.append(DeviceSelectDropdown(self.root, 0, 1, device_names, self.stop_audio_streams))
        self.audio_input_dropdowns.append(DeviceSelectDropdown(self.root, 1, 1, device_names, self.stop_audio_streams))

        # language dropdown
        languages = ["en-US", "en-GB", "en-AU", "en-IN", "en-CA", "en-NZ"]
        self.selected_language = tk.StringVar(self.root)
        self.selected_language.set("en-US")
        self.selected_language.trace_add('write', self.language_changed)
        language_dropdown = tk.OptionMenu(self.root, self.selected_language, *languages)
        language_dropdown.grid(row=1, column=3, padx=10, pady=10)

        # start/stop capture button
        self.capture_button = tk.Button(self.root, text="Start Capture", command=self.toggle_capture)
        self.capture_button.grid(row=0, column=3, padx=10, pady=10)

        # transcribed text label
        label_textbox_left = tk.Label(self.root, text="Input Log:", justify='left')
        label_textbox_left.grid(row=2, column=0, padx=10, pady=10)

        label_textbox_right = tk.Label(self.root, text="Guru:", justify='left')
        label_textbox_right.grid(row=2, column=3, padx=10, pady=10)

        # transcribed text box
        self.textbox_left = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=25, width=50)
        self.textbox_left.grid(row=3, column=0, padx=10, pady=10, columnspan=3)
        self.textbox_left.configure(state='disabled')

        # AI text box
        self.textbox_right = scrolledtext.ScrolledText(self.root, wrap=tk.WORD, height=25, width=50)
        self.textbox_right.grid(row=3, column=3, padx=10, pady=10, columnspan=3)
        self.textbox_right.configure(state='disabled')

    def find_devices(self):
        # query and map audio devices
        num_devices = self.transcription_controller.p.get_device_count()
        for i in range(num_devices):
            device_info = self.transcription_controller.p.get_device_info_by_index(i)
            # check for input channels
            if device_info['maxInputChannels'] > 0:
                # create device name
                device_name = f"{str(device_info['index'])}. {device_info['name']}"
                # set local data
                self.device_map[device_name] = device_info['index']
                self.device_map['None'] = None
   
    def start_audio_streams(self):
        # get selected
        device_ids = [self.device_map[dropdown.selected_option.get()] for dropdown in self.audio_input_dropdowns]
        # remove None values
        device_ids = [x for x in device_ids if x is not None]
        if (len(device_ids) == 0):
            print("no audio input devices selected")
            return
        language = self.selected_language.get()
        asyncio.run_coroutine_threadsafe(self.transcription_controller.start(device_ids, language), self.asyncio_loop)
        self.capture_button.config(text="Stop Capture")

    def stop_audio_streams(self):
        future = asyncio.run_coroutine_threadsafe(self.transcription_controller.stop(), self.asyncio_loop)
        future.result() # make UI hang while stopping
        self.capture_button.config(text="Start Capture")

    def toggle_capture(self):
        # toggle capture button logic
        if self.transcription_controller.audio_stream_user is None:
            self.start_audio_streams()
        else:
            self.stop_audio_streams()

    def update_log(self, message, color='black'):
        # update the scrolled text widget with a new message
        def task():
            self.textbox_left.configure(state='normal')
            
            # Use color code as the tag name
            color_tag = f"color_{color}"
            if color_tag not in self.textbox_left.tag_names():
                self.textbox_left.tag_configure(color_tag, foreground=color)

            # insert text with the color tag
            self.textbox_left.insert(tk.END, message, color_tag)

            self.textbox_left.configure(state='disabled')
            self.textbox_left.see(tk.END)
        self.root.after(0, task)

    def language_changed(self, *args):
        print(f"language changed to {self.selected_language.get()}")

class DeviceSelectDropdown:
    def __init__(self, master, row, col, device_names, device_changed_callback):
        self.device_changed_callback = device_changed_callback
        # creates dropdown for selecting audio input device
        self.selected_option = tk.StringVar(master)
        self.selected_option.set(device_names[0] if device_names else "")
        self.selected_option.trace_add('write', self.device_changed)
        self.audio_input_dropdown = tk.OptionMenu(master, self.selected_option, *device_names)
        self.audio_input_dropdown.grid(row=row, column=col, padx=10, pady=10)

    def device_changed(self, *args):
        # handle selected device change
        self.device_changed_callback()
