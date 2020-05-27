import abc
from enum import Enum
import threading
import time
import logging
import collections
import numpy as np
import cv2
import requests
import subprocess
import mss
from PIL import Image
import mouseinfo

class Provider(object):

    __metaclass__ = abc.ABCMeta

    def __init__(self, **kwargs):
        self.provider = None
        self.frame = None
        self.mask = None
        self.setParams(kwargs)

    def setParams(self, kwargs):
        if 'provider' in kwargs:
            self.provider = kwargs.pop('provider', None)
        if 'dimension' in kwargs:
            self.width = kwargs['dimension'][0]
            self.height = kwargs['dimension'][1]

    def command(self, **kwargs):
        if self.provider is not None:
            return self.provider.command(**kwargs)
        return False

    @abc.abstractmethod
    def stop(self):
        pass

    @abc.abstractmethod
    def reset(self):
        pass

    @abc.abstractmethod
    def next(self):
        return (False, None, None)


class ImageProvider(Provider):

    def __init__(self, path, **kwargs):
        self.frame = None
        self.mask = None
        kwargs['path'] = path
        super().__init__(**kwargs)

    def setParams(self, kwargs):
        super().setParams(kwargs)
        if 'path' in kwargs:
            self.path = kwargs['path']

    def stop(self):
        pass

    def reset(self):
        self.stop()
        self.frame = cv2.imread(self.path, cv2.IMREAD_UNCHANGED)
        if self.frame.shape[2] == 4:
            self.mask = self.frame[:, :, 3]
            self.frame = self.frame[:, :, :3]

    def next(self):
        frame, mask = self.frame, self.mask
        if self.width <= 0 and self.height <= 0:
            pass
        else:
            if self.width > 0 and self.height > 0:
                pass
            elif self.width > 0:
                self.height = self.width * frame.shape[0] // frame.shape[1]
            elif self.height > 0:
                self.width = self.height * frame.shape[1] // frame.shape[0]
            frame = cv2.resize(frame, (self.width, self.height))
            if mask is not None:
                mask = cv2.resize(mask, (self.width, self.height))
        return (True, frame, mask)


class GIFProvider(Provider):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cap = None
        self.time = 0
        if 'path' in kwargs:
            self.path = kwargs['path']

    def loadVideo(self, path):
        self.path = path
        self.reset()

    def stop(self):
        pass

    def reset(self):
        self.stop()
        self.cap = Image.open(self.path)
        logging.debug("reload {}".format(self.path))
        if self.width <= 0 and self.width <= 0:
            self.width, self.height = self.cap.size
        else:
            if self.width > 0 and self.height > 0:
                pass
            elif self.width > 0:
                self.height = self.width * self.cap.size[1] // self.cap.size[0]
            elif self.height > 0:
                self.width = self.height * self.cap.size[0] // self.cap.size[1]

    def next(self):
        try:
            self.cap.seek(self.cap.tell()+1)
            #frame = self.cap.convert('RGB')
            frame = np.array(self.cap.convert('RGBA'), dtype=np.uint8)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGRA)
            if self.width <= 0 and self.height <= 0:
                pass
            else:
                if self.width > 0 and self.height > 0:
                    pass
                elif self.width > 0:
                    self.height = self.width * frame.shape[0] // frame.shape[1]
                elif self.height > 0:
                    self.width = self.height * frame.shape[1] // frame.shape[0]
                frame = cv2.resize(frame, (self.width, self.height))
            mask = frame[:, :, 3]
            frame = frame[:, :, :3]
            # delay returning frame
            duration = self.cap.info['duration'] / 1000
            sleep = self.time + duration - time.time()
            if sleep > 0:
                time.sleep(sleep)
            self.time = time.time()
            return (True, frame, mask)
        except EOFError:
            return (False, None, None)


