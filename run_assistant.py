import sys, logging
sys.path.insert(0, '/home/pi/app')
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s: %(message)s')
import tts, stt, intent

def run():
    tts.speak('CannaKit voice assistant ready.')
    print('', flush=True)
    print('  Press Enter to speak.  Ctrl+C to quit.', flush=True)
    print('', flush=True)
    while True:
        try:
            input('  [ Press Enter to speak ] ')
        except KeyboardInterrupt:
            print('\nShutting down...', flush=True)
            tts.speak('Goodbye.')
            break
        tts.speak('Yes?')
        command = stt.listen_and_transcribe(6)
        print(f'  Heard : {command}', flush=True)
        if command.strip():
            response = intent.route(command)
            print(f'  Reply : {response}', flush=True)
            tts.speak(response)
        else:
            tts.speak('I did not catch that.')

run()
