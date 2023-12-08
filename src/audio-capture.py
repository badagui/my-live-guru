import sounddevice as sd
import numpy as np
from google.cloud import speech_v2
from google.cloud.speech_v2.types import cloud_speech
from dotenv import load_dotenv
import os
import threading
import queue
import time
import sys

load_dotenv()
google_project_id = os.getenv('GOOGLE_PROJECT_ID')

# Initialize Google Cloud Speech Client
# Ensure the environment variable GOOGLE_APPLICATION_CREDENTIALS is set correctly
# os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = r"C:/Users/Bug/projects/my-live-guru/google-service-acc.json"
# $env:GOOGLE_APPLICATION_CREDENTIALS="C:/Users/Bug/projects/my-live-guru/google-service-acc.json"

print('', os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))

# client = speech_v2.SpeechClient.from_service_account_json('C:/Users/Bug/projects/my-live-guru/google-service-acc.json')
client = speech_v2.SpeechClient()

# Define the recognition configuration
recognition_config = cloud_speech.RecognitionConfig(
    explicit_decoding_config=speech_v2.ExplicitDecodingConfig(
        encoding=speech_v2.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        audio_channel_count=1,
    ),
    language_codes=["en-US"],
    model="long",
)

streaming_config = cloud_speech.StreamingRecognitionConfig(config=recognition_config)

config_request = cloud_speech.StreamingRecognizeRequest(
    recognizer=f"projects/{google_project_id}/locations/global/recognizers/_",
    streaming_config=streaming_config,
)

class AudioStream:
    def __init__(self):
        self.stream = None
        self.transcription_callback = None
        self.config_sent = False
        self._buffer = queue.Queue()
        self.worker_thread = threading.Thread(target=self.worker)
        self.worker_thread.daemon = True
        self.worker_thread.start()

    def start(self, device_id, transcription_callback):
        self.transcription_callback = transcription_callback
        self.stop()
        # self.stream = sd.InputStream(device=device_id, callback=callback)
        self.stream = sd.InputStream(samplerate=16000, blocksize=1024*4, device=device_id, channels=1, dtype='int16', callback=self._fill_buffer)
        self.stream.start()

    def stop(self):
        if self.stream is not None:
            self.stream.stop()
            self.stream.close()
            self.stream = None

    def worker(self):
        while True:
            audio_data = self._buffer.get()
            if audio_data is None:
                print('f:worker None - returning')
                return
                # time.sleep(0.1)
                # continue
            print('f:worker transcribing')
            transcript = self.transcribe_audio(audio_data)
            self.transcription_callback(transcript)

    def compute_amplitude(self, indata):
        # basic amplitude for testing
        return np.linalg.norm(indata) * 10
    
    def transcribe_audio(self, indata):
        print('f:transcribe_audio')
        # transcribe = str(self.compute_amplitude(indata))
        # transcribe = 'indata len: ' + str(len(indata))
        # return transcribe
        
        # Convert the NumPy array to bytes and send for transcription
        audio_chunk = indata.tobytes()
        audio_request = cloud_speech.StreamingRecognizeRequest(audio=audio_chunk)
        
        def request_generator():
            if not self.config_sent:
                self.config_sent = True
                yield config_request
            yield audio_request

        responses_iterator = client.streaming_recognize(requests=request_generator())
        transcript = ""
        for response in responses_iterator:
            for result in response.results:
                transcript += str(result.alternatives[0].transcript)
        return transcript
    
    def _fill_buffer(self, indata, frames, time, status):
        self._buffer.put(indata.copy())

def print_transcript(transcript):
    print('print_transcript: ', transcript)

audio_stream_user = AudioStream()
audio_stream_user.start(1, print_transcript)

try:
    while True:
        # Keep the main thread alive.
        time.sleep(0.1)
except KeyboardInterrupt:
    audio_stream_user.stop()
    print("Audio stream stopped.")

# app = AppGUI((audio_stream_user,))
# app.run()
# audio_stream_sys = AudioStream()
# app = AppGUI((audio_stream_user, audio_stream_sys))
