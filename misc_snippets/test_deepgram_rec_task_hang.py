# minimum example to reproduce the hang issue in deepgram's transcription.py (line 247)
# except websockets.exceptions.ConnectionClosedOK:
#     await self._queue.join() # --- THIS HANGS ---
#     self.done = True # socket closed, will terminate on next loop

import asyncio
from threading import Thread
import time
from deepgram import Deepgram
from dotenv import load_dotenv
import pyaudio
import os

load_dotenv()

DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
MIC_DEVICE_ID = 1
deepgram_live = None

# start asyncio loop
def start_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main_task())
    loop.close()

# keep asyncio loop running
async def main_task():
    global deepgram_live
    try:
        client = Deepgram(DEEPGRAM_API_KEY)
        deepgram_live = await client.transcription.live(
            { 
                "smart_format": True, 
                "model": "nova-2", 
                "language": "en-US",
                "encoding": "linear16",
                "channels": 1,
                "sample_rate": 16000
            }
        )
        deepgram_live.register_handler(
            deepgram_live.event.CLOSE,
            lambda _: print('deepgram connection closed')
        )
        while(True):
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f'main routine exception {e}')

async def close(self):
    try:
        await deepgram_live.finish()
    except:
        print("exception when closing deepgram")

# start asyncio loop in another thread
asyncio_loop = asyncio.new_event_loop()
thread = Thread(target=start_asyncio_loop, args=(asyncio_loop,), daemon=True)
thread.start()

time.sleep(1)
print('main thread doing important stuff...')
time.sleep(1)
asyncio.run_coroutine_threadsafe(close(deepgram_live), asyncio_loop)
print('main thread finished')