class LayerProvider(Provider):

    def __init__(self, layer, **kwargs):
        self.layer = layer
        super().__init__(**kwargs)

    def stop(self):
        pass

    def reset(self):
        pass

    def next(self):
        frame = self.layer.getFrame()
        mask = self.layer.getMask()
        ret = self.layer.dorun
        if frame is not None:
            if self.width <= 0 and self.height <= 0:
                pass
            else:
                if self.width > 0 and self.height > 0:
                    pass
                elif self.width > 0:
                    self.height = self.width * frame.shape[0] // frame.shape[1]
                elif self.height > 0:
                    self.width = self.height * frame.shape[1] // frame.shape[0]
                frame = cv2.resize(frame, (self.width, self.height))
            if mask is not None:
                mask = cv2.resize(mask[0], (frame.shape[1], frame.shape[0])) * 255
        return (ret, frame, mask)


class VideoProvider(Provider):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cap = None
        self.time = 0
        if 'path' in kwargs:
            self.path = kwargs['path']

    def loadVideo(self, path):
        self.path = path
        self.reset()

    def stop(self):
        if self.cap is not None:
            self.cap.release()

    def reset(self):
        self.stop()
        self.cap = cv2.VideoCapture(self.path)

        # TODO: this feature is broken as opencv is unable to open video/gif WITH alpha channel contrary to their statement
        # if this is fixed, GIFProvider is deprecated as this would support alpha channel
        convert = self.cap.get(cv2.CAP_PROP_CONVERT_RGB)
        if convert == 1.0:
            logging.debug(self.cap.get(cv2.CAP_PROP_CONVERT_RGB))
            logging.debug(self.cap.set(cv2.CAP_PROP_CONVERT_RGB, 0.0))
            logging.debug(self.cap.get(cv2.CAP_PROP_CONVERT_RGB))

        self.frametime = 1 / self.cap.get(cv2.CAP_PROP_FPS)
        if self.width <= 0 and self.width <= 0:
            self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        else:
            if self.width > 0 and self.height > 0:
                pass
            elif self.width > 0:
                self.height = int(self.width * self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT) // self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            elif self.height > 0:
                self.width = int(self.height * self.cap.get(cv2.CAP_PROP_FRAME_WIDTH) // self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        logging.debug("reload {}, fps: {}".format(self.path, self.cap.get(cv2.CAP_PROP_FPS)))

    def next(self):
        mask = None
        ret, frame = self.cap.read()
        if ret == True:
            if self.width <= 0 and self.height <= 0:
                pass
            else:
                if self.width > 0 and self.height > 0:
                    pass
                elif self.width > 0:
                    self.height = self.width * frame.shape[0] // frame.shape[1]
                elif self.height > 0:
                    self.width = self.height * frame.shape[1] // frame.shape[0]
                frame = cv2.resize(frame, (self.width, self.height))
            if frame.shape[2] == 4:
                mask = frame[:, :, 3]
                frame = frame[:, :, :3]

            # delay returning frame
            sleep = self.time + self.frametime - time.time()
            if sleep > 0:
                time.sleep(sleep)
            self.time = time.time()
        return (ret, frame, mask)


class CameraProvider(Provider):

    def __init__(self, **kwargs):
        self.cap = None
        self.time = 0
        super().__init__(**kwargs)

    def setParams(self, kwargs):
        super().setParams(kwargs)
        if 'device' in kwargs:
            self.device = kwargs['device']

    def stop(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

    def reset(self):
        self.stop()
        logging.debug("reload camera {}".format(self.device))

    def next(self):
        if self.cap is None:
            self.cap = cv2.VideoCapture(self.device)
            #self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            #self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            #self.cap.set(cv2.CAP_PROP_FPS, self.fps)
        # get frame
        mask = None
        ret, frame = self.cap.read()
        if ret == True:
            if self.width <= 0 and self.height <= 0:
                pass
            else:
                if self.width > 0 and self.height > 0:
                    pass
                elif self.width > 0:
                    self.height = self.width * frame.shape[0] // frame.shape[1]
                elif self.height > 0:
                    self.width = self.height * frame.shape[1] // frame.shape[0]
                frame = cv2.resize(frame, (self.width, self.height))
                if mask is not None:
                    mask = cv2.resize(mask, (self.width, self.height))
        return (ret, frame, mask)


class DesktopProvider(Provider):

    def __init__(self, **kwargs):
        self.sct = None
        self.monitor = None
        kwargs.setdefault('monitor', {"top": 0, "left": 0, "width": 1920, "height": 1080})
        super().__init__(**kwargs)

    def setParams(self, kwargs):
        super().setParams(kwargs)
        if 'monitor' in kwargs:
            self.monitor = kwargs['monitor']

    def stop(self):
        self.sct = None

    def reset(self):
        self.stop()
        self.sct = mss.mss()
        r = 10
        self.r = r
        self.circ = np.zeros((r*2,r*2), np.uint8) + 255
        circm = np.zeros((r*2,r*2), np.float)
        cv2.circle(circm, (r,r), r, (0.5), -1)
        self.circ = self.circ * circm
        self.circminv = 1 - circm

    def next(self):
        # get screen frame
        frame = np.array(self.sct.grab(self.monitor))[:,:,:3] # is the 4th channel of any use...?
        # draw current mouse position
        x,y = mouseinfo.position()
        x = max(self.r, min(frame.shape[1]-self.r, x))
        y = max(self.r, min(frame.shape[0]-self.r, y))
        frame[y-self.r:y+self.r,x-self.r:x+self.r,2] = frame[y-self.r:y+self.r,x-self.r:x+self.r,2] * self.circminv[:,:] + self.circ[:,:]
        for c in range(2):
            frame[y-self.r:y+self.r,x-self.r:x+self.r,c] = frame[y-self.r:y+self.r,x-self.r:x+self.r,c] * self.circminv[:,:]
        # resize if necessary
        if self.width <= 0 and self.height <= 0:
            pass
        else:
            if self.width > 0 and self.height > 0:
                pass
            elif self.width > 0:
                self.height = self.width * frame.shape[0] // frame.shape[1]
            elif self.height > 0:
                self.width = self.height * frame.shape[1] // frame.shape[0]
            frame = cv2.resize(frame, (self.width, self.height))
        return (True, frame, None)


class TextProvider(Provider):

    def __init__(self, text="empty", **kwargs):
        self.dx = 0
        kwargs['text'] = text
        kwargs.setdefault('size', 3)
        kwargs.setdefault('thickness', 3)
        kwargs.setdefault('fgcolor', (0, 255, 0))
        kwargs.setdefault('bgcolor', None)
        super().__init__(**kwargs)

    def setParams(self, kwargs):
        super().setParams(kwargs)
        if 'text' in kwargs:
            self.text = kwargs['text']
        if 'size' in kwargs:
            self.size = kwargs['size']
        if 'thickness' in kwargs:
            self.thickness = kwargs['thickness']
        if 'fgcolor' in kwargs:
            self.fgcolor = kwargs['fgcolor']
        if 'bgcolor' in kwargs:
            self.bgcolor = kwargs['bgcolor']

    def stop(self):
        pass

    def reset(self):
        self.stop()
        (width, height), baseline = cv2.getTextSize(self.text, cv2.FONT_HERSHEY_SIMPLEX, self.size, self.thickness)
        if self.bgcolor is not None:
            pad = baseline // 4
            self.frame = np.zeros((height + baseline + pad*2, width + pad*2, 3), np.uint8)
            self.frame[:,:] = self.bgcolor
            cv2.putText(self.frame, self.text, (pad, height - 1 + pad), cv2.FONT_HERSHEY_SIMPLEX, self.size, self.fgcolor, self.thickness)
            self.mask = None
        else:
            self.frame = np.zeros((height + baseline, width, 3), np.uint8)
            cv2.putText(self.frame, self.text, (0, height - 1), cv2.FONT_HERSHEY_SIMPLEX, self.size, self.fgcolor, self.thickness)
            self.mask = np.zeros((height + baseline, width, 1), np.uint8)
            cv2.putText(self.mask, self.text, (0, height - 1), cv2.FONT_HERSHEY_SIMPLEX, self.size, (255), self.thickness)

    def next(self):
        frame, mask = self.frame, self.mask
        if self.width <= 0 and self.height <= 0:
            pass
        else:
            if self.width > 0 and self.height > 0:
                pass
            elif self.width > 0:
                self.height = self.width * frame.shape[0] // frame.shape[1]
            elif self.height > 0:
                self.width = self.height * frame.shape[1] // frame.shape[0]
            frame = cv2.resize(frame, (self.width, self.height))
            if mask is not None:
                mask = cv2.resize(mask, (self.width, self.height))
        return (True, frame, mask)


class CommandlineProvider(TextProvider):

    def __init__(self, clicommand=['date', '+%T'], frequency=1.0, **kwargs):
        self.t = 0
        kwargs['clicommand'] = clicommand
        kwargs['frequency'] = frequency
        super().__init__(**kwargs)

    def setParams(self, kwargs):
        super().setParams(kwargs)
        if 'clicommand' in kwargs:
            self.clicommand = kwargs.pop('clicommand', None)
        if 'frequency' in kwargs:
            self.frequency = kwargs.pop('frequency', None)

    def next(self):
        t = time.time()
        if t - self.t > self.frequency:
            output = subprocess.check_output(self.clicommand).decode("utf-8").replace('\n', '')
            self.setParams({'text': output})
            self.reset()
            self.t = t
        return super().next()


class Frequency(Provider):

    def __init__(self, fps, provider, **kwargs):
        self.time = 0
        kwargs['provider'] = provider
        kwargs['fps'] = fps
        super().__init__(**kwargs)

    def setParams(self, kwargs):
        super().setParams(kwargs)
        self.provider.setParams(kwargs)
        if 'fps' in kwargs:
            self.frametime = 1 / kwargs['fps']
            if kwargs['fps'] <= 0:
                self.frametime = 0
            else:
                self.frametime = 1 / kwargs['fps']

    def stop(self):
        self.provider.stop()

    def reset(self):
        self.provider.reset()

    def next(self):
        ret, frame, mask = self.provider.next()
        # delay returning frame
        sleep = self.time + self.frametime - time.time()
        if sleep > 0:
            time.sleep(sleep)
        self.time = time.time()
        return (ret, frame, mask)


class Looper(Provider):

    def __init__(self, provider, **kwargs):
        kwargs['provider'] = provider
        super().__init__(**kwargs)

    def setParams(self, kwargs):
        super().setParams(kwargs)
        self.provider.setParams(kwargs)

    def stop(self):
        self.provider.stop()

    def reset(self):
        self.provider.reset()

    def next(self):
        ret, frame, mask = self.provider.next()
        if ret == False:
            self.provider.reset()
            ret, frame, mask = self.provider.next()
        return (ret, frame, mask)


class OnPress(Provider):

    def __init__(self, key, provider, **kwargs):
        self.lasttriggercount = 0
        self.triggercount = 0
        kwargs['key'] = key
        kwargs['provider'] = provider
        super().__init__(**kwargs)

    def setParams(self, kwargs):
        super().setParams(kwargs)
        if 'key' in kwargs:
            self.key = kwargs.pop('key', ord(' '))
        self.provider.setParams(kwargs)

    def stop(self):
        self.provider.stop()

    def reset(self):
        self.provider.reset()

    def next(self):
        frame, mask = (None, None)
        if self.triggercount > self.lasttriggercount:
            if self.lasttriggercount > 0:
                self.triggercount = 0
                self.lasttriggercount = 0
            self.provider.reset()
            self.lasttriggercount = self.triggercount
        if self.triggercount > 0:
            ret, frame, mask = self.provider.next()
            if ret == False:
                self.triggercount = 0
                self.lasttriggercount = 0
        else:
            time.sleep(0.033)
        return (True, frame, mask)

    def command(self, **kwargs):
        if kwargs.get('keypress', -1) == self.key:
            kwargs.pop('keypress', None)
            self.triggercount += 1
            return True
        return super().command(**kwargs)


class Boomerang(Provider):

    class Status(Enum):
        ACTIVE = 1
        INACTIVE = 2
        TRANSITION = 3

    def __init__(self, duration, key, provider, **kwargs):
        self.frames = collections.deque([])
        self.status = Boomerang.Status.INACTIVE
        kwargs.setdefault('fakelagduration', 1.0)
        kwargs['duration'] = duration
        kwargs['key'] = key
        kwargs['provider'] = provider
        super().__init__(**kwargs)

    def setParams(self, kwargs):
        super().setParams(kwargs)
        if 'duration' in kwargs:
            self.duration = kwargs.pop('duration', 2)
        if 'key' in kwargs:
            self.key = kwargs.pop('key', ord(' '))
        if 'fakelagduration' in kwargs:
            self.fakelagduration = kwargs.pop('fakelagduration', 0)
        self.provider.setParams(kwargs)

    def stop(self):
        self.provider.stop()

    def reset(self):
        self.provider.reset()

    def next(self):
        ret, frame, mask = self.provider.next()
        t = time.time()
        # save frames
        self.frames.append({'frame': frame, 'mask': mask, 'time': t})
        while self.frames[0]['time'] + self.duration < t:
            self.frames.popleft()

        if self.status == Boomerang.Status.ACTIVE:
            frame = self.boomerang[len(self.boomerang)-1-self.boomerangidx]['frame']
            mask = self.boomerang[len(self.boomerang)-1-self.boomerangidx]['mask']
            if self.boomerangidx == 0 or self.boomerangidx == len(self.boomerang) - 1:
                self.boomerangidx, self.boomeranglastidx = self.boomeranglastidx, self.boomerangidx
            else:
                tmp = self.boomerangidx
                self.boomerangidx += 1 if self.boomerangidx >= self.boomeranglastidx else -1
                self.boomeranglastidx = tmp
            
            # sleep until t + delta
            future = self.t + abs(self.boomerang[self.boomerangidx]['time'] - self.boomerang[self.boomeranglastidx]['time'])
            sleep = future - time.time()
            if sleep > 0:
                time.sleep(sleep)
            ret = True
        elif self.status == Boomerang.Status.TRANSITION:
            if t < self.triggertime + self.fakelagduration:
                frame = self.boomerang[len(self.boomerang)-1-self.boomerangidx]['frame']
                mask = self.boomerang[len(self.boomerang)-1-self.boomerangidx]['mask']
            else:
                self.status = Boomerang.Status.INACTIVE
        self.t = t
        return (ret, frame, mask)

    def command(self, **kwargs):
        if kwargs.get('keypress', -1) == self.key:
            kwargs.pop('keypress', None)
            if self.status == Boomerang.Status.INACTIVE or self.status == Boomerang.Status.TRANSITION:
                self.status = Boomerang.Status.ACTIVE
                self.boomerangidx = 1
                self.boomeranglastidx = 0
                self.boomerang = self.frames.copy()
            elif self.status == Boomerang.Status.ACTIVE:
                self.status = Boomerang.Status.TRANSITION
            self.triggertime = time.time()
            logging.info("Set boomerang to: {}".format(self.status))
            return True
        return super().command(**kwargs)


class HorizontalShift(Provider):

    def __init__(self, provider, **kwargs):
        self.dx = 0
        kwargs.setdefault('speed', 3)
        kwargs.setdefault('padpercentage', 0.5)
        kwargs['provider'] = provider
        super().__init__(**kwargs)

    def setParams(self, kwargs):
        super().setParams(kwargs)
        if 'speed' in kwargs:
            self.speed = kwargs.pop('speed', None)
        if 'dimension' in kwargs:
            kwargs['dimension'] = (-1, -1)
        if 'padpercentage' in kwargs:
            self.padpercentage = kwargs.pop('padpercentage', None)
        self.provider.setParams(kwargs)

    def stop(self):
        self.provider.stop()

    def reset(self):
        self.provider.reset()

    def next(self):
        ret, frame, mask = self.provider.next()
        if frame is None or (self.width <= 0 and self.height <= 0):
            pass
        else:
            if self.width > 0 and self.height > 0:
                pass
            elif self.width > 0:
                self.height = frame.shape[0]
            elif self.height > 0:
                frame = cv2.resize(frame, (frame.shape[1] * self.height // frame.shape[0], self.height))
                self.width = frame.shape[1]

            pad = int(self.width * self.padpercentage)

            res = np.zeros((self.height, self.width, 3), dtype=np.uint8)
            rmask = np.zeros((self.height, self.width), dtype=np.uint8)
            frame = cv2.resize(frame, (frame.shape[1] * self.height // frame.shape[0], self.height))
            if mask is not None:
                mask = cv2.resize(mask, (frame.shape[1] * self.height // frame.shape[0], self.height))

            if frame.shape[1] > self.width:
                if mask is None and pad > 0:
                    mask = np.zeros((frame.shape[0], frame.shape[1]), np.uint8) + 255
                frame = cv2.copyMakeBorder(frame, 0, 0, 0, pad, cv2.BORDER_CONSTANT, None, 0)
                d1 = self.dx % frame.shape[1]
                d2 = d1 + self.width
                d3, d4 = 0, 0
                if d2 > frame.shape[1]:
                    d4 = d2 - frame.shape[1]
                    d2 = frame.shape[1]
                res[:, :(d2-d1), :] = frame[:, d1:d2, :]
                res[:, (d2-d1):, :] = frame[:, d3:d4, :]
                rmask[:, :] = 255
                if mask is not None:
                    mask = cv2.copyMakeBorder(mask, 0, 0, 0, pad, cv2.BORDER_CONSTANT, None, 0)
                    rmask[:, :(d2-d1)] = mask[:, d1:d2]
                    rmask[:, (d2-d1):] = mask[:, d3:d4]
            else:
                res = cv2.copyMakeBorder(res, 0, 0, 0, pad, cv2.BORDER_CONSTANT, None, 0)
                rmask = cv2.copyMakeBorder(rmask, 0, 0, 0, pad, cv2.BORDER_CONSTANT, None, 0)
                d1 = self.dx % res.shape[1]
                d2 = d1 + frame.shape[1]
                d3, d4 = 0, 0
                if d2 > res.shape[1]:
                    d4 = d2 - res.shape[1]
                    d2 = res.shape[1]
                res[:, d1:d2, :] = frame[:, :(d2-d1), :]
                res[:, d3:d4, :] = frame[:, (d2-d1):, :]
                rmask[:, d1:d2] = 255
                rmask[:, d3:d4] = 255
                if mask is not None:
                    rmask[:, d1:d2] = mask[:, :(d2-d1)]
                    rmask[:, d3:d4] = mask[:, (d2-d1):]
                if pad > 0:
                    res = res[:, :-pad, :]
                    rmask = rmask[:, :-pad]

            self.dx += self.speed
            frame = res
            mask = rmask
        return (ret, frame, mask)


class BodypixProvider(Provider):

    def __init__(self, provider, **kwargs):
        kwargs['provider'] = provider
        super().__init__(**kwargs)

    def setParams(self, kwargs):
        super().setParams(kwargs)
        kwargs['dimension'] = (-1, -1)
        self.provider.setParams(kwargs)

    def stop(self):
        self.provider.stop()

    def reset(self):
        self.provider.reset()

    def next(self):
        ret, frame, mask = self.provider.next()
        if frame is not None:
            mask = self.getMask(frame)
            if self.width <= 0 and self.height <= 0:
                pass
            else:
                if self.width > 0 and self.height > 0:
                    pass
                elif self.width > 0:
                    self.height = self.width * frame.shape[0] // frame.shape[1]
                elif self.height > 0:
                    self.width = self.height * frame.shape[1] // frame.shape[0]
                frame = cv2.resize(frame, (self.width, self.height))
                if mask is not None:
                    mask = cv2.resize(mask, (self.width, self.height))
        return (ret, frame, mask)

    def getMask(self, frame, bodypix_url='http://localhost:9000', scale=0.25):
        sframe = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
        _, data = cv2.imencode(".jpg", sframe)
        r = requests.post(
            url=bodypix_url,
            data=data.tobytes(),
            headers={'Content-Type': 'application/octet-stream'})
        mask = np.frombuffer(r.content, dtype=np.uint8)
        mask = mask.reshape((sframe.shape[0], sframe.shape[1])) * 255
        mask = cv2.resize(mask, (frame.shape[1], frame.shape[0]), interpolation=cv2.INTER_LINEAR)
        return mask


class Filter(Provider):

    __metaclass__ = abc.ABCMeta

    def __init__(self, key, provider, **kwargs):
        self.triggercount = 0
        kwargs['key'] = key
        kwargs['provider'] = provider
        super().__init__(**kwargs)

    def setParams(self, kwargs):
        super().setParams(kwargs)
        if 'key' in kwargs:
            self.key = kwargs.pop('key', ord(' '))
        self.provider.setParams(kwargs)

    def stop(self):
        self.provider.stop()

    def reset(self):
        self.provider.reset()

    def next(self):
        ret, frame, mask = self.provider.next()
        if frame is not None:
            frame, mask = self.applyFilter(frame, mask)
        return (ret, frame, mask)

    @abc.abstractmethod
    def applyFilter(self, frame, mask):
        pass

    def command(self, **kwargs):
        if kwargs.get('keypress', -1) == self.key:
            kwargs.pop('keypress', None)
            self.triggercount += 1
            return True
        return super().command(**kwargs)


class SmoothingFilter(Filter):

    def applyFilter(self, frame, mask):
        if self.triggercount % 2 == 1:
            frame = cv2.bilateralFilter(frame,9,75,75)
        return (frame, mask)


class InvertFilter(Filter):

    def applyFilter(self, frame, mask):
        if self.triggercount % 2 == 1:
            frame = cv2.bitwise_not(frame)
        return (frame, mask)


class HologramFilter(Filter):

    def shift_image(self, img, dx, dy):
        img = np.roll(img, dy, axis=0)
        img = np.roll(img, dx, axis=1)
        if dy > 0:
            img[:dy, :] = 0
        elif dy < 0:
            img[dy:, :] = 0
        if dx > 0:
            img[:, :dx] = 0
        elif dx < 0:
            img[:, dx:] = 0
        return img

    def hologram_effect(self, img):
        # add a blue tint
        holo = cv2.applyColorMap(img, cv2.COLORMAP_WINTER)
        # add a halftone effect
        bandLength, bandGap = 2, 3
        for y in range(holo.shape[0]):
            if y % (bandLength+bandGap) < bandLength:
                holo[y,:,:] = holo[y,:,:] * np.random.uniform(0.1, 0.3)
        # add some ghosting
        holo_blur = cv2.addWeighted(holo, 0.2, self.shift_image(holo.copy(), 5, 5), 0.8, 0)
        holo_blur = cv2.addWeighted(holo_blur, 0.4, self.shift_image(holo.copy(), -5, -5), 0.6, 0)
        # combine with the original color, oversaturated
        out = cv2.addWeighted(img, 0.5, holo_blur, 0.6, 0)
        return out

    def applyFilter(self, frame, mask):
        if self.triggercount % 2 == 1:
            frame = self.hologram_effect(frame)
        return (frame, mask)
