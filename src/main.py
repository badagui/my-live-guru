"""
    author: Jonas Mirovski
    email: jonasmirovski@gmail.com

    considerations

    * TkInter GUI lives on mainthread.
    * asyncio mainloop lives in an off-thread.
    * PyAudio streams live in their own threads, capturing single-channel 16bit data and putting them into a buffer for thread safe consumption.
    * two capture streams are created, one for the user, and one for the system loopback audio.
    * each input stream buffer is then consumed in the asyncio loop and then passed to our AudioMixer.
    * AudioMixer joins the audio slices into a dual channel buffer that is then sent to Deepgram with multichannel=True (Multichannel audio is audio that has multiple separate audio channels, and the audio in each channel is distinct).
    * Deepgram puts the results in our TranscriptionController queue for thread safe consumption again.
    * TkInter consumes the buffer directly from the main thread, for simplicity.
"""

from threading import Thread
import pyaudiowpatch as pyaudio
import os
import asyncio
import signal
from dotenv import load_dotenv
from app_gui import AppGUI
from live_transcriber import TranscriptionController
from gpt_controller import GPTController

load_dotenv()

DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# asyncio event wrapper
class EventAsyncio:
    def __init__(self):
        self.event = None
    
    def create(self):
        self.event = asyncio.Event()

    def set(self):
        if self.event is not None:
            self.event.set()
    
    def wait(self):
        if self.event is not None:
            return self.event.wait()

# start asyncio loop in current thread
def start_asyncio_loop(loop, terminate_event: EventAsyncio):
    asyncio.set_event_loop(loop)
    terminate_event.create()
    loop.run_until_complete(asyncio_main(terminate_event))
    loop.close()

# keep asyncio loop running
async def asyncio_main(terminate_event: EventAsyncio):
    try:
        await terminate_event.wait()
        print('asyncio_main() terminating...')
    except Exception as e:
        print(f'main routine exception {e}')

# ctrl+C handler
def SIGINT_handler(signal, frame, app_gui: AppGUI):
    print('SIGINT received')
    app_gui.root.after(0, app_gui.close_program)

def main():
    p = pyaudio.PyAudio()
    transcription_controller = TranscriptionController(p, DEEPGRAM_API_KEY)
    gpt_controller = GPTController(OPENAI_API_KEY)
    terminate_event = EventAsyncio()
    asyncio_loop = asyncio.new_event_loop()
    app_gui = AppGUI(transcription_controller, gpt_controller, asyncio_loop, terminate_event)
    
    # ctrl+C handler
    signal.signal(signal.SIGINT, lambda signal, frame: SIGINT_handler(signal, frame, app_gui))

    # start the asyncio loop in a separate thread
    asyncio_thread = Thread(target=start_asyncio_loop, args=(asyncio_loop, terminate_event), daemon=True)
    asyncio_thread.start()

    # start GUI loop in mainthread
    app_gui.run_mainloop()

    p.terminate()
    
    # wait until asyncio loop is terminated
    asyncio_thread.join()

if __name__ == "__main__":
    main()
