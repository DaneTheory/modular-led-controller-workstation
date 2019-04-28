from __future__ import (absolute_import, division, print_function, unicode_literals)

import colorsys
import math
import random
from collections import OrderedDict

import matplotlib as mpl
import numpy as np
import scipy as sp
from scipy.ndimage.filters import gaussian_filter1d
from scipy.signal import lfilter

import audioled.colors as colors
import audioled.dsp as dsp
from audioled.effects import Effect
from audioled.audio import GlobalAudio


class Spectrum(Effect):
    """
    Spectrum performs a FFT and visualizes bass and melody frequencies with different colors.

    Inputs:
    - 0: Audio
    - 1: Color for melody (default: white)
    - 2: Color for bass (default: white)

    Outputs:
    - 0: Pixel array

    """

    @staticmethod
    def getEffectDescription():
        return \
            "Spectrum performs a FFT on the audio input (channel 0) and visualizes bass and melody frequencies "\
            "with different colors (channel 1 for bass, channel 2 for melody)."

    def __init__(self, fmax=6000, n_overlaps=4, fft_bins=64, col_blend=colors.blend_mode_default):
        self.fmax = fmax
        self.n_overlaps = n_overlaps
        self.fft_bins = fft_bins
        self.col_blend = col_blend
        self.__initstate__()

    def __initstate__(self):
        # state
        self._norm_dist = None
        self.fft_bins = 64
        self._fft_dist = np.linspace(0, 1, self.fft_bins)
        self._max_filter = np.ones(8)
        self._min_feature_win = np.hamming(8)
        self._fs_ds = 0.0
        self._bass_rms = None
        self._melody_rms = None
        self._lastAudioChunk = None
        self._gen = None
        super(Spectrum, self).__initstate__()

    def numInputChannels(self):
        return 3

    def numOutputChannels(self):
        return 1

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("n_overlaps", [4, 0, 20, 1]),
                ("fft_bins", [64, 32, 128, 1]),
                ("col_blend", colors.blend_modes)
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "n_overlaps": "Number of overlapping samples in time. This smoothes the FFT.",
                "fft_bins": "Number of bins of the FFT. Increase for a more detailed FFT.",
                "col_blend": "Color blend mode for combining bass and melody FFT."
            }
        }
        return help

    def getParameter(self):
        definition = self.getParameterDefinition()
        definition['parameters']['n_overlaps'][0] = self.n_overlaps
        definition['parameters']['fft_bins'][0] = self.fft_bins
        definition['parameters']['col_blend'] = [self.col_blend
                                                 ] + [x for x in colors.blend_modes if x != self.col_blend]
        return definition

    def _audio_gen(self, audio_gen):
        audio, self._fs_ds = dsp.preprocess(audio_gen, GlobalAudio.sample_rate, self.fmax, self.n_overlaps)
        return audio

    def buffer_coroutine(self):
        while True:
            yield self._lastAudioChunk

    async def update(self, dt):
        await super().update(dt)
        if self._num_pixels is None:
            return
        if self._norm_dist is None or len(self._norm_dist) != self._num_pixels:
            self._norm_dist = np.linspace(0, 1, self._num_pixels)

    def process(self):

        if self._inputBuffer is not None and self._outputBuffer is not None:
            audio = self._inputBuffer[0]
            col_melody = self._inputBuffer[1]
            col_bass = self._inputBuffer[2]
            if col_melody is None:
                # default color: all white
                col_melody = np.ones(self._num_pixels) * np.array([[255.0], [255.0], [255.0]])
            if col_bass is None:
                # default color: all white
                col_bass = np.ones(self._num_pixels) * np.array([[255.0], [255.0], [255.0]])
            if audio is not None:
                if self._gen is None:
                    g = self.buffer_coroutine()
                    next(g)
                    self._lastAudioChunk = audio
                    self._gen = self._audio_gen(g)
                self._lastAudioChunk = audio
                y = next(self._gen)
                bass = dsp.warped_psd(y, self.fft_bins, self._fs_ds, [32.7, 261.0], 'bark')
                melody = dsp.warped_psd(y, self.fft_bins, self._fs_ds, [261.0, self.fmax], 'bark')
                bass = self.process_line(bass)
                melody = self.process_line(melody)
                pixels = colors.blend(1. / 255.0 * np.multiply(col_bass, bass),
                                      1. / 255. * np.multiply(col_melody, melody), self.col_blend)
                self._outputBuffer[0] = pixels.clip(0, 255).astype(int)

    def process_line(self, fft):

        # fft = np.convolve(fft, self._max_filter, 'same')

        # Some kind of normalization?
        # fft_rms[1:] = fft_rms[:-1]
        # fft_rms[0] = np.mean(fft)
        # fft = np.tanh(fft / np.max(fft_rms)) * 255

        # Upsample to number of pixels
        fft = np.interp(self._norm_dist, self._fft_dist, fft)

        #
        fft = np.convolve(fft, self._min_feature_win, 'same')

        return fft * 255


