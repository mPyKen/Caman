#!/usr/bin/env python3
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
import cairo

import numpy as np
import cv2
import threading
import requests


class CamWindow(Gtk.Window):

    def __init__(self):
        super().__init__()
        self.supports_alpha = False
        self.dorun = False
        self.threadlock = threading.Lock()
        self.frame = None
        self.t = None

        self.set_position(Gtk.WindowPosition.CENTER)
        self.set_default_size(480, 270)
        self.set_title("CamWindow")
        self.connect("delete-event", self.onDestroy)

        self.set_app_paintable(True)
        self.connect("draw", self.expose_draw)
        self.connect("screen-changed", self.screen_changed)

        self.set_decorated(False)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK)
        self.connect("button-press-event", self.clicked)

        self.connect("key-press-event", self.key_press_event)

        fixed_container = Gtk.Fixed()
        self.add(fixed_container)
        #button = Gtk.Button.new_with_label("button1")
        #button.set_size_request(100, 100)
        #fixed_container.add(button)

        self.screen_changed(self, None, None)

    def clicked(self, window, event, userdata=None):
        # toggle window manager frames
        window.set_decorated(not window.get_decorated())
        print("Decoration:", window.get_decorated())
        return True

    def key_press_event(self, widget, event):
        keyval = event.keyval
        keyval_name = Gdk.keyval_name(keyval)
        state = event.state
        if keyval_name == "Escape":
            #self.destroy()
            self.close()
            return True
        return False

    def screen_changed(self, widget, old_screen, userdata=None):
        screen = widget.get_screen()
        visual = screen.get_rgba_visual()
        if visual is None:
            print("Your screen does not support alpha channels!")
            visual = screen.get_system_visual()
            self.supports_alpha = False
        else:
            print("Your screen supports alpha channels!")
            self.supports_alpha = True
        widget.set_visual(visual)

    def expose_draw(self, widget, event, userdata=None):
        cr = widget.get_window().cairo_create()
        if self.supports_alpha:
            #print("setting transparent window")
            cr.set_source_rgba(1.0, 1.0, 0.0, 0.0)
        else:
            #print("setting opaque window")
            cr.set_source_rgb(1.0, 1.0, 1.0)
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.paint()
        width, height = widget.get_size()
        if self.frame is None:
            cr.set_source_rgba(1, 0.2, 0.2, 1.0);
            cr.arc(width / 2, height / 2, (width if width < height else height) / 2 - 8 , 0, 2 * 3.14)
            cr.fill()
            cr.stroke()
        else:
            self.threadlock.acquire()
            try:
                frame = self.frame.copy()
            finally:
                self.threadlock.release()
                h, w = frame.shape[:2]
                w, h = height*w//h, height
                frame = cv2.resize(frame, (w, h))
                surf = self.cv2cairo(frame)
                pos = (width - w) // 2
                cr.set_source_surface(surf, pos, 0)
                cr.paint()
        return False

    def cv2cairo(self, buf):
        if buf.shape[2] < 4:
            buf = cv2.cvtColor(buf, cv2.COLOR_BGR2BGRA)
        h,w = buf.shape[:2]
        return cairo.ImageSurface.create_for_data(buf, cairo.FORMAT_ARGB32, w, h)

    def runCam(self):
        cap = cv2.VideoCapture(0)
        while self.dorun == True:
            _, frame = cap.read()
            mask = self.getMask(frame)
            frame[mask==0] = 0
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2BGRA)
            frame[:, :, 3] = mask[:, :]
            self.threadlock.acquire()
            try:
                self.frame = frame
            finally:
                self.threadlock.release()
            self.queue_draw()
        cap.release()

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

    def startCam(self):
        self.dorun = True
        self.t = threading.Thread(target=self.runCam)
        self.t.start()

    def onDestroy(self, widget=None, *data):
        self.dorun = False
        if self.t is not None:
            self.t.join()
        Gtk.main_quit()
        #return False

if __name__ == "__main__":
    window = CamWindow()
    window.startCam()
    window.show_all()
    Gtk.main()
