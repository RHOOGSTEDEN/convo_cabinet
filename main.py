from __future__ import division

import re
import sys
import os

from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types
import pyaudio #for recording audio!
import pygame  #for playing audio
from six.moves import queue

from gtts import gTTS
import os
import time
from adafruit_crickit import crickit
from adafruit_seesaw.neopixel import NeoPixel
import datetime

num_pixels = 75  # Number of pixels driven from Crickit NeoPixel terminal
 
# The following line sets up a NeoPixel strip on Seesaw pin 20 for Feather
pixels = NeoPixel(crickit.seesaw, 20, num_pixels)

# Audio recording parameters, set for our USB mic.
RATE = 48000 #if you change mics - be sure to change this :)
CHUNK = int(RATE / 10)  # 100ms

credential_path = "/home/pi/DET-2019.json" #replace with your file name!
os.environ["GOOGLE_APPLICATION_CREDENTIALS"]=credential_path

client = speech.SpeechClient()

pygame.init()
pygame.mixer.init()

user_report = " "
#Some boolean values to control state
START = True
ACTIVE = False #cabinet is conversing
ALERT = False # dosage alert
REPORT = False #save response
class Medicine(object):
    def __init__(self, name, dosage, hour, location):
        self.name = name
        self.dosage = dosage
        self.hour = hour
        self.location = location
        self.taken = False
        self.alert_msg = 'alert_msg.mp3'
        self.loc_msg = 'loc_msg.mp3'

def med_alert(med):
    currDT = datetime.datetime.now()

    if currDT.hour-med.hour == 0:
        play_audio(med.alert_msg)
        play_audio(med.loc_msg)
    else:
        play_audio(med.alert_msg)
        time_msg = " before " +str(med.hour) + " hundred hours."
        t2s = gTTS(time_msg, lang='en-uk')
        t2s.save('time_alert.mp3')
        play_audio('time_alert.mp3')
        play_audio(med.loc_msg)
    return
#medical info
med_1 = Medicine("Adderal", "2 pills", 23, " the center, of the top shelf in the cabinet, ") 
med_list = {med_1}

def play_audio(file_path):
    pygame.mixer.init()
    pygame.mixer.music.load(file_path)
    pygame.mixer.music.play()
    while pygame.mixer.music.get_busy(): 
        pygame.time.Clock().tick(10)


def wake():
    global ACTIVE, START 
    ACTIVE = True
    
    if START:
        play_audio('greeting.mp3')
        check_meds()
        START = False
    else if ALERT == True:
        play_audio('takethem.mp3')
        return
    else:
        play_audio('help.mp3')
        

def check_meds():
    global med_list
    print("checking meds")
    currDT = datetime.datetime.now()
    for med in med_list:
        if med.hour <= currDT.hour:
            global ALERT 
            ALERT = True
    
        for med in med_list:
            med_alert(med)
    return

def takemeds():
    play_audio("finished.mp3")
    
def delaymeds():
    play_audio("delaymeds.mp3")

def get_update():
    global REPORT
    REPORT = True
    play_audio('inquiry.mp3')





#MicrophoneStream() is brought in from Google Cloud Platform
class MicrophoneStream(object):
    """Opens a recording stream as a generator yielding the audio chunks."""
    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            # The API currently only supports 1-channel (mono) audio
            # https://goo.gl/z757pE
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,
            # Run the audio stream asynchronously to fill the buffer object.
            # This is necessary so that the input device's buffer doesn't
            # overflow while the calling thread makes network requests, etc.
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        # Signal the generator to terminate so that the client's
        # streaming_recognize method will not block the process termination.
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        """Continuously collect data from the audio stream, into the buffer."""
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            # Use a blocking get() to ensure there's at least one chunk of
            # data, and stop iteration if the chunk is None, indicating the
            # end of the audio stream.
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            # Now consume whatever other data's still buffered.
            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)


#this loop is where the microphone stream gets sent
def listen_print_loop(responses):
    """Iterates through server responses and prints them.

    The responses passed is a generator that will block until a response
    is provided by the server.

    Each response may contain multiple results, and each result may contain
    multiple alternatives; for details, see https://goo.gl/tjCPAU.  Here we
    print only the transcription for the top alternative of the top result.

    In this case, responses are provided for interim results as well. If the
    response is an interim one, print a line feed at the end of it, to allow
    the next result to overwrite it, until the response is a final one. For the
    final one, print a newline to preserve the finalized transcription.
    """
    num_chars_printed = 0
    for response in responses:
        if not response.results:
            continue

        # The `results` list is consecutive. For streaming, we only care about
        # the first result being considered, since once it's `is_final`, it
        # moves on to considering the next utterance.
        result = response.results[0]
        if not result.alternatives:
            continue

        # Display the transcription of the top alternative.
        transcript = result.alternatives[0].transcript

        # Display interim results, but with a carriage return at the end of the
        # line, so subsequent lines will overwrite them.
        #
        # If the previous result was longer than this one, we need to print
        # some extra spaces to overwrite the previous result
        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if not result.is_final:
#            sys.stdout.write(transcript + overwrite_chars + '\r')
#            sys.stdout.flush()

            num_chars_printed = len(transcript)

        else:
            print(transcript + overwrite_chars)
            #if there's a voice activitated quit - quit!
            if re.search(r'\b(exit|quit)\b', transcript, re.I):
                print('Exiting..')
                break
            else:
                decide_action(transcript)
#            print(transcript)
            # Exit recognition if any of the transcribed phrases could be
            # one of our keywords.
            num_chars_printed = 0

def decide_action(transcript):
    if re.search('hello', transcript, re.I):
        wake()
    else if START == False and ALERT == True:
        if re.search('yes', transcript, re.I):
            takemeds()
        else if re.search('no', transcript, re.I):
            delaymeds()
        else:
            play_audio('confused.mp3')
    else:
        return
def main():


    
    #setting up the GTTS responses as .mp3 files!
    t2s = gTTS('I didn't understand what you said.', lang ='en-UK', slow=False)
    t2s.save('confused.mp3')
    t2s = gTTS('Would you like to take your medication now?', lang ='en-UK', slow=False)
    t2s.save('takethem.mp3')
#    t2s = gTTS('Hello, User', lang ='en-UK', slow=False)
#    t2s.save('greeting.mp3')
#    alert_msg = 'Please take ' + med_1.dosage + ' of your ' + med_1.name
#    t2s = gTTS(alert_msg,lang='en-UK')
#    t2s.save('alert_msg.mp3')
#    loc_msg = 'They are located on ' + med_1.location + '. They will be marked by the green LED lights.'
#    t2s = gTTS(loc_msg, lang='en-UK')
#    t2s.save('loc_msg.mp3')   
#    t2s = gTTS('Ok!', lang ='en-UK')
#    t2s.save('ok.mp3')
#    t2s = gTTS('Is there anything else I can help you with?', lang='en-UK')
#    t2s.save('help.mp3')
#    t2s = gTTS('My records indicate that you have already taken your prescriptions for the day. Would you like to take an additional dose?', lang='en-UK')
#    t2s.save('no_meds.mp3')
#    t2s = gTTS('Great. How are you feeling?', lang='en-UK')
#    t2s.save('feelings.mp3')
#    t2s = gTTS('Have you finished taking your medications?', lang='en-UK')
#    t2s.save('finished.mp3')
#    t2s = gTTS('Let me know when you are done.', lang='en-UK')
#    t2s.save('done.mp3')
    # See http://g.co/cloud/speech/docs/languages
    # for a list of supported languages.
    # this code comes from Google Cloud's Speech to Text API!
    # Check out the links in your handout. Comments are ours.
    language_code = 'en-US'  # a BCP-47 language tag

    #set up a client
    #make sure GCP is aware of the encoding, rate 
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code)
    #our example uses streamingrecognition - most likely what you will want to use.
    #check out the simpler cases of asychronous recognition too!
    streaming_config = types.StreamingRecognitionConfig(
        config=config,
        interim_results=True)
    
    #this section is where the action happens:
    #a microphone stream is set up, requests are generated based on
    #how the audiofile is chunked, and they are sent to GCP using
    #the streaming_recognize() function for analysis. responses
    #contains the info you get back from the API. 
    with MicrophoneStream(RATE, CHUNK) as stream:
        audio_generator = stream.generator()
        requests = (types.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator)

        responses = client.streaming_recognize(streaming_config, requests)

        # Now, put the transcription responses to use.
        listen_print_loop(responses)
        


if __name__ == '__main__':
    main()