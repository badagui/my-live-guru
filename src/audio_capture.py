import threading
from app_gui import AppGUI
from threading import Thread
import pyaudio
from dotenv import load_dotenv
import os
import asyncio
import signal
from live_transcriber import TranscriptionController

load_dotenv()

DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
MIC_DEVICE_ID = 1
STEREOMIX_DEVICE_ID = 2

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
def SIGINT_handler(signal, frame):
    print('SIGINT received')
    future = asyncio.run_coroutine_threadsafe(transcription_controller.stop(), asyncio_loop)
    future.result()
    asyncio_loop.call_soon_threadsafe(terminate_event.set)
    app_gui.root.destroy()

signal.signal(signal.SIGINT, SIGINT_handler)

p = pyaudio.PyAudio()
transcription_controller = TranscriptionController(p, DEEPGRAM_API_KEY)
terminate_event = EventAsyncio()

# start the asyncio loop in a separate thread
asyncio_loop = asyncio.new_event_loop()
asyncio_thread = Thread(target=start_asyncio_loop, args=(asyncio_loop, terminate_event), daemon=False)
asyncio_thread.start()

# start GUI loop in mainthread
app_gui = AppGUI(transcription_controller, asyncio_loop, terminate_event)
app_gui.run_mainloop()

p.terminate()

# wait until asyncio loop is terminated
asyncio_thread.join()

