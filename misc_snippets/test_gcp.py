import pyaudio
import numpy as np
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
import queue
import os
import time
from dotenv import load_dotenv
load_dotenv()
import threading

buffer = queue.Queue()
config_sent = False
device_id = 1

p = pyaudio.PyAudio()  # PortAudio interface

iterator_ready = threading.Event()

# GCP config - make sure these is set correctly to use the GCP service account
GOOGLE_PROJECT_ID = os.getenv('GOOGLE_PROJECT_ID')
print('GOOGLE_PROJECT_ID:', GOOGLE_PROJECT_ID)
print('GOOGLE_APPLICATION_CREDENTIALS:', os.getenv("GOOGLE_APPLICATION_CREDENTIALS"))

# GCP speech client
client = SpeechClient()

# GCP speech to text configurations
recognition_config = cloud_speech.RecognitionConfig(
    explicit_decoding_config=cloud_speech.ExplicitDecodingConfig(
        encoding=cloud_speech.ExplicitDecodingConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=16000,
        audio_channel_count=1,
    ),
    language_codes=["en-US"],
    model="long",
)

streaming_config = cloud_speech.StreamingRecognitionConfig(config=recognition_config)

request_config = cloud_speech.StreamingRecognizeRequest(
    recognizer=f"projects/{GOOGLE_PROJECT_ID}/locations/global/recognizers/_",
    streaming_config=streaming_config,
)

start_time = time.time()
responses_iterator = None

def handle_responses():
    print('Waiting for response iterator to be ready...')
    iterator_ready.wait()  # Wait until the event is set
    print('Response iterator is ready, starting to handle responses.')

    while True:
        if not responses_iterator:
            print('handle_resp: no iterator', responses_iterator)
            time.sleep(0.1)
            continue
        print('we got a response iterator!')
        try:
            for response in responses_iterator:
                print('Response:', response)
        except Exception as e:
            print(f"An error occurred while processing responses: {e}")
        time.sleep(0.1)

def fill_buffer(in_data, frame_count, time_info, status_flags):
    print('f: fill_buffer', frame_count, time.time() - start_time)
    indata = np.frombuffer(in_data, dtype=np.int16)
    buffer.put(indata.copy())
    return (None, pyaudio.paContinue)

def transcribe_audio():
    def request_generator():
        yield request_config
        while True:
            audio_data = buffer.get()
            if audio_data is None:
                print('audio_data None')
                break
            print('audio_data available')
            audio_chunk = audio_data.tobytes()
            audio_request = cloud_speech.StreamingRecognizeRequest(audio=audio_chunk)
            yield audio_request
    try:
        global responses_iterator 
        responses_iterator = client.streaming_recognize(requests=request_generator())
        iterator_ready.set()  # Signal that the iterator is ready
    except Exception as e:
        print(f"An error occurred in streaming_recognize: {e}")

try:
    stream = p.open(format=pyaudio.paInt16,
        channels=1,
        rate=16000,
        input=True,
        input_device_index=device_id,
        frames_per_buffer=1024*4,
        stream_callback=fill_buffer)

    response_thread = threading.Thread(target=handle_responses)
    response_thread.daemon = True
    response_thread.start()
    
    transcribe_thread = threading.Thread(target=transcribe_audio)
    transcribe_thread.daemon = True
    transcribe_thread.start()


    while True:
        time.sleep(0.1)

except KeyboardInterrupt:
    stream.stop_stream()
    stream.close()
