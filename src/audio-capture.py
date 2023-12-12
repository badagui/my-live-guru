import aiohttp
import pyaudio
from deepgram import Deepgram
from dotenv import load_dotenv
import os
import asyncio

load_dotenv()

DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
MIC_DEVICE_ID = 1
STEREOMIX_DEVICE_ID = 2

class AudioStream:
    def __init__(self):
        self.stream = None
        self.audio_callback = None
        self._buffer = asyncio.Queue(maxsize=5)
        self.p = pyaudio.PyAudio()  # PyAudio object

    def start(self, device_id, audio_chunk_callback):
        self.audio_callback = audio_chunk_callback
        self.stop()
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=1,
                                  rate=16000,
                                  input=True,
                                  input_device_index=device_id,
                                  frames_per_buffer=1024*4,
                                  stream_callback=self._fill_buffer)
        asyncio.create_task(self._consume_buffer())

    def stop(self):
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None

    def _fill_buffer(self, in_data, frame_count, time_info, status):
        try:
            self._buffer.put_nowait(in_data)
        except asyncio.QueueFull:
            print("audio queue full")
        return (None, pyaudio.paContinue)
    
    async def _consume_buffer(self):
        while True:
            audio_data = await self._buffer.get()
            if audio_data is None:
                print('audio worker: got None from buffer - returning')
                return
            if self.audio_callback:
                self.audio_callback(audio_data)

class DeepgramTranscriber:
    def __init__(self, DEEPGRAM_API_KEY):
        self.client = Deepgram(DEEPGRAM_API_KEY)
        self.deepgram_live = None
        self.transcription_callback = None

    async def initialize(self, transcription_callback):
        self.transcription_callback = transcription_callback
        try:
            # create a websocket connection to deepgram
            self.deepgram_live = await self.client.transcription.live(
                { 
                    "smart_format": True, 
                    "model": "nova-2", 
                    "language": "en-US",
                    "encoding": "linear16",
                    "channels": 1,
                    "sample_rate": 16000,
                }
            )
        except Exception as e:
            print(f'could not open deepgram socket: {e}')
        
        # deepgram events
        self.deepgram_live.register_handler(
            self.deepgram_live.event.TRANSCRIPT_RECEIVED, 
            self._deepgram_transcription_callback
        )

        self.deepgram_live.register_handler(
            self.deepgram_live.event.CLOSE,
            lambda _: print('deepgram connection closed')
        )
    
    # new transcription received
    def _deepgram_transcription_callback(self, transcript_json):
        transcription = transcript_json['channel']['alternatives'][0]['transcript']
        self.transcription_callback(transcription)
    
    # sends a new audio chunk for deepgram live transcription
    def process_audio_chunk(self, chunk):
        self.deepgram_live.send(chunk)

def print_transcription(transcription):
    print(transcription)

async def main():
    deepgram_transcriber = DeepgramTranscriber(DEEPGRAM_API_KEY)
    await deepgram_transcriber.initialize(print_transcription)
    audio_stream_user = AudioStream()
    audio_stream_user.start(STEREOMIX_DEVICE_ID, deepgram_transcriber.process_audio_chunk)
    try:
        while True:
            await asyncio.sleep(0.1)
    except KeyboardInterrupt:
        audio_stream_user.stop()
        print("Audio stream stopped.")

asyncio.run(main())


# app = AppGUI((audio_stream_user,))
# app.run()
# audio_stream_sys = AudioStream()
# app = AppGUI((audio_stream_user, audio_stream_sys))

