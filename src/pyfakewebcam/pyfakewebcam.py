import os
import sys
import fcntl
import timeit
import sys

import numpy as np
import pyfakewebcam.v4l2 as _v4l2

import cv2

class FakeWebcam:

    # TODO: add support for more pixfmts
    # TODO: add support for grayscale
    def __init__(self, video_device, width, height, channels=3, input_pixfmt='BGR', output_pixfmt=_v4l2.V4L2_PIX_FMT_YUYV):
        
        if channels != 3:
            raise NotImplementedError('Code only supports inputs with 3 channels right now. You tried to intialize with {} channels'.format(channels))

        if not os.path.exists(video_device):
            sys.stderr.write('\n--- Make sure the v4l2loopback kernel module is loaded ---\n')
            sys.stderr.write('sudo modprobe v4l2loopback devices=1\n\n')
            raise FileNotFoundError('device does not exist: {}'.format(video_device))

        self.input_pixfmt = input_pixfmt
        self._channels = channels
        self._video_device = os.open(video_device, os.O_WRONLY | os.O_SYNC)
                    
        self._settings = _v4l2.v4l2_format()
        self._settings.type = _v4l2.V4L2_BUF_TYPE_VIDEO_OUTPUT
        self._settings.fmt.pix.pixelformat = output_pixfmt
        self._settings.fmt.pix.width = width
        self._settings.fmt.pix.height = height
        self._settings.fmt.pix.field = _v4l2.V4L2_FIELD_NONE
        self._settings.fmt.pix.colorspace = _v4l2.V4L2_COLORSPACE_JPEG
        #self._settings.fmt.pix.colorspace = _v4l2.V4L2_COLORSPACE_SRGB
        #self._settings.fmt.pix.colorspace = _v4l2.V4L2_COLORSPACE_RAW

        if self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_YUYV \
            or self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_YVYU \
            or self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_YYUV:
            self._settings.fmt.pix.bytesperline = width * 2
            self._settings.fmt.pix.sizeimage = width * height * 2
            self._buffer = np.zeros((self._settings.fmt.pix.height, 2*self._settings.fmt.pix.width), dtype=np.uint8)
        elif self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_BGR24 or self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_RGB24:
            self._settings.fmt.pix.bytesperline = width * 3
            self._settings.fmt.pix.sizeimage = width * height * 3
            self._buffer = np.zeros((self._settings.fmt.pix.height, 3*self._settings.fmt.pix.width), dtype=np.uint8)
        elif self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_YUV32 or self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_RGB32:
            self._settings.fmt.pix.bytesperline = width * 4
            self._settings.fmt.pix.sizeimage = width * height * 4
            self._buffer = np.zeros((self._settings.fmt.pix.height, 4*self._settings.fmt.pix.width), dtype=np.uint8)
        else:
            raise NotImplementedError('Code does not support outputs in format {} right now.'.format(self._settings.fmt.pix.pixelformat))

        self._yuv = np.zeros((self._settings.fmt.pix.height, self._settings.fmt.pix.width, 3), dtype=np.uint8)
        
        fcntl.ioctl(self._video_device, _v4l2.VIDIOC_S_FMT, self._settings)

    def print_capabilities(self):
        capability = _v4l2.v4l2_capability()
        print(("get capabilities result", (fcntl.ioctl(self._video_device, _v4l2.VIDIOC_QUERYCAP, capability))))
        print(("capabilities", hex(capability.capabilities)))
        print(("v4l2 driver: {}".format(capability.driver)))

    def schedule_frame(self, frame):
        if frame.shape[0] != self._settings.fmt.pix.height:
            raise Exception('frame height does not match the height of webcam device: {}!={}\n'.format(self._settings.fmt.pix.height, frame.shape[0]))
        if frame.shape[1] != self._settings.fmt.pix.width:
            raise Exception('frame width does not match the width of webcam device: {}!={}\n'.format(self._settings.fmt.pix.width, frame.shape[1]))
        if frame.shape[2] != self._channels:
            raise Exception('num frame channels does not match the num channels of webcam device: {}!={}\n'.format(self._channels, frame.shape[2]))

        if self.input_pixfmt != 'BGR':
            raise NotImplementedError('Code does not support inputs in format {} right now.'.format(self.input_pixfmt))


        if self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_YUYV:
            self._yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
            self._yuv[:, :, 0] = self._yuv[:, :, 0].astype(np.uint16) * 235 // 255 + 16
            self._buffer[:,::2] = self._yuv[:,:,0]
            self._buffer[:,1::4] = self._yuv[:,::2,1]
            self._buffer[:,3::4] = self._yuv[:,::2,2]
        elif self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_YVYU:
            self._yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
            self._yuv[:, :, 0] = self._yuv[:, :, 0].astype(np.uint16) * 235 // 255 + 16
            for i in range(self._settings.fmt.pix.height):
                self._buffer[i,::2] = self._yuv[i,:,0]
                self._buffer[i,1::4] = self._yuv[i,::2,2]
                self._buffer[i,3::4] = self._yuv[i,::2,1]
        elif self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_YYUV:
            self._yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
            self._yuv[:, :, 0] = self._yuv[:, :, 0].astype(np.uint16) * 235 // 255 + 16
            for i in range(self._settings.fmt.pix.height):
                self._buffer[i,::4] = self._yuv[i,::2,0]
                self._buffer[i,1::4] = self._yuv[i,1::2,0]
                self._buffer[i,2::4] = self._yuv[i,::2,1]
                self._buffer[i,3::4] = self._yuv[i,::2,2]
        elif self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_BGR24:
            for i in range(self._settings.fmt.pix.height):
                self._buffer[i,::3] = frame[i,:,0]
                self._buffer[i,1::3] = frame[i,:,1]
                self._buffer[i,2::3] = frame[i,:,2]
        elif self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_RGB24:
            for i in range(self._settings.fmt.pix.height):
                self._buffer[i,::3] = frame[i,:,2]
                self._buffer[i,1::3] = frame[i,:,1]
                self._buffer[i,2::3] = frame[i,:,0]
        elif self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_YUV32:
            self._yuv = cv2.cvtColor(frame, cv2.COLOR_BGR2YUV)
            self._yuv[:, :, 0] = self._yuv[:, :, 0].astype(np.uint16) * 235 // 255 + 16
            for i in range(self._settings.fmt.pix.height):
                self._buffer[i,1::4] = self._yuv[i,:,0]
                self._buffer[i,2::4] = self._yuv[i,:,1]
                self._buffer[i,3::4] = self._yuv[i,:,2]
        elif self._settings.fmt.pix.pixelformat == _v4l2.V4L2_PIX_FMT_RGB32:
            for i in range(self._settings.fmt.pix.height):
                self._buffer[i,1::4] = frame[i,:,2]
                self._buffer[i,2::4] = frame[i,:,1]
                self._buffer[i,3::4] = frame[i,:,0]
        os.write(self._video_device, self._buffer.tostring())

