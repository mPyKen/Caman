import threading
import time
import logging
import numpy as np
import cv2

class Layer(object):

    def __init__(self, **kwargs):
        self.frame = None
        self.mask = None
        self.framelock = threading.Lock()
        self.masklock = threading.Lock()
        self.setParams(kwargs)

    def setParams(self, kwargs):
        if 'position' in kwargs:
            self.posx = kwargs['position'][0]
            self.posy = kwargs['position'][1]
        if 'dimension' in kwargs:
            self.width = kwargs['dimension'][0]
            self.height = kwargs['dimension'][1]
        if 'level' in kwargs:
            self.level = kwargs['level']
        if 'frame' in kwargs:
            self.writeFrame(kwargs['frame'])
        if 'mask' in kwargs:
            self.writeMask(kwargs['mask'])
    
    def command(self, **kwargs):
        return False

    def updateDimension(self):
        frame = self.getFrame()
        mask = self.getMask()
        if frame is not None:
            frame = cv2.resize(frame, (self.width, self.height))
        if mask is not None:
            mask = cv2.resize(mask[0], (self.width, self.height)) * 255
        self.writeFrame(frame)
        self.writeMask(mask)

    def writeFrame(self, frame):
        self.framelock.acquire()
        try:
            self.frame = frame
        finally:
            self.framelock.release()

    def writeMask(self, mask):
        self.masklock.acquire()
        try:
            if mask is None:
                self.mask = None
                self.invmask = None
            else:
                self.mask = mask / 255
                self.invmask = 1 - self.mask
        finally:
            self.masklock.release()

    def getFrame(self):
        res = None
        self.framelock.acquire()
        try:
            if self.frame is not None:
                res = self.frame.copy()
        finally:
            self.framelock.release()
        return res

    def getMask(self):
        res = None
        self.masklock.acquire()
        try:
            if self.mask is not None:
                res = (self.mask.copy(), self.invmask.copy())
        finally:
            self.masklock.release()
        return res


class ImageLayer(Layer):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if 'path' in kwargs:
            self.loadImage(kwargs['path'])

    def updateDimension(self):
        super().updateDimension()
        self.reload()

    def loadImage(self, path):
        self.path = path
        self.reload()

    def reload(self):
        image = cv2.imread(self.path, cv2.IMREAD_UNCHANGED)
        if self.width <= 0 and self.height <= 0:
            self.height = image.shape[0]
            self.width = image.shape[1]
        else:
            if self.width > 0 and self.height > 0:
                pass
            elif self.width > 0:
                self.height = self.width * image.shape[0] // image.shape[1]
            elif self.height > 0:
                self.width = self.height * image.shape[1] // image.shape[0]
            image = cv2.resize(image, (self.width, self.height))
        if image.shape[2] == 4:
            alpha = image[:, :, 3]
            image = image[:, :, :3]
            self.writeMask(alpha)
        self.writeFrame(image)


class AnimatedLayer(Layer):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.threadlock = threading.Lock()
        self.pauselock = threading.Lock()
        self.dorun = False
        if 'provider' in kwargs:
            self.setProvider(kwargs['provider'])

    def setProvider(self, provider):
        self.provider = provider
        self.reset()

    def updateDimension(self):
        super().updateDimension()
        self.provider.setParams({'dimension': (self.width, self.height)})

    def command(self, **kwargs):
        return self.provider.command(**kwargs)

    def reset(self):
        self.updateDimension()
        self.provider.reset()

    def stop(self):
        self.dorun = False
        self.provider.stop()

    def start(self):
        if self.dorun == False:
            self.dorun = True
            self.t = threading.Thread(target=self.run)
            self.t.start()

    def pause(self):
        self.pauselock.acquire()
        self.threadlock.acquire()
        self.pauselock.release()

    def resume(self):
        self.threadlock.release()

    def run(self):
        while self.dorun == True:
            self.threadlock.acquire()
            try:
                ret, frame, mask = self.provider.next()
                if ret == False:
                    self.level = -self.level
                    self.stop()
                else:
                    if frame is not None:
                        if self.height < 0:
                            self.height = frame.shape[0]
                        if self.width < 0:
                            self.width = frame.shape[1]
                    self.writeFrame(frame)
                    self.writeMask(mask)
            finally:
                self.threadlock.release()
            self.pauselock.acquire()
            self.pauselock.release()
