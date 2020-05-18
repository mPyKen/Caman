import logging
import sys

from src.Layer import *
from src.Provider import *

def meeting(width, height):
    bg = np.zeros((height, width, 3), np.uint8) + 34
    layers = [
        #AnimatedLayer(position=(800,550),   dimension=(width//4,-1), level=4, frame=None, mask=None, provider=Looper(GIFProvider(path="res/dancing-penguin.gif"))),
        AnimatedLayer(position=(286,328),   dimension=(707,67), level=4, frame=None, mask=None, provider=Frequency(24, HorizontalShift(ImageProvider("res/name.png")))),
        AnimatedLayer(position=(500,600), dimension=(250,-1),             level=7, frame=None, mask=None, provider=Frequency(2, CommandlineProvider(size=3, fgcolor=(255,255,255)))),
    ]
    return (bg, layers)

def virtualbackground(width, height):
    bg = cv2.imread("res/background.jpg")
    layers = [
        AnimatedLayer(position=(0,0),   dimension=(width,height), level=6, frame=None, mask=None, provider=HologramFilter(ord('h'), SmoothingFilter(ord('s'), InvertFilter(ord('i'), Boomerang(2.0, ord(' '), BodypixProvider(CameraProvider(device=0))))))),
    ]
    return (bg, layers)

def webcam(width, height):
    bg = np.zeros((height, width, 3), np.uint8) + 128
    layers = [
        AnimatedLayer(position=(0,0),   dimension=(width,height), level=6, frame=None, mask=None, provider=HologramFilter(ord('h'), SmoothingFilter(ord('s'), InvertFilter(ord('i'), Boomerang(2.0, ord(' '), CameraProvider(device=0)))))),
    ]
    return (bg, layers)

def screenshare(width, height):
    bg = np.zeros((height, width, 3), np.uint8) + 128
    layers = [
        AnimatedLayer(position=(0,0),                   dimension=(width,height),       level=2, frame=None, mask=None, provider=Frequency(20, DesktopProvider())),
        #AnimatedLayer(position=(width*6//10,height//2), dimension=(width//2,height//2), level=6, frame=None, mask=None, provider=Boomerang(2.0, ord(' '), BodypixProvider(CameraProvider(device=0)))),
        AnimatedLayer(position=(width*75//100,height*7//10), dimension=(width*3//10,height*3//10), level=6, frame=None, mask=None, provider=HologramFilter(ord('h'), SmoothingFilter(ord('s'), InvertFilter(ord('i'), Boomerang(2.0, ord(' '), BodypixProvider(CameraProvider(device=0))))))),
    ]
    return (bg, layers)

def loadConfig(width, height):
    bg = np.zeros((height, width, 3), np.uint8) + 128
    #bg, layer = webcam(width, height)
    #bg, layer = meeting(width, height)
    bg, layer = virtualbackground(width, height)
    #bg, layer = screenshare(width, height)
    #layer.append(AnimatedLayer(position=(550,600), dimension=(150,-1), level=7, frame=None, mask=None, provider=Frequency(20, CommandlineProvider(size=3, fgcolor=(255,255,255)))))
    #layer.append(AnimatedLayer(position=(0,600),   dimension=(width//4,height//4), level=5, frame=None, mask=None, provider=Looper(GIFProvider(path="res/dancing-penguin.orig.gif"))))

    #return (bg, layer)

    back = ImageLayer   (position=(0,0),     dimension=(width,height),       level=1, frame=None, mask=None, path="res/background.jpg")
    vid  = AnimatedLayer(position=(0,0),     dimension=(width//3,-1),        level=2, frame=None, mask=None, provider=VideoProvider(path="res/Tabletennis.mp4"))
    vid2  = AnimatedLayer(position=(800,0),     dimension=(width//3,height//3),        level=2, frame=None, mask=None, provider=HorizontalShift(VideoProvider(path="res/Tabletennis.mp4"), padpercentage=0.0))
    gif  = AnimatedLayer(position=(500,300),   dimension=(width//4,height//4), level=5, frame=None, mask=None, provider=Looper(GIFProvider(path="res/dancing-penguin.gif")))
    #cam  = AnimatedLayer(position=(0,0),     dimension=(width,height),       level=3, frame=None, mask=None, provider=HorizontalShift(BodypixProvider(CameraProvider(device=0)), speed=6))
    cam  = AnimatedLayer(position=(0,400),   dimension=(width//3,height//3), level=3, frame=None, mask=None, provider=Boomerang(2.0, ord(' '), BodypixProvider(CameraProvider(device=0))))
    dup  = AnimatedLayer(position=(900,400), dimension=(width//3,height//3), level=4, frame=None, mask=None, provider=Frequency(20, HorizontalShift(LayerProvider(cam, fps=30), padpercentage=0.0)))
    text = AnimatedLayer(position=(550,100), dimension=(150,-1),             level=7, frame=None, mask=None, provider=Frequency(20, HorizontalShift(TextProvider("long text "))))

    layers = [
        back,
        vid,
        vid2,
        gif,
        cam,
        dup,
        text,
    ]
    return (bg, layers)

