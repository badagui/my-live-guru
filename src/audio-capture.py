import pyaudio
from deepgram import Deepgram
from dotenv import load_dotenv
import os
import asyncio
import numpy as np
import signal

load_dotenv()

DEEPGRAM_API_KEY = os.getenv('DEEPGRAM_API_KEY')
MIC_DEVICE_ID = 1
STEREOMIX_DEVICE_ID = 2

p = None
deepgram_transcriber = None
audio_stream_user = None
audio_stream_system = None
terminate_program = False

# mixes audio streams into a single or multi-channel buffer
# mode 0: single channel
# mode 1: multi channel
class AudioMixer:
    def __init__(self, device_ids, mode, mixed_callback):
        self.audio = {device_id: None for device_id in device_ids}
        self.mode = mode
        self.mixed_callback = mixed_callback

    def audio_handler(self, device_id, audio):
        # store audio chunk
        self.audio[device_id] = audio
        
        # check if all data available
        if not all(data is not None for data in self.audio.values()):
            return
        
        # mix data
        mixed_data = self._mix_audio()
        if self.mixed_callback:
            self.mixed_callback(mixed_data)
        
        # clear buffer - keys must persist to check for data availability
        self.audio = {key: None for key in self.audio}

    def _mix_audio(self):
        if not self.audio:
            raise ValueError("audio_data is empty")
        
        audio_arrays = []

        # gather audio data
        for device_id in self.audio:
            audio_arrays.append(np.frombuffer(self.audio[device_id], dtype=np.int16))

        if not audio_arrays:
            raise ValueError("no audio data found")
        
        # single channel, averaged
        if (self.mode == 0):
            mixed_array = np.mean(audio_arrays, axis=0).astype(np.int16)
            return mixed_array.tobytes()
        
        # multi channel
        if (self.mode == 1):
            return np.stack(audio_arrays, axis=-1).tobytes()

class AudioStream:
    def __init__(self, pyaudio_obj, device_id, audio_chunk_callback):
        self.p = pyaudio_obj  # PyAudio object
        self.device_id = device_id
        self.audio_callback = audio_chunk_callback
        self._buffer = asyncio.Queue(maxsize=5)
        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=1,
                                  rate=16000,
                                  input=True,
                                  input_device_index=device_id,
                                  frames_per_buffer=1024*4,
                                  stream_callback=self._fill_buffer)
        self.consume_buffer_task = asyncio.create_task(self._consume_buffer())

    def stop(self):
        if self.stream is not None:
            self.stream.stop_stream()
            self.stream.close()
            self.stream = None
        self.consume_buffer_task.cancel()

    def _fill_buffer(self, in_data, frame_count, time_info, status):
        try:
            self._buffer.put_nowait(in_data)
            return (None, pyaudio.paContinue)
        except:
            return
    
    async def _consume_buffer(self):
        try:
            while True:
                audio_data = await self._buffer.get()
                if audio_data is None:
                    print('audio worker: got None from buffer - returning')
                    return
                if self.audio_callback:
                    self.audio_callback(self.device_id, audio_data)
        except:
            return

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
                    "multichannel": True,
                    "channels": 2,
                    "sample_rate": 16000
                }
            )
        except Exception as e:
            print(f'could not open deepgram socket: {e}')
        
        # deepgram events
        self.deepgram_live.register_handler(
            self.deepgram_live.event.TRANSCRIPT_RECEIVED, 
            self._transcription_received
        )

        self.deepgram_live.register_handler(
            self.deepgram_live.event.CLOSE,
            lambda _: print('deepgram connection closed')
        )
    
    # transcription result received
    async def _transcription_received(self, transcript_json: dict):
        if not 'channel' in transcript_json:
            return
        transcription = transcript_json['channel']['alternatives'][0]['transcript']
        # stop propagation if empty
        if not transcription:
            return
        is_channel_0 = transcript_json['channel_index'][0] == 0
        prefix = 'user: ' if is_channel_0 else 'system: '
        await self.transcription_callback(prefix + transcription)
    
    # sends audio chunk to live transcription API
    def send_audio(self, chunk):
        self.deepgram_live.send(chunk)
    
    async def close(self):
        try:
            await self.deepgram_live.finish()
        except:
            print("exception when closing deepgram")

async def transcription_handler(transcription: str):
    print(transcription)
    # voice command
    if transcription.lower().startswith("user: stop program"):
        await close_program()

async def close_program():
    print('closing program...')
    audio_stream_user.stop()
    audio_stream_system.stop()
    p.terminate()
    await deepgram_transcriber.close()
    global terminate_program
    terminate_program = True

# ctrl+C handler
def signal_handler(signal, frame):
    asyncio.create_task(close_program())
signal.signal(signal.SIGINT, signal_handler)

async def main():
    global p, deepgram_transcriber, audio_stream_user, audio_stream_system
    
    p = pyaudio.PyAudio()  # PyAudio object

    deepgram_transcriber = DeepgramTranscriber(DEEPGRAM_API_KEY)
    await deepgram_transcriber.initialize(transcription_handler)
    
    audio_mixer = AudioMixer([MIC_DEVICE_ID, STEREOMIX_DEVICE_ID], 1, deepgram_transcriber.send_audio)

    audio_stream_user = AudioStream(p, MIC_DEVICE_ID, audio_mixer.audio_handler)
    audio_stream_system = AudioStream(p, STEREOMIX_DEVICE_ID, audio_mixer.audio_handler)
    
    try:
        while not terminate_program:
            await asyncio.sleep(0.1)
    except:
        print("main thread exception")

asyncio.run(main())


# app = AppGUI((audio_stream_user,))
# app.run()
# app = AppGUI((audio_stream_user, audio_stream_sys))

