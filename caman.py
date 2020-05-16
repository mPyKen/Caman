#!python3
import sys
import time
import threading
import logging
import traceback
from collections import defaultdict
import numpy as np
import cv2

from src.Layer import *
from src.Provider import *
from src.pyfakewebcam import *

import importlib
import config

class Caman():

    def __init__(self, **kwargs):
        self.layers = []
        self.keystatus = defaultdict(int)
        self.width = kwargs['dimension'][0]
        self.height = kwargs['dimension'][1]
        self.mousemode = ["", "", ""]
        self.mousepos = (0, 0)

    def reloadConfig(self):
        try:
            importlib.reload(config)
            bg, newlayers = config.loadConfig(self.width, self.height)
            if newlayers is not None and bg is not None:
                self.shutdownLayers()
                self.background = cv2.resize(bg, (self.width, self.height))
                self.layers = newlayers
                self.updateLayerOrder()
                self.startLayers()
        except Exception:
            print(traceback.format_exc())

    def updateLayerOrder(self):
        self.layers.sort(key=lambda layer: layer.level)

    def renderLayers(self):
        # render all layers
        render = self.background.copy()
        for layer in self.layers:
            # skip if layer is disabled or if frame is empty
            if layer.level < 0:
                continue
            frame = layer.getFrame()
            if frame is None:
                continue

            # get bounding box of layer
            area = [layer.posy, layer.posx, layer.posy + layer.height, layer.posx + layer.width]
            crop = [0, 0, frame.shape[0], frame.shape[1]]
            # calculate the part that has to be drawn if it exceeds any border
            for i in (0, 1):
                if area[i] < 0:
                    crop[i] = -area[i]
                    area[i] = 0
            for i in (2, 3):
                if area[i] > self.background.shape[i-2]:
                    crop[i] -= area[i] - self.background.shape[i-2]
                    area[i] = self.background.shape[i-2]
            
            #if area[0] > self.height or area[1] > self.width or area[2] <= 0 or area[3] <= 0:
            if crop[2] - crop[0] <= 0 or crop[3] - crop[1] < 0:
                layer.level = -layer.level
                continue

            # composite layer with alpha blending
            mask = layer.getMask()
            try:
                # put this into a try-except block. reason: resizing with mouse can cause conflict between updated layer.width and current layer.width
                if mask is None:
                    render[area[0]:area[2], area[1]:area[3], :] = frame[crop[0]:crop[2],crop[1]:crop[3],:]
                else:
                    for c in range(frame.shape[2]):
                        render[area[0]:area[2], area[1]:area[3],c] \
                            = frame[crop[0]:crop[2],crop[1]:crop[3],c] * mask[0][crop[0]:crop[2],crop[1]:crop[3]] \
                            + render[area[0]:area[2], area[1]:area[3],c] * mask[1][crop[0]:crop[2],crop[1]:crop[3]]
            except:
                print(traceback.format_exc())
        return render

    def handleInput(self):
        # receive keyboard input
        key = cv2.waitKey(1)
        self.keystatus[key] += 1
        if key == 27:
            return False
        elif key == ord('r'):
            self.reloadConfig()
        elif key == -1:
            pass
        else:
            print(key)
            for layer in reversed(self.layers):
                if layer.command(keypress=key):
                    break
        return True

    def findLayerAt(self, x, y):
        for layer in reversed(self.layers):
            if layer.level >= 0:
                if layer.posx <= x and layer.posy <= y and x <= layer.posx + layer.width and y <= layer.posy + layer.height:
                    return layer
        return None

    def closestPointLine(self, p1, p2, p3):
        # finds closest point between line (through p1 and p2) and p3
        d1 = (p2[1] - p1[1]) / (p2[0] - p1[0])
        z1 = p2[1] - d1*p2[0] # mx+y -> d1*x+z1
        d2 = -1/d1
        z2 = p3[1] - d2*p3[0] # mx+y -> d2*x+z2
        x = (z2-z1) / (d1 - d2)
        y = d1*x + z1
        return (int(x), int(y))

    def mouse(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.mousemode[0] = "down"
            self.grabbedlayer = self.findLayerAt(x, y)
            self.grabbedlayerpos = (self.grabbedlayer.posx, self.grabbedlayer.posy)
            self.grabbedlayerdim = (self.grabbedlayer.width, self.grabbedlayer.height)
            self.grabbedmousepos = (x, y)
            dx = (x - self.grabbedlayerpos[0]) / self.grabbedlayerdim[0]
            dy = (y - self.grabbedlayerpos[1]) / self.grabbedlayerdim[1]
            dx = int(dx*3)
            dy = int(dy*3)
            # create following grid. 0,2,6,8 scales according to aspect ratio, 1,3,5,7 scales one axis only. 4 moves object.
            # 0 1 2
            # 3 4 5
            # 6 7 8
            self.grabbedeffect = 3*dy + dx
        elif event == cv2.EVENT_MBUTTONDOWN:
            self.mousemode[1] = "down"
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.mousemode[2] = "down"
        elif event == cv2.EVENT_LBUTTONUP:
            self.mousemode[0] = "up"
            self.grabbedlayer = None
        elif event == cv2.EVENT_MBUTTONUP:
            self.mousemode[1] = "up"
            layer = self.findLayerAt(x, y)
            layer.level = -layer.level
        elif event == cv2.EVENT_RBUTTONUP:
            self.mousemode[2] = "up"
        elif event == cv2.EVENT_MOUSEMOVE:
            self.mousepos = (x, y)
            if self.mousemode[0] == "down" and self.grabbedlayer is not None:
                if isinstance(self.grabbedlayer, AnimatedLayer):
                    self.grabbedlayer.pause()
                dx = x - self.grabbedmousepos[0]
                dy = y - self.grabbedmousepos[1]
                tl = (self.grabbedlayerpos[0], self.grabbedlayerpos[1])
                br = (self.grabbedlayerpos[0] + self.grabbedlayerdim[0], self.grabbedlayerpos[1] + self.grabbedlayerdim[1])

                if self.grabbedeffect == 0:
                    x1, y1 = self.closestPointLine(br, tl, (x,y))
                    x2, y2 = self.closestPointLine(br, tl, self.grabbedmousepos)
                    dx, dy = x1 - x2, y1 - y2
                    tl = (tl[0] + dx, tl[1] + dy)
                elif self.grabbedeffect == 2:
                    x1, y1 = self.closestPointLine((br[0], tl[1]), (tl[0], br[1]), (x,y))
                    x2, y2 = self.closestPointLine((br[0], tl[1]), (tl[0], br[1]), self.grabbedmousepos)
                    dx, dy = x1 - x2, y1 - y2
                    tl = (tl[0], tl[1] + dy)
                    br = (br[0] + dx, br[1])
                elif self.grabbedeffect == 6:
                    x1, y1 = self.closestPointLine((br[0], tl[1]), (tl[0], br[1]), (x,y))
                    x2, y2 = self.closestPointLine((br[0], tl[1]), (tl[0], br[1]), self.grabbedmousepos)
                    dx, dy = x1 - x2, y1 - y2
                    tl = (tl[0] + dx, tl[1])
                    br = (br[0], br[1] + dy)
                elif self.grabbedeffect == 8:
                    x1, y1 = self.closestPointLine(br, tl, (x,y))
                    x2, y2 = self.closestPointLine(br, tl, self.grabbedmousepos)
                    dx, dy = x1 - x2, y1 - y2
                    br = (br[0] + dx, br[1] + dy)
                elif self.grabbedeffect == 1:
                    tl = (tl[0], tl[1] + dy)
                elif self.grabbedeffect == 3:
                    tl = (tl[0] + dx, tl[1])
                elif self.grabbedeffect == 5:
                    br = (br[0] + dx, br[1])
                elif self.grabbedeffect == 7:
                    br = (br[0], br[1] + dy)
                elif self.grabbedeffect == 4:
                    tl = (tl[0] + dx, tl[1] + dy)
                    br = (br[0] + dx, br[1] + dy)
                if br[0] - tl[0] <= 0 or br[1] - tl[1] <= 0:
                    self.grabbedlayer.level = -self.grabbedlayer.level
                    self.grabbedlayer = None
                else:
                    self.grabbedlayer.posx = tl[0]
                    self.grabbedlayer.posy = tl[1]
                    self.grabbedlayer.width = br[0] - tl[0]
                    self.grabbedlayer.height = br[1] - tl[1]
                    self.grabbedlayer.updateDimension()
                if isinstance(self.grabbedlayer, AnimatedLayer):
                    self.grabbedlayer.resume()

    def renderAdditionalInfo(self, render, fps):
        cv2.putText(render, "FPS: {}".format(format(fps, '.2f')), (15, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0))
        # show bounding box and a grid for the hovered layer
        if self.keystatus[ord('i')] %2 == 1:
            hoveredlayer = self.findLayerAt(*self.mousepos)
            if hoveredlayer is not None:
                cv2.line(render, (hoveredlayer.posx+hoveredlayer.width//3,  hoveredlayer.posy), (hoveredlayer.posx+hoveredlayer.width//3,  hoveredlayer.posy+hoveredlayer.height), (255, 0, 0, 1))
                cv2.line(render, (hoveredlayer.posx+hoveredlayer.width*2//3,hoveredlayer.posy), (hoveredlayer.posx+hoveredlayer.width*2//3,hoveredlayer.posy+hoveredlayer.height), (255, 0, 0, 1))
                cv2.line(render, (hoveredlayer.posx,hoveredlayer.posy+hoveredlayer.height//3),   (hoveredlayer.posx+hoveredlayer.width,hoveredlayer.posy+hoveredlayer.height//3),   (255, 0, 0, 1))
                cv2.line(render, (hoveredlayer.posx,hoveredlayer.posy+hoveredlayer.height*2//3), (hoveredlayer.posx+hoveredlayer.width,hoveredlayer.posy+hoveredlayer.height*2//3), (255, 0, 0, 1))
                cv2.rectangle(render, (hoveredlayer.posx,hoveredlayer.posy), (hoveredlayer.posx+hoveredlayer.width,hoveredlayer.posy+hoveredlayer.height),(0,255,0), 1)
        return render

    def run(self, **kwargs):
        logging.info("Create camera with dimensions of {}x{}".format(self.width, self.height))

        # setup the fake camera
        self.fake = pyfakewebcam.FakeWebcam('/dev/video20', self.width, self.height, \
            input_pixfmt='BGR', output_pixfmt=v4l2.V4L2_PIX_FMT_YUYV)

        # create named window
        cv2.namedWindow("Caman")

        # initiate all layers
        self.reloadConfig()

        #def chCamLevel(v):
        #    for layer in self.layers:
        #        if isinstance(layer, AnimatedLayer) and isinstance(layer.provider, CameraProvider):
        #            layer.level = v
        #            self.updateLayerOrder(layers)
        #            return
        #for hoveredlayer in self.layers:
        #    if isinstance(hoveredlayer, AnimatedLayer) and isinstance(hoveredlayer.provider, CameraProvider):
        #        cv2.createTrackbar("level", "Caman", hoveredlayer.level, 5, lambda v: chCamLevel(v))
        #        break
        cv2.setMouseCallback('Caman', self.mouse)

        loop = True
        fps = 0.0
        while loop:
            t = time.time()
            render = self.renderLayers()
            # pass to fake
            #render = cv2.cvtColor(render, cv2.COLOR_BGR2RGB)
            self.fake.schedule_frame(render)
            # show info image
            render = self.renderAdditionalInfo(render, fps)
            cv2.imshow("Caman", render)
            loop = self.handleInput()
            # print current fps
            fps = 1 / (time.time() - t);
            #logging.info(fps)

        self.shutdownLayers()
        
        # finalize
        cv2.destroyAllWindows()
        logging.info('Done')
        sys.exit(0)

    def startLayers(self):
        for layer in self.layers:
            if isinstance(layer, AnimatedLayer):
                layer.start()

    def shutdownLayers(self):
        # stop all animated layers
        for layer in self.layers:
            if isinstance(layer, AnimatedLayer):
                layer.stop()
        logging.debug('Waiting for worker threads')
        main_thread = threading.currentThread()
        for t in threading.enumerate():
            if t is not main_thread:
                t.join()

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, format='(%(threadName)-9s) %(message)s',)
    caman = Caman(dimension = (1280, 720))
    try:
        caman.run()
    except:
        caman.shutdownLayers()
        raise

