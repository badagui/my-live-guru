import pyaudio

# Define the file path for the raw audio file
filename = 'mixed_audio.lin16'

# audio file params
FILE_FORMAT = pyaudio.paInt16
FILE_CHANNELS = 1
FILE_RATE = 16000

# Audio stream parameters
chunk = 1024

# Initialize PyAudio
p = pyaudio.PyAudio()

# Open the raw audio file in read-binary mode
with open(filename, 'rb') as f:
    # Open a stream
    stream = p.open(format=FILE_FORMAT,
                    channels=FILE_CHANNELS,
                    rate=FILE_RATE,
                    output=True)

    # Read and play back chunks of data from the file
    data = f.read(chunk)
    while data:
        stream.write(data)
        data = f.read(chunk)

    # Stop and close the stream
    stream.stop_stream()
    stream.close()

# Terminate PyAudio
p.terminate()
