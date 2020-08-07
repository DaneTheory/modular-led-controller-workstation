import argparse
import logging
import colorsys
import time
import numpy as np
import sys
import os

from audioled import devices

logger = logging.getLogger(__name__)
logging.basicConfig(stream=sys.stdout,
                    level=os.environ.get("LOGLEVEL", "INFO"))

def strandTest(dev, num_pixels):
    pixels = np.zeros(int(num_pixels / 2)) * np.array([[255.0], [255.0], [255.0]])
    t = 0.0
    dt = 1.0 / num_pixels
    for i in range(0, int(num_pixels * 1.2)):
        h = t / dt / num_pixels
        r, g, b, = 0, 0, 0
        if i < num_pixels / 2:
            r, g, b = colorsys.hsv_to_rgb(h, 1.0, 1.0)
        pixels = np.roll(pixels, -1, axis=1)
        pixels[0][0] = r * 255.0
        pixels[1][0] = g * 255.0
        pixels[2][0] = b * 255.0
        dev.show(np.concatenate((pixels, pixels[:, ::-1]), axis=1))
        t = t + dt
        time.sleep(dt)

def runTest(dev, num_pixels):
    pos = np.zeros(int(num_pixels))
    for i in range(0, num_pixels):
        pos[i] = 1
        pixels = pos * np.array([[255.0], [255.0], [255.0]])
        tMs = time.time() * 1000
        dev.show(pixels)
        t2Ms = time.time() * 1000
        # print("Device took {} ms".format(t2Ms - tMs))
        pos[i] = 0

        time.sleep((max(0, (1./60.)*1000 - (t2Ms - tMs)))/1000.)
        # time.sleep(0.01)
        # print("Slept for {} ms".format(time.time() * 1000 - t2Ms))
        # print("Achieving {} Hz".format(1. / (time.time()*1000-tMs )*1000))
        

if __name__ == '__main__':
    num_pixels = 10
    parser = argparse.ArgumentParser(description='DeviceTest - send pixel data to audioled device')
    parser.add_argument(
        '--num_pixels',
        '-N',
        dest='num_pixels',
        default=500,
        help='Number of pixels to show',
    )
    args = parser.parse_args()
    if args.num_pixels:
        num_pixels = int(args.num_pixels)
    
    device = devices.WS2812SPI(num_pixels, 1, 1, 0)
    logger.info("Starting test on '{}'".format(device))
    while True:
        runTest(device, num_pixels)
    logger.info("Test finished")