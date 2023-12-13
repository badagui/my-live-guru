from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
import os
from dotenv import load_dotenv

def transcribe_streaming_v2(project_id: str, audio_file: str) -> cloud_speech.StreamingRecognizeResponse:
    client = SpeechClient()

    # Reads a file as bytes
    with open(audio_file, "rb") as f:
        content = f.read()

    # In practice, stream should be a generator yielding chunks of audio data
    chunk_length = len(content) // 10
    stream = [
        content[start : start + chunk_length]
        for start in range(0, len(content), chunk_length)
    ]
    audio_requests = (
        cloud_speech.StreamingRecognizeRequest(audio=audio) for audio in stream
    )

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

    config_request = cloud_speech.StreamingRecognizeRequest(
        recognizer=f"projects/{project_id}/locations/global/recognizers/_",
        streaming_config=streaming_config,
    )

    def requests(config: cloud_speech.RecognitionConfig, audio: list) -> list:
        yield config
        yield from audio

    # Transcribes the audio into text
    responses_iterator = client.streaming_recognize(
        requests=requests(config_request, audio_requests)
    )
    responses = []
    for response in responses_iterator:
        responses.append(response)
        for result in response.results:
            print(f"Transcript: {result.alternatives[0].transcript}")

    return responses


if __name__ == "__main__":
    load_dotenv()
    google_project_id = os.getenv('GOOGLE_PROJECT_ID')
    audio_file = r'C:\Users\Bug\projects\my-live-guru\recorded_audio.pcm'
    transcribe_streaming_v2(google_project_id, audio_file)