class VUMeterRMS(Effect):
    """ VU Meter style effect
    Inputs:
    - 0: Audio
    - 1: Color
    """

    @staticmethod
    def getEffectDescription():
        return \
            "VUMeterRMS visualizes the RMS value of the audio input (channel 0) with the color (channel 1)."

    def __init__(self, db_range=60.0, n_overlaps=1):
        self.db_range = db_range
        self.n_overlaps = n_overlaps
        self.__initstate__()

    def __initstate__(self):
        super().__initstate__()
        try:
            self._hold_values
        except AttributeError:
            self._hold_values = []
        self._default_color = None

    def numInputChannels(self):
        return 2

    def numOutputChannels(self):
        return 1

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("db_range", [60.0, 20.0, 100.0, 1.0]),
                ("n_overlaps", [1, 0, 20, 1])
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "db_range": "Range of the VU Meter in decibels.",
                "n_overlaps": "Number of overlapping samples in time. This smoothes the VU Meter."
            }
        }
        return help

    def getParameter(self):
        definition = self.getParameterDefinition()
        definition['parameters']['db_range'][0] = self.db_range
        definition['parameters']['n_overlaps'][0] = self.n_overlaps
        return definition

    async def update(self, dt):
        await super().update(dt)
        if self._num_pixels is None:
            return
        if self._default_color is None:
            # default color: VU Meter style
            # green from -inf to -24
            # green to red from -24 to 0
            h_a, s_a, v_a = colorsys.rgb_to_hsv(0, 1, 0)
            h_b, s_b, v_b = colorsys.rgb_to_hsv(1, 0, 0)
            scal_value = (self.db_range + (-24)) / self.db_range
            index = int(self._num_pixels * scal_value)
            np = self._num_pixels - index
            interp_v = np.linspace(v_a, v_b, np)
            interp_s = np.linspace(s_a, s_b, np)
            interp_h = np.linspace(h_a, h_b, np)
            hsv = np.array([interp_h, interp_s, interp_v]).T

            rgb = mpl.colors.hsv_to_rgb(hsv)
            green = np.array([[0, 255.0, 0] for i in range(index)]).T
            self._default_color = np.concatenate((green, rgb.T * 255.0), axis=1)

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        buffer = self._inputBuffer[0]
        if buffer is None:
            self._outputBuffer[0] = None
            return
        color = self._inputBuffer[1]
        if color is None:
            color = self._default_color

        y = self._inputBuffer[0]
        rms = dsp.rms(y)
        # calculate rms over hold_time
        while len(self._hold_values) > self.n_overlaps:
            self._hold_values.pop()
        self._hold_values.insert(0, rms)
        rms = dsp.rms(self._hold_values)
        db = 20 * math.log10(max(rms, 1e-16))
        scal_value = (self.db_range + db) / self.db_range
        bar = np.zeros(self._num_pixels) * np.array([[0], [0], [0]])
        index = int(self._num_pixels * scal_value)
        index = np.clip(index, 0, self._num_pixels - 1)
        bar[0:3, 0:index] = color[0:3, 0:index]
        self._outputBuffer[0] = bar


class VUMeterPeak(Effect):
    """ VU Meter style effect
    Inputs:
    - 0: Audio
    - 1: Color
    """

    @staticmethod
    def getEffectDescription():
        return \
            "VUMeterPeak visualizes the Peak value of the audio input (channel 0) with the color (channel 1)."

    def __init__(self, db_range=60.0, n_overlaps=1):
        self.db_range = db_range
        self.n_overlaps = n_overlaps
        self._default_color = None
        self.__initstate__()

    def __initstate__(self):
        super().__initstate__()
        try:
            self._hold_values
        except AttributeError:
            self._hold_values = []
        self._default_color = None

    def numInputChannels(self):
        return 2

    def numOutputChannels(self):
        return 1

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("db_range", [60.0, 20.0, 100.0, 1.0]),
                ("n_overlaps", [1, 0, 20, 1])
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "db_range": "Range of the VU Meter in decibels.",
                "n_overlaps": "Number of overlapping samples in time. This smoothes the VU Meter."
            }
        }
        return help

    def getParameter(self):
        definition = self.getParameterDefinition()
        definition['parameters']['db_range'][0] = self.db_range
        definition['parameters']['n_overlaps'][0] = self.n_overlaps
        return definition

    async def update(self, dt):
        if self._num_pixels is None:
            return
        if self._default_color is None or np.size(self._default_color, 1) != self._num_pixels:
            # default color: VU Meter style
            # green from -inf to -24
            # green to red from -24 to 0
            h_a, s_a, v_a = colorsys.rgb_to_hsv(0, 1, 0)
            h_b, s_b, v_b = colorsys.rgb_to_hsv(1, 0, 0)
            scal_value = (self.db_range + (-24)) / self.db_range
            index = int(self._num_pixels * scal_value)
            num_pix = self._num_pixels - index
            interp_v = np.linspace(v_a, v_b, num_pix)
            interp_s = np.linspace(s_a, s_b, num_pix)
            interp_h = np.linspace(h_a, h_b, num_pix)
            hsv = np.array([interp_h, interp_s, interp_v]).T

            rgb = mpl.colors.hsv_to_rgb(hsv)
            if (index > 0):
                green = np.array([[0, 255.0, 0] for i in range(index)]).T
                self._default_color = np.concatenate((green, rgb.T * 255.0), axis=1)
            else:
                self._default_color = rgb.T * 255.0

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        buffer = self._inputBuffer[0]
        if buffer is None:
            self._outputBuffer[0] = None
            return
        color = self._inputBuffer[1]
        if color is None:
            try:
                color = self._default_color
            except Exception:
                self.__initstate__()
                color = self._default_color
        if self._num_pixels != np.size(color, axis=1):
            self.__initstate__()
            color = self._default_color

        y = self._inputBuffer[0]

        peak = np.max(y)
        # calculate max over hold_time
        while len(self._hold_values) > self.n_overlaps:
            self._hold_values.pop()
        self._hold_values.insert(0, peak)
        peak = np.max(self._hold_values)

        db = (20 * (math.log10(max(peak, 1e-16))))
        scal_value = (self.db_range + db) / self.db_range
        bar = np.zeros(self._num_pixels) * np.array([[0], [0], [0]])
        index = int(self._num_pixels * scal_value)
        index = np.clip(index, 0, self._num_pixels - 1)
        bar[0:3, 0:index] = color[0:3, 0:index]
        self._outputBuffer[0] = bar


class MovingLight(Effect):
    """
    This effect generates a peak at the beginning of the strip that moves and dissipates

    Inputs:
    - 0: Audio
    - 1: Color
    """

    @staticmethod
    def getEffectDescription():
        return \
            "MovingLight generates a visual peak based on the audio input (channel 0) with the given color (channel 1) "\
            "at the beginning of the strip. This peak moves down the strip until it dissipates."

    def __init__(self,
                 speed=100.0,
                 dim_time=2.5,
                 lowcut_hz=50.0,
                 highcut_hz=300.0,
                 peak_scale=4.0,
                 peak_filter=2.6,
                 highlight=0.6):
        self.speed = speed
        self.dim_time = dim_time
        self.lowcut_hz = lowcut_hz
        self.highcut_hz = highcut_hz
        self.peak_scale = peak_scale
        self.peak_filter = peak_filter
        self.highlight = highlight
        self.__initstate__()

    def __initstate__(self):
        # state
        self._pixel_state = None
        if GlobalAudio.sample_rate is not None:
            self._filter_b, self._filter_a, self._filter_zi = dsp.design_filter(self.lowcut_hz, self.highcut_hz, GlobalAudio.sample_rate, 3)
        self._last_t = 0.0
        self._last_move_t = 0.0
        super(MovingLight, self).__initstate__()

    def numInputChannels(self):
        return 2

    def numOutputChannels(self):
        return 1

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("speed", [10.0, 1.0, 200.0, 1.0]),
                ("dim_time", [1.0, 0.01, 10.0, 0.01]),
                ("lowcut_hz", [50.0, 0.0, 8000.0, 1.0]),
                ("highcut_hz", [100.0, 0.0, 8000.0, 1.0]),
                ("peak_filter", [1.0, 0.0, 10.0, .01]),
                ("peak_scale", [1.0, 0.0, 5.0, .01]),
                ("highlight", [0.0, 0.0, 1.0, 0.01])
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "speed":
                "Speed of the moving peak.",
                "dim_time":
                "Amount of time for the afterglow of the moving peak.",
                "lowcut_hz":
                "Lowcut frequency of the audio input.",
                "highcut_hz":
                "Highcut frequency of the audio input.",
                "peak_filter":
                "Filters the audio peaks. Increase this value to transform only high audio peaks into visual peaks.",
                "peak_scale":
                "Scales the visual peak after the filter.",
                "highlight":
                "Amount of white light added to the audio peak.",
            }
        }
        return help

    def getParameter(self):
        definition = self.getParameterDefinition()
        definition['parameters']['speed'][0] = self.speed
        definition['parameters']['dim_time'][0] = self.dim_time
        definition['parameters']['lowcut_hz'][0] = self.lowcut_hz
        definition['parameters']['highcut_hz'][0] = self.highcut_hz
        definition['parameters']['peak_scale'][0] = self.peak_scale
        definition['parameters']['peak_filter'][0] = self.peak_filter
        definition['parameters']['highlight'][0] = self.highlight
        return definition

    async def update(self, dt):
        await super().update(dt)
        if self._pixel_state is None or np.size(self._pixel_state, 1) != self._num_pixels:
            self._pixel_state = np.zeros(self._num_pixels) * np.array([[0.0], [0.0], [0.0]])

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        buffer = self._inputBuffer[0]
        color = self._inputBuffer[1]
        if color is None:
            # default color: all white
            color = np.ones(self._num_pixels) * np.array([[255.0], [255.0], [255.0]])
        if buffer is not None:
            audio = self._inputBuffer[0]
            # apply bandpass to audio
            y, self._filter_zi = lfilter(b=self._filter_b, a=self._filter_a, x=np.array(audio), zi=self._filter_zi)
            # move in speed
            dt_move = self._t - self._last_move_t
            if dt_move * self.speed > 1:
                shift_pixels = int(dt_move * self.speed)
                shift_pixels = np.clip(shift_pixels, 1, self._num_pixels - 1)
                self._pixel_state[:, shift_pixels:] = self._pixel_state[:, :-shift_pixels]
                self._pixel_state[:, 0:shift_pixels] = self._pixel_state[:, shift_pixels:shift_pixels + 1]
                # convolve to smooth edges
                self._pixel_state[:, 0:2 * shift_pixels] = gaussian_filter1d(
                    self._pixel_state[:, 0:2 * shift_pixels], sigma=0.5, axis=1)
                self._last_move_t = self._t
            # dim with time
            dt = self._t - self._last_t
            self._last_t = self._t
            self._pixel_state *= (1.0 - dt / self.dim_time)
            self._pixel_state = gaussian_filter1d(self._pixel_state, sigma=0.5, axis=1)
            self._pixel_state = gaussian_filter1d(self._pixel_state, sigma=0.5, axis=1)
            # new color at origin
            peak = np.max(y) * 1.0
            try:
                peak = peak**self.peak_filter
            except Exception:
                peak = peak
            peak = peak * self.peak_scale
            r, g, b = color[0, 0], color[1, 0], color[2, 0]
            self._pixel_state[0][0] = r * peak + self.highlight * peak * 255.0
            self._pixel_state[1][0] = g * peak + self.highlight * peak * 255.0
            self._pixel_state[2][0] = b * peak + self.highlight * peak * 255.0
            self._pixel_state = np.nan_to_num(self._pixel_state).clip(0.0, 255.0)
            self._outputBuffer[0] = self._pixel_state


