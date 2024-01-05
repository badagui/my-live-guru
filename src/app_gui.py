import time
import tkinter as tk
from tkinter import scrolledtext
from live_transcriber import TranscriptionController
from gpt_controller import GPTController
import asyncio # used to run transcription_controller coroutines from tkinter thread using asyncio.run_coroutine_threadsafe
import queue
from tkinter import ttk
from prompts import base_prompts
import tiktoken

class AppGUI:
    def __init__(self, transcription_controller: TranscriptionController, gpt_controller: GPTController, asyncio_loop: asyncio.BaseEventLoop, terminate_event: asyncio.Event):
        self.transcription_controller = transcription_controller
        self.gpt_controller = gpt_controller
        self.asyncio_loop = asyncio_loop
        self.terminate_event = terminate_event
        self.audio_input_dropdowns = []
        self.device_map = {}
        
        # create the main window
        self.root = tk.Tk() 
        self.root.title("My Live Guru")
        self.root.protocol("WM_DELETE_WINDOW", self.close_program)
        self.create_widgets()

    def run_mainloop(self):
        self.consume_transcription()
        self.consume_ai_answer()
        self.root.mainloop()
    
    def close_program(self):
        print("performing cleanup...")
        # stop transcription controller
        self.stop_transcription()
        
        # stop asyncio main loop
        self.asyncio_loop.call_soon_threadsafe(self.terminate_event.set)
        
        # terminate GUI
        self.root.destroy()

    def consume_transcription(self):
        try:
            while True:
                msg_type, msg = self.transcription_controller.transcriptions_queue.get_nowait()
                if msg_type == "user_msg":
                    self.update_log(msg, "#004000")
                elif msg_type == "system_msg":
                    self.update_log(msg, "#000050")
                else:
                    print(f"unknown message type {msg_type}")
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.consume_transcription)
    
    def consume_ai_answer(self):
        try:
            while True:
                ai_chunk = self.gpt_controller.queue.get_nowait()
                self.textbox_right.configure(state='normal')
                self.textbox_right.insert(tk.END, ai_chunk)
                self.textbox_right.configure(state='disabled')
                self.textbox_right.see(tk.END)
        except queue.Empty:
            pass
        finally:
            self.root.after(100, self.consume_ai_answer)

    def create_widgets(self):
         # tabs widget
        self.notebook = ttk.Notebook(self.root)
        self.notebook.grid(row=0, column=0, columnspan=4)

        # first tab
        self.tab1 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab1, text='Main')

        # audio input selection
        audio_input_label = tk.Label(self.tab1, text="User Input")
        audio_input_label.grid(row=0, column=0, padx=5, pady=5)

        audio_input_label = tk.Label(self.tab1, text="System Loopback")
        audio_input_label.grid(row=1, column=0, padx=5, pady=5)

        # dropdown for audio input
        self.find_devices()
        device_names = [x for x in self.device_map.keys() if x != 'None']
        device_names.insert(0, 'None') # make 'None' first element
        self.audio_input_dropdowns.append(DeviceSelectDropdown(self.tab1, 0, 1, device_names, self.stop_transcription))
        self.audio_input_dropdowns.append(DeviceSelectDropdown(self.tab1, 1, 1, device_names, self.stop_transcription))

        # language selection dropdown
        languages = ["en", "en-US", "en-AU", "en-GB", "en-NZ", "en-IN", "fr", "fr-CA", "de", "hi", "hi-Latn", "pt", "pt-BR", "es", "es-419"]
        self.selected_language = tk.StringVar(self.tab1)
        self.selected_language.set("en-US")
        self.selected_language.trace_add('write', self.language_changed)
        language_dropdown = tk.OptionMenu(self.tab1, self.selected_language, *languages)
        language_dropdown.grid(row=1, column=2, padx=5, pady=5)

        # start/stop capture button
        self.capture_button = tk.Button(self.tab1, text="Start Capture", command=self.toggle_capture)
        self.capture_button.grid(row=0, column=2, padx=5, pady=5)

        # ask guru button
        self.ask_guru_button = tk.Button(self.tab1, text="ASK\nGURU", command=self.ask_guru)
        self.ask_guru_button.grid(row=0, column=4, padx=20, pady=20, columnspan=3, rowspan=2, ipadx=20, ipady=20)

        # transcribed text label
        label_textbox_left = tk.Label(self.tab1, text="Input Log:", justify='left')
        label_textbox_left.grid(row=2, column=0, padx=5, pady=5)

        label_textbox_right = tk.Label(self.tab1, text="Guru:", justify='left')
        label_textbox_right.grid(row=2, column=4, padx=5, pady=5)

        # transcribed text box
        self.textbox_left = scrolledtext.ScrolledText(self.tab1, wrap=tk.WORD, height=25, width=50)
        self.textbox_left.grid(row=3, column=0, padx=5, pady=5, columnspan=3, sticky='nsew')
        # self.textbox_left.configure(state='disabled') ### testing editable log transcript

        # clear log button
        self.clear_log_button = tk.Button(self.tab1, text="Clear Log", command=self.clear_log)
        self.clear_log_button.grid(row=4, column=0, padx=5, pady=0)

        # AI text box
        self.textbox_right = scrolledtext.ScrolledText(self.tab1, wrap=tk.WORD, height=25, width=50)
        self.textbox_right.grid(row=3, column=4, padx=10, pady=10, columnspan=2, sticky='nsew')
        self.textbox_right.configure(state='disabled')

        # second tab
        self.tab2 = ttk.Frame(self.notebook)
        self.notebook.add(self.tab2, text='Stage')

        # base prompt textbox
        self.textbox_base_prompt = scrolledtext.ScrolledText(self.tab2, wrap=tk.WORD, height=30, width=100, background='#f0f0f0')
        self.textbox_base_prompt.grid(row=1, column=0, padx=10, pady=10, columnspan=5,  sticky='nsew')
        
        # base prompt text
        base_prompt = base_prompts['interview_candidate']
        self.textbox_base_prompt.insert(tk.INSERT, base_prompt)
        self.textbox_base_prompt.configure(state='disabled', background='#f0f0f0')

        # edit / save button
        self.edit_save_button = tk.Button(self.tab2, text="Edit", command=self.toggle_prompt_edit_save)
        self.edit_save_button.grid(row=2, column=0, padx=5, pady=5)

        # default prompts buttons
        prompt2_button = tk.Button(self.tab2, text="The Perfect Candidate", command=lambda: self.toggle_prompt('interview_candidate'))
        prompt2_button.grid(row=0, column=0, padx=5, pady=5)
        prompt1_button = tk.Button(self.tab2, text="The Perfect Interviewer", command=lambda: self.toggle_prompt('interview_host'))
        prompt1_button.grid(row=0, column=1, padx=5, pady=5)
        prompt3_button = tk.Button(self.tab2, text="The Perfect Salesperson", command=lambda: self.toggle_prompt('salesperson'))
        prompt3_button.grid(row=0, column=2, padx=5, pady=5)
        prompt4_button = tk.Button(self.tab2, text="Easy Customer", command=lambda: self.toggle_prompt('customer_easy'))
        prompt4_button.grid(row=0, column=3, padx=5, pady=5)
        prompt5_button = tk.Button(self.tab2, text="Hard Customer", command=lambda: self.toggle_prompt('customer_hard'))
        prompt5_button.grid(row=0, column=4, padx=5, pady=5)


    def find_devices(self):
        # query and map audio input devices
        num_devices = self.transcription_controller.p.get_device_count()
        for i in range(num_devices):
            device_info = self.transcription_controller.p.get_device_info_by_index(i)
            # check if input device
            if device_info['maxInputChannels'] > 0:
                # create device name
                device_name = f"{str(device_info['index'])}. {device_info['name']}"
                # set local data
                self.device_map[device_name] = device_info
                self.device_map['None'] = None

    def start_audio_streams(self):
        # get selected
        device_infos = [self.device_map[dropdown.selected_option.get()] for dropdown in self.audio_input_dropdowns]
        device_ids = [device_info['index'] for device_info in device_infos if device_info['index'] is not None]
        if (len(device_ids) == 0):
            print("no audio input devices selected")
            return
        language = self.selected_language.get()
        fut = asyncio.run_coroutine_threadsafe(self.transcription_controller.start_deepgram(device_ids, language), self.asyncio_loop)
        fut.result()
        # get audio input capture frequencies
        device_frequencies = [device_info['defaultSampleRate'] for device_info in device_infos if device_info['index'] is not None]
        print('device_frequencies', device_frequencies)
        self.transcription_controller.start(device_ids, device_frequencies, self.asyncio_loop)
        self.capture_button.config(text="Stop Capture")

    def stop_transcription(self):
        future = asyncio.run_coroutine_threadsafe(self.transcription_controller.stop(), self.asyncio_loop)
        future.result() # make UI hang while stopping
        self.capture_button.config(text="Start Capture")

    def toggle_capture(self):
        # toggle capture button logic
        if self.transcription_controller.audio_stream_0 == None and \
            self.transcription_controller.audio_stream_1 == None:
            self.start_audio_streams()
        else:
            self.stop_transcription()

    def toggle_prompt_edit_save(self):
        if self.textbox_base_prompt.cget('state') == 'disabled':
            # enable textbox
            self.textbox_base_prompt.configure(state='normal', background='white')
            self.edit_save_button.config(text="Save")
        else:
            # disable textbox
            self.textbox_base_prompt.configure(state='disabled', background='#f0f0f0')
            self.edit_save_button.config(text="Edit")
    
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

            # self.textbox_left.configure(state='disabled') ### testing editable log transcript
            self.textbox_left.see(tk.END)
        self.root.after(0, task)

    def language_changed(self, *args):
        print(f"language changed to {self.selected_language.get()}")
    
    def toggle_prompt(self, prompt_id='interview_candidate'):
        # erase and insert default text on textbox
        self.textbox_base_prompt.configure(state='normal', background='white')
        self.textbox_base_prompt.delete('1.0', tk.END)
        self.textbox_base_prompt.insert(tk.INSERT, base_prompts[prompt_id])
        self.textbox_base_prompt.configure(state='disabled', background='#f0f0f0')

    def clear_log(self):
        self.textbox_left.configure(state='normal')
        self.textbox_left.delete('1.0', tk.END)
        # self.textbox_left.configure(state='disabled') ### testing editable log transcript

    def ask_guru(self):
        # clear guru textbox
        self.textbox_right.configure(state='normal')
        self.textbox_right.delete('1.0', tk.END)
        self.textbox_right.configure(state='disabled')
        # prepare prompt 
        transcription = self.textbox_left.get("1.0", tk.END)
        final_prompt = self.textbox_base_prompt.get("1.0", tk.END)
        final_prompt = final_prompt.replace("[INPUT_TRANSCRIPTION]", transcription)
        # prompt token size
        enc = tiktoken.get_encoding("cl100k_base")
        token_count = len(enc.encode(final_prompt))
        print("asking guru...\n", token_count, " tokens")
        print(final_prompt)
        asyncio.run_coroutine_threadsafe(self.gpt_controller.send_prompt(final_prompt), self.asyncio_loop)


class DeviceSelectDropdown:
    def __init__(self, master, row, col, device_names, device_changed_callback):
        self.device_changed_callback = device_changed_callback
        # creates dropdown for selecting audio input device
        self.selected_option = tk.StringVar(master)
        self.selected_option.set(device_names[0] if device_names else "")
        self.selected_option.trace_add('write', self.device_changed)
        self.audio_input_dropdown = tk.OptionMenu(master, self.selected_option, *device_names)
        self.audio_input_dropdown.grid(row=row, column=col, padx=5, pady=5)

    def device_changed(self, *args):
        # handle selected device change
        self.device_changed_callback()
