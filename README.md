# My Live Guru

A real time voice transcription assistant with single-click LLM feedback.

* Uses Deepgram API for transcription
* Uses OpenAI API for LLM
* Uses PyAudio for audio capture
* Uses TkInter for GUI

<br><img src="https://github.com/badagui/my-live-guru/assets/18372659/d945c33a-dc38-47d5-abec-0d9bc8a6d488" width="700">

## Run Instructions:
* clone this repo
* python -m venv venv
* pip install -r requirements.txt
* create a .env file with DEEPGRAM_API_KEY and OPENAI_API_KEY set
* set up a system audio loopback: activate Stereo Mix (Windows) or set up PulseAudio for monitor of your output device (Linux).
* run python src/main.py
  
<br><br>explanation: accessing the system audio output directly is hard. So we need a virtual input containing all the output audio (an audio loopback). There are many free softwares that can create this, and windows comes with this by default called Stereo Mix, just have to activate it. Getting the raw output audio this way ensures we can work with any source.

## Use Instructions:
* Prepare your prompt in the stage tab.
* Use the [INPUT_TRANSCRIPTION] tag to indicate where the input transcription should be placed.
* Select your input devices and click start capturing.
* The transcription will be updated in real time and you will be identified as "user:" and the loopback audio as "system:".
* Click ASK GURU to send the prompt to the LLM and get the response.

## Example taken from the following mock interview video:
https://www.youtube.com/watch?v=1qw5ITr3k9E&t=164s

<br><img src="https://github.com/badagui/my-live-guru/assets/18372659/19403ec8-a6ef-40c1-a5df-c506da7f30f7" width="600">
<br><img src="https://github.com/badagui/my-live-guru/assets/18372659/c06b4748-ba0e-4c5e-bec6-39adb4174bac" width="600">

## Applications:
* Training and/or assistance for job interviews (for both interviewers and candidates), sales reps, aviation communications, legal practice, political debates...
* Customer reps assistant: on handling difficult customers or following protocols.
* Meetings assistant: delivering unique viewpoints, augmenting presented suggestions, and contrasting diverse lines of reasoning.
* Any kind of real-time conversation chatbot.
* Tabletop RPG helper.

## todo list
* Support local processing.
* Better prompt management.
* Allow multiple buttons to call different prompts.
* Add response automation.
* Remove the need for a system audio loopback setup.
* Improve GUI.

<br><br>
p.s: this is a proof of concept, not intended for live use. Do not use without everyones consent.