class Bonfire(Effect):
    """ Effect for audio-reactive color splitting of an existing pixel array.
    Compare searchlight and bonfireSearchlight WebUIConfigs.
    Inputs:
    - 0: Audio
    - 1: Pixels
    """

    @staticmethod
    def getEffectDescription():
        return \
            "Bonfire performs an audio-reactive color splitting of input channel 1 based on "\
            "the audio input (channel 0)."

    def __init__(self, spread=100, lowcut_hz=50.0, highcut_hz=200.0):
        self.spread = spread
        self.lowcut_hz = lowcut_hz
        self.highcut_hz = highcut_hz
        self._default_color = None
        self.__initstate__()

    def __initstate__(self):
        if GlobalAudio.sample_rate is not None:
            self._filter_b, self._filter_a, self._filter_zi = dsp.design_filter(self.lowcut_hz, self.highcut_hz, GlobalAudio.sample_rate, 3)
        super(Bonfire, self).__initstate__()

    def numInputChannels(self):
        return 2

    def numOutputChannels(self):
        return 1

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("spread", [10, 0, 100, 1]),
                ("lowcut_hz", [50.0, 0.0, 8000.0, 1.0]),
                ("highcut_hz", [100.0, 0.0, 8000.0, 1.0]),
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "spread": "Amount of pixels the splitted colors are moved.",
                "lowcut_hz": "Lowcut frequency of the audio input.",
                "highcut_hz": "Highcut frequency of the audio input.",
            }
        }
        return help

    def getParameter(self):
        definition = self.getParameterDefinition()
        definition['parameters']['spread'][0] = self.spread
        definition['parameters']['lowcut_hz'][0] = self.lowcut_hz
        definition['parameters']['highcut_hz'][0] = self.highcut_hz
        return definition

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        if self._inputBufferValid(1):
            pixelbuffer = self._inputBuffer[1]
        else:
            # default color: all white
            pixelbuffer = np.ones(self._num_pixels) * np.array([[255.0], [255.0], [255.0]])
        if not self._inputBufferValid(0):
            self._outputBuffer[0] = pixelbuffer
            return

        audiobuffer = self._inputBuffer[0]

        y, self._filter_zi = lfilter(b=self._filter_b, a=self._filter_a, x=np.array(audiobuffer), zi=self._filter_zi)
        peak = np.max(y) * 1.0

        pixelbuffer[0] = sp.ndimage.interpolation.shift(
            pixelbuffer[0], -self.spread * peak, mode='wrap', prefilter=True)
        pixelbuffer[2] = sp.ndimage.interpolation.shift(pixelbuffer[2], self.spread * peak, mode='wrap', prefilter=True)
        self._outputBuffer[0] = pixelbuffer


