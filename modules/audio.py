import pygame
import numpy as np

# Audio Engine initialization
try:
    pygame.mixer.init()
except Exception as e:
    print(f"Audio init warning: {e}")

def play_ui_tone(freq):
    try:
        duration = 0.08
        t = np.linspace(0, duration, int(44100 * duration), False)
        wave = (np.sin(2 * np.pi * freq * t) * 32767).astype(np.int16)
        pygame.sndarray.make_sound(np.stack((wave, wave), axis=-1)).play()
    except Exception as e:
        print(f"UI Tone play error: {e}")
