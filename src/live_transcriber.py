import asyncio
import pyaudio
from deepgram import Deepgram
import numpy as np
import queue

# controls audio_stream -> mixer -> transcription pipeline
class TranscriptionController:
    def __init__(self, p: pyaudio.PyAudio, DEEPGRAM_API_KEY: str):
        self.p = p  # PyAudio object
        self.deepgram_transcriber = DeepgramTranscriber(DEEPGRAM_API_KEY)
        self.audio_stream_user = None
        self.audio_stream_system = None
        self.final_results = queue.Queue(10) # thread safe interface

    async def start(self, device_ids: list):
        print (f'starting transcription controller with device ids {device_ids}')
        try:
            await self.deepgram_transcriber.initialize(self.final_results)
            audio_mixer = AudioMixer(device_ids, 1, self.deepgram_transcriber.send_audio)
            self.audio_stream_user = AudioStream(self.p, device_ids[0], audio_mixer.audio_handler)
            self.audio_stream_system = AudioStream(self.p, device_ids[1], audio_mixer.audio_handler)
            # audio_mixer.save_mixed_data_to_file('mixed_audio.lin16') # uncomment to save mixed audio to file
        except Exception as e:
            print(f"audio controller start exception {e}")
    
    async def stop(self):
        try:
            if self.audio_stream_user is not None:
                self.audio_stream_user.stop()
                self.audio_stream_user = None
            if self.audio_stream_system is not None:
                self.audio_stream_system.stop()
                self.audio_stream_system = None
            await self.deepgram_transcriber.close()
        except Exception as e:
            print(f"audio controller stop exception {e}")

    async def terminate(self):
        await self.stop()
    
# mixes audio streams into a single or multi-channel buffer
class AudioMixer:
    # mode 0: mix all devices into a single channel
    # mode 1: mix each device into its own channel
    # device_ids are needed so we can know when all chunks are available for mixing
    def __init__(self, device_ids: list, mode: int, mixed_callback):
        self.set_new_device_ids(device_ids)
        self.mode = mode
        self.mixed_callback = mixed_callback
        self.mixed_data_file = None

    def set_new_device_ids(self, device_ids: list):
        self.audio_sync = {device_id: None for device_id in device_ids}

    def audio_handler(self, device_id, audio):
        print('received device_id', device_id, 'audio', len(audio), 'bytes')
        # store audio chunk
        self.audio_sync[device_id] = audio
        
        # check if all data available
        if not all(data is not None for data in self.audio_sync.values()):
            return
        
        # mix data
        mixed_data = self._mix_audio()

        # sends mixed data
        if self.mixed_callback:
            self.mixed_callback(mixed_data)

        # save mixed data to file if specified
        if self.mixed_data_file:  # Check if a file is open and save mixed_data
            with open(self.mixed_data_file, 'ab') as file:
                file.write(mixed_data)
        
        # clear buffer - keys must persist to check for data availability
        self.audio_sync = {key: None for key in self.audio_sync}

    def _mix_audio(self):
        if not self.audio_sync:
            raise ValueError("audio_data is empty")
        
        audio_arrays = []

        # gather audio data
        for device_id in self.audio_sync:
            audio_arrays.append(np.frombuffer(self.audio_sync[device_id], dtype=np.int16))

        print(len(audio_arrays)) # 2
        if not audio_arrays:
            raise ValueError("no audio data found")
        
        # single channel, averaged
        if self.mode == 0:
            mixed_array = np.mean(audio_arrays, axis=0).astype(np.int16)
            return mixed_array.tobytes()
        
        # multi channel
        if self.mode == 1:
            return np.stack(audio_arrays, axis=-1).tobytes()
    
    def save_mixed_data_to_file(self, filename):
        self.mixed_data_file = filename

# single audio stream that generate audio slices from an input device
class AudioStream:
    def __init__(self, pyaudio_obj, device_id, audio_callback):
        self.p = pyaudio_obj  # PyAudio object
        self.device_id = device_id
        self.audio_callback = audio_callback
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
        except asyncio.QueueFull:
            print("buffer full, dropping audio data")
        except:
            print ("fill buffer exception")
    
    async def _consume_buffer(self):
        try:
            while True:
                audio_data = await self._buffer.get()
                if audio_data is None:
                    print('audio worker: got None from buffer - returning')
                    return
                if self.audio_callback:
                    self.audio_callback(self.device_id, audio_data)
                await asyncio.sleep(0.01)
        except:
            print("consume buffer exception")
            return

# accept audio slices and sends them to deepgram returning transcriptions
class DeepgramTranscriber:
    def __init__(self, DEEPGRAM_API_KEY):
        self.client = Deepgram(DEEPGRAM_API_KEY)
        self.deepgram_live = None
        self.results_queue = None
        self.last_speaker = ""

    async def initialize(self, results_queue: queue.Queue):
        self.results_queue = results_queue
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
            print("transcription live")
        except Exception as e:
            print(f'could not open deepgram socket: {e}')
        
        # deepgram events
        self.deepgram_live.register_handler(
            self.deepgram_live.event.TRANSCRIPT_RECEIVED, 
            self._transcript_received
        )

        self.deepgram_live.register_handler(
            self.deepgram_live.event.CLOSE,
            lambda _: print('deepgram connection closed')
        )
    
    # put transcription results on queue appending the speaker prefix when needed.
    async def _transcript_received(self, transcript_json: dict):
        if not 'channel' in transcript_json:
            return
        transcription = transcript_json['channel']['alternatives'][0]['transcript']
        # stop propagation if empty
        if not transcription:
            return
        is_channel_0 = transcript_json['channel_index'][0] == 0
        prefix = 'user: ' if is_channel_0 else 'system: '
        # check need for prefix
        try:
            if prefix == self.last_speaker:
                self.results_queue.put_nowait(('transcription_msg', transcription))
            else:
                self.results_queue.put_nowait(('transcription_msg', prefix + transcription))
        except queue.Full:
            print("results queue full")
        except Exception as e:
            print(f"results queue exception {e}")
        # update last speaker
        self.last_speaker = prefix
    
    # sends audio chunk to live transcription API
    def send_audio(self, chunk):
        try:
            self.deepgram_live.send(chunk)
        except Exception as e:
            print(f"deepgram send audio exception {e}")
    
    async def close(self):
        # check if deepgram connection is open before finishing
        if self.deepgram_live is None:
            return
        try:
            await self.deepgram_live.finish()
            self.deepgram_live = None
        except:
            print("exception when closing deepgram")