class FallingStars(Effect):
    """Effect for creating random stars that fade over time."""

    @staticmethod
    def getEffectDescription():
        return \
            "Effect for creating random stars based on audio input that fade over time."

    def __init__(self,
                 lowcut_hz=50.0,
                 highcut_hz=300.0,
                 peak_filter=1.0,
                 peak_scale=1.0,
                 dim_speed=100,
                 thickness=1,
                 probability=0.1,
                 min_brightness=0.1,
                 max_spawns=10):
        self.dim_speed = dim_speed
        self.thickness = thickness  # getting down with it
        self.probability = probability
        self.lowcut_hz = lowcut_hz
        self.highcut_hz = highcut_hz
        self.peak_filter = peak_filter
        self.peak_scale = peak_scale
        self.min_brightness = min_brightness
        self.max_spawns = max_spawns
        self.__initstate__()

    def __initstate__(self):
        # state
        self._t0Array = []
        self._spawnArray = []
        self._peakArray = []
        self._starCounter = 0
        if GlobalAudio.sample_rate is not None:
            self._filter_b, self._filter_a, self._filter_zi = dsp.design_filter(self.lowcut_hz, self.highcut_hz, GlobalAudio.sample_rate, 3)
        super(FallingStars, self).__initstate__()

    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("lowcut_hz", [50.0, 0.0, 8000.0, 1.0]),
                ("highcut_hz", [100.0, 0.0, 8000.0, 1.0]),
                ("peak_filter", [1.0, 0.0, 10.0, .01]),
                ("peak_scale", [1.0, 0.0, 10.0, .01]),
                ("dim_speed", [100, 1, 1000, 1]),
                ("thickness", [1, 1, 300, 1]),
                ("probability", [0.1, 0.0, 1.0, 0.01]),
                ("min_brightness", [0.1, 0.0, 1.0, 0.01]),
                ("max_spawns", [10, 1, 10, 1])
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "lowcut_hz":
                "Lowcut frequency of the audio input.",
                "highcut_hz":
                "Highcut frequency of the audio input.",
                "peak_filter":
                "Filters the audio peaks. Increase this value to transform only high audio peaks into visual peaks.",
                "peak_scale":
                "Scales the visual peak after the filter.",
                "dim_speed":
                "Time to fade out one star.",
                "thickness":
                "Thickness of one star in pixels.",
                "probability":
                "Probability of spawning a new star even if there's no audio peak.",
                "max_spawns":
                "Maximum number of spawning stars per frame.",
                "min_brightness":
                "Adjust minimum brightness of stars."
            }
        }
        return help

    def getParameter(self):
        definition = self.getParameterDefinition()
        definition['parameters']['lowcut_hz'][0] = self.lowcut_hz
        definition['parameters']['highcut_hz'][0] = self.highcut_hz
        definition['parameters']['peak_filter'][0] = self.peak_filter
        definition['parameters']['peak_scale'][0] = self.peak_scale
        definition['parameters']['dim_speed'][0] = self.dim_speed
        definition['parameters']['thickness'][0] = self.thickness
        definition['parameters']['probability'][0] = self.probability
        definition['parameters']['min_brightness'][0] = self.min_brightness
        definition['parameters']['max_spawns'][0] = self.max_spawns
        return definition

    def numInputChannels(self):
        return 2

    def numOutputChannels(self):
        return 1

    def spawnStar(self, peak):
        self._starCounter += 1
        self._t0Array.append(self._t)
        self._spawnArray.append(random.randint(0, self._num_pixels - self.thickness))
        self._peakArray.append(peak)
        if self._starCounter > 100:
            self._starCounter -= 1
            self._t0Array.pop(0)
            self._spawnArray.pop(0)
            self._peakArray.pop(0)

    def allStars(self, t, dim_speed, thickness, t0, spawnSpot, peak):
        controlArray = []
        for i in range(0, self._starCounter):
            oneStarArray = np.zeros(self._num_pixels)
            for j in range(0, thickness):
                if i < len(spawnSpot):
                    index = spawnSpot[i] + j
                    if index < self._num_pixels:
                        oneStarArray[index] = math.exp(-(100 / dim_speed) * (self._t - t0[i])) * max(
                            self.min_brightness, peak[i])
            controlArray.append(oneStarArray)
        return controlArray

    def starControl(self, prob, peak):
        for i in range(int(self.max_spawns)):
            if random.random() <= prob:
                self.spawnStar(peak)
        outputArray = self.allStars(self._t, self.dim_speed, self.thickness, self._t0Array, self._spawnArray,
                                    self._peakArray)
        return np.sum(outputArray, axis=0)

    async def update(self, dt):
        await super().update(dt)

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        if not self._inputBufferValid(0):
            return
        if self._inputBufferValid(1):
            color = self._inputBuffer[1]
        else:
            color = np.ones(self._num_pixels) * np.array([[255.0], [255.0], [255.0]])
        
        audio = self._inputBuffer[0]
        # apply bandpass to audio
        y, self._filter_zi = lfilter(b=self._filter_b, a=self._filter_a, x=np.array(audio), zi=self._filter_zi)

        # adjust probability according to peak of audio
        peak = np.max(y) * 1.0
        try:
            peak = peak**self.peak_filter
        except Exception:
            peak = peak
        prob = min(self.probability + peak, 1.0)
        if self._outputBuffer is not None:
            self._output = np.multiply(
                color,
                self.starControl(prob, peak) * np.array([[self.peak_scale * 1.0], [self.peak_scale * 1.0],
                                                         [self.peak_scale * 1.0]]))
        self._outputBuffer[0] = self._output.clip(0.0, 255.0)


class Oscilloscope(Effect):

    @staticmethod
    def getEffectDescription():
        return \
            "Displays audio as a wave signal over time."

    def __init__(self,
                 lowcut_hz=1.0,
                 highcut_hz=22000.0):
        self.lowcut_hz = lowcut_hz
        self.highcut_hz = highcut_hz
        self.__initstate__()
    
    def __initstate__(self):
        super().__initstate__()
        if GlobalAudio.sample_rate is not None:
            self._filter_b, self._filter_a, self._filter_zi = dsp.design_filter(self.lowcut_hz, max(self.highcut_hz, self.lowcut_hz), GlobalAudio.sample_rate, 3)
            
    @staticmethod
    def getParameterDefinition():
        definition = {
            "parameters":
            OrderedDict([
                # default, min, max, stepsize
                ("lowcut_hz", [1.0, 1.0, 8000.0, 1.0]),
                ("highcut_hz", [22000.0, 0.0, 22000.0, 1.0])
            ])
        }
        return definition

    @staticmethod
    def getParameterHelp():
        help = {
            "parameters": {
                "lowcut_hz":
                "Lowcut frequency of the audio input.",
                "highcut_hz":
                "Highcut frequency of the audio input."
            }
        }
        return help

    def getParameter(self):
        definition = self.getParameterDefinition()
        definition['parameters']['lowcut_hz'][0] = self.lowcut_hz
        definition['parameters']['highcut_hz'][0] = self.highcut_hz
        return definition

    def numInputChannels(self):
        return 2

    def numOutputChannels(self):
        return 1
    
    def getNumInputPixels(self, channel):
        if self._num_pixels is not None:
            cols = int(self._num_pixels / self._num_rows)
            return cols
        return None
    
    async def update(self, dt):
        await super().update(dt)

    def process(self):
        if self._inputBuffer is None or self._outputBuffer is None:
            return
        if not self._inputBufferValid(0):
            return
        audio = self._inputBuffer[0]
        cols = int(self._num_pixels / self._num_rows)
        if self._inputBufferValid(1):
            color = self._inputBuffer[1]
        else:
            color = np.ones(cols) * np.array([[255], [255], [255]])
        
        # apply bandpass to audio
        audio, self._filter_zi = lfilter(b=self._filter_b, a=self._filter_a, x=np.array(audio), zi=self._filter_zi)

        output = np.zeros((3, self._num_rows, cols))
        # First downsample to half the cols
        decimation_ratio = np.round(len(audio) / cols * 2)
        downsampled_audio = sp.signal.decimate(audio, int(decimation_ratio), ftype='fir', zero_phase=True)
        # Then resample to the number of cols -> prevents jumping between positive and negative values
        downsampled_audio = sp.signal.resample(downsampled_audio, cols)
        for i in range(0, cols):
            # determine index in audio array
            valIdx = i
            # get value
            val = downsampled_audio[valIdx]
            # convert to row idx
            rowIdx = max(0, min(int(self._num_rows / 2 + val * self._num_rows / 2), self._num_rows - 1))
            # set value for this col
            output[:, rowIdx, i] = color[:, i]
        self._outputBuffer[0] = output.reshape((3, -1))

        
        