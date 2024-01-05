import asyncio
# import pyaudio
import pyaudiowpatch as pyaudio
from deepgram import Deepgram
import numpy as np
import queue

# controls audio_stream -> mixer -> transcription pipeline
class TranscriptionController:
    def __init__(self, p: pyaudio.PyAudio, DEEPGRAM_API_KEY: str):
        self.p = p  # PyAudio object
        self.deepgram_transcriber = DeepgramTranscriber(DEEPGRAM_API_KEY)
        self.audio_stream_0 = None
        self.audio_stream_1 = None
        self.transcriptions_queue = queue.Queue(10) # thread safe interface

    def start(self, device_ids: list, device_input_rates: list, loop: asyncio.AbstractEventLoop):
        print (f'starting transcription controller with device ids {device_ids}')
        channels = len(device_ids)
        multichannel = channels > 1
        try:
            mixer_mode = 1 if multichannel else 0
            audio_mixer = AudioMixer(device_ids, mixer_mode, self.deepgram_transcriber.send_audio)
            self.audio_stream_0 = AudioStream(self.p, device_ids[0], audio_mixer.audio_handler, loop, device_input_rates[0])
            if (channels == 2):
                self.audio_stream_1 = AudioStream(self.p, device_ids[1], audio_mixer.audio_handler, loop, device_input_rates[1])
            audio_mixer.save_mixed_data_to_file('mixed_audio.lin16') # uncomment to save mixed audio to file
        except Exception as e:
            print(f"audio controller start exception {e}")
    
    async def start_deepgram(self, device_ids: list, language: str):
        channels = len(device_ids)
        multichannel = channels > 1
        await self.deepgram_transcriber.initialize(self.transcriptions_queue, language, channels, multichannel)

    async def stop(self):
        try:
            if self.audio_stream_0 is not None:
                self.audio_stream_0.stop()
                self.audio_stream_0 = None
            if self.audio_stream_1 is not None:
                self.audio_stream_1.stop()
                self.audio_stream_1 = None
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
    def __init__(self, device_ids: list, mode: int, mixed_callback, chunk_size=1024*4):
        self.device_ids = device_ids
        self.mode = mode
        self.mixed_callback = mixed_callback
        self.chunk_size = chunk_size
        self.output_file = None
        self.audio_buffers = {device_id: b'' for device_id in device_ids}

    def set_new_device_ids(self, device_ids: list):
        self.audio_buffers = {device_id: b'' for device_id in device_ids}

    def audio_handler(self, device_id, audio_chunk):
        # append new chunk to the buffer
        self.audio_buffers[device_id] += audio_chunk

        # check if all data available
        if not all(len(self.audio_buffers[device_id]) >= self.chunk_size for device_id in self.device_ids):
            return
        
        # mix data
        mixed_data = self._mix_audio()

        # sends mixed data
        if self.mixed_callback:
            self.mixed_callback(mixed_data)

        # save mixed data to file if specified
        if self.output_file:
            with open(self.output_file, 'ab') as file:
                file.write(mixed_data)
        
        # clear used data from buffers
        for device_id in self.device_ids:
            self.audio_buffers[device_id] = self.audio_buffers[device_id][self.chunk_size:]

    def _mix_audio(self):
        audio_arrays = []

        # gather audio data
        for device_id in self.device_ids:
            # ensure each buffer has enough data for chunk_size
            buffer = self.audio_buffers[device_id][:self.chunk_size]
            audio_arrays.append(np.frombuffer(buffer, dtype=np.int16))

        # mix audio data
        if self.mode == 0: # single channel, averaged
            mixed_array = np.mean(audio_arrays, axis=0).astype(np.int16)
            return mixed_array.tobytes()
        elif self.mode == 1: # multi channel
            mixed_array = np.stack(audio_arrays, axis=-1).astype(np.int16)
        else:
            raise ValueError(f"invalid mixer mode {self.mode}")
        
        return mixed_array.tobytes()
    
    def save_mixed_data_to_file(self, filename):
        self.output_file = filename



# single audio stream that generate audio slices from an input device
class AudioStream:
    # note: if we run this as a coroutine from mainthread (with run_coroutine_threadsafe) we get an error [Errno -9999] Unanticipated host error (when opening loopback streams available with pyaudiowpatch)
    def __init__(self, pyaudio_obj, device_id, audio_callback, loop, source_rate, out_rate=16000):
        self.p = pyaudio_obj  # PyAudio object
        self.device_id = device_id
        self.audio_callback = audio_callback
        self.in_rate = source_rate
        self.out_rate = out_rate
        self._buffer = asyncio.Queue(maxsize=50, loop=loop)

        self.stream = self.p.open(format=pyaudio.paInt16,
                                  channels=1,
                                  rate=int(source_rate),
                                  input=True,
                                  input_device_index=device_id,
                                  frames_per_buffer=int(1024*4 * source_rate / out_rate),
                                  stream_callback=self._fill_buffer)
        
        self.consume_buffer_task = asyncio.run_coroutine_threadsafe(self._consume_buffer(), loop)

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
            return (None, pyaudio.paContinue)
        except Exception as e:
            print ("fill buffer exception", e)
    
    async def _consume_buffer(self):
        try:
            while True:
                audio_data = await self._buffer.get()
                if audio_data is None:
                    print('audio worker: got None from buffer - returning')
                    return
                # convert bytes data to numpy array
                np_audio_data = np.frombuffer(audio_data, dtype=np.int16)
                # resample the audio using interpolation
                resampled_data = self._resample(np_audio_data, self.in_rate, self.out_rate)
                # convert back to bytes
                resampled_bytes = resampled_data.astype(np.int16).tobytes()
                if self.audio_callback:
                    self.audio_callback(self.device_id, resampled_bytes)
                await asyncio.sleep(0)
        except Exception as e:
            print("consume buffer exception", e)
            return

    # uses linear interpolation for resampling
    def _resample(self, audio_data: np.ndarray, original_rate, new_rate):
        try:
            # new number of samples
            ratio = new_rate / original_rate
            new_length = int(len(audio_data) * ratio)
            # new sample indices
            new_indices = np.linspace(0, len(audio_data) - 1, new_length)
            # use numpy interpolation
            resampled_data = np.interp(new_indices, np.arange(len(audio_data)), audio_data)
            return resampled_data
        except Exception as e:
            print("resample exception", e)
            return None

# accept audio slices and sends them to deepgram returning transcriptions
class DeepgramTranscriber:
    def __init__(self, DEEPGRAM_API_KEY):
        self.client = Deepgram(DEEPGRAM_API_KEY)
        self.deepgram_live = None
        self.results_queue = None
        self.last_speaker = ""

    async def initialize(self, results_queue: queue.Queue, language: str, channels: int, multichannel: bool):
        self.results_queue = results_queue
        try:
            # create a websocket connection to deepgram
            self.deepgram_live = await self.client.transcription.live(
                { 
                    "smart_format": True, 
                    "model": "nova-2", 
                    "language": language,
                    "encoding": "linear16",
                    "multichannel": multichannel,
                    "channels": channels,
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
        
        transcription: str = transcript_json['channel']['alternatives'][0]['transcript']
        
        # stop propagation if empty
        if not transcription:
            return
        
        # clear new lines
        transcription = transcription.replace('\n', '').replace('\r', '')

        # check need for prefix and speaker identifier
        is_channel_0 = transcript_json['channel_index'][0] == 0
        msg_type = 'user_msg' if is_channel_0 else 'system_msg'
        speaker = 'user: ' if is_channel_0 else 'system: '
        if self.last_speaker == "":
            # first message
            transcription = speaker + transcription
        elif speaker != self.last_speaker:
            # new speaker
            transcription = "\n" + speaker + transcription
        else:
            # same speaker
            transcription = " " + transcription
        
        # put message in queue for consumption
        try:
            self.results_queue.put_nowait((msg_type, transcription))
        except queue.Full:
            print("results queue full")
        except Exception as e:
            print(f"results queue exception {e}")
        
        # update last speaker
        self.last_speaker = speaker
    
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
