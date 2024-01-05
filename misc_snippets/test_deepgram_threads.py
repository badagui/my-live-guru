from threading import Thread
import time
from deepgram import Deepgram
import asyncio
import aiohttp
import os
from dotenv import load_dotenv
load_dotenv()

# The API key you created in step 1
DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')

# URL for the real-time streaming audio you would like to transcribe
URL = 'http://stream.live.vc.bbcmedia.co.uk/bbc_world_service'
deepgramLive = None

# start asyncio loop
def start_asyncio_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_until_complete(main())
    loop.close()

def handle_transcription_json(transcription_json):
    # print(transcription_json['duration'])
    # print(transcription_json['is_final'])
    print(transcription_json['channel']['alternatives'][0]['transcript'])

async def main():
    # Initializes the Deepgram SDK
    deepgram = Deepgram(DEEPGRAM_API_KEY)

    # Create a websocket connection to Deepgram
    try:
        global deepgramLive    
        deepgramLive = await deepgram.transcription.live(
            { "smart_format": True, "model": "nova-2", "language": "en-US" }
        )
    except Exception as e:
        print(f'Could not open socket: {e}')
        return

    # Listen for the connection to close
    deepgramLive.registerHandler(deepgramLive.event.CLOSE, lambda _: print('Connection closed.'))

    # Listen for any transcripts received from Deepgram and write them to the console
    deepgramLive.registerHandler(deepgramLive.event.TRANSCRIPT_RECEIVED, handle_transcription_json)

    # Listen for the connection to open and send streaming audio from the URL to Deepgram
    async with aiohttp.ClientSession() as session:
        async with session.get(URL) as audio:
            while True:
                data = await audio.content.readany()
                deepgramLive.send(data)

                # If no data is being sent from the live stream, then break out of the loop.
                if not data:
                    break

    # Indicate that we've finished sending data by sending the customary zero-byte message to the Deepgram streaming endpoint, and wait until we get back the final summary metadata object
    print("off-thread main ended")

async def close():
    try:
        await deepgramLive.finish()
    except:
        print("exception when closing deepgram")

# start asyncio loop in another thread
asyncio_loop = asyncio.new_event_loop()
thread = Thread(target=start_asyncio_loop, args=(asyncio_loop,), daemon=True)
thread.start()

print('main thread doing important stuff...')
time.sleep(10)
asyncio.run_coroutine_threadsafe(close(), asyncio_loop)
print('main thread finished')

# asyncio.run(main())

