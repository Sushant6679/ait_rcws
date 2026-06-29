import pygame
import numpy as np

class SoundPlayer:
    @classmethod
    def initialize(cls):
        pygame.mixer.init()

    @classmethod
    def play_error_sound(cls):
        cls._play_beep(2000, 300, 2)  # 2000 Hz, 300 ms, 2 times

    @classmethod
    def play_success_sound(cls):
        cls._play_beep(1000, 700, 1)  # 1000 Hz, 700 ms, 1 time

    @classmethod
    def play_warning_sound(cls):
        cls._play_beep(750, 600, 1)  # 750 Hz, 600 ms, 1 time

    @classmethod
    def _play_beep(cls, frequency, duration, times):
        sound = pygame.sndarray.make_sound(cls._generate_sine_wave(frequency, duration))
        for _ in range(times):
            sound.play()
            pygame.time.wait(duration)

    @staticmethod
    def _generate_sine_wave(frequency, duration):
        sample_rate = 44100
        t = np.linspace(0, duration / 1000, int(duration * sample_rate / 1000), False)
        wave = np.sin(2 * np.pi * frequency * t) * 32767
        # Ensure the array is 2D (stereo)
        stereo_wave = np.column_stack((wave, wave))
        return np.int16(stereo_wave)

# Initialize pygame mixer when the module is imported
SoundPlayer.initialize()