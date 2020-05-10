#!python3
import os
import time
import collections
import cv2
import numpy as np
import requests
import pyfakewebcam
import mss
from VideoGet import VideoGet

def get_mask(frame, bodypix_url='http://localhost:9000', scale=0.25):
    frame = cv2.resize(frame, (0, 0), fx=scale, fy=scale)
    _, data = cv2.imencode(".jpg", frame)
    r = requests.post(
        url=bodypix_url,
        data=data.tobytes(),
        headers={'Content-Type': 'application/octet-stream'})
    mask = np.frombuffer(r.content, dtype=np.uint8)
    mask = mask.reshape((frame.shape[0], frame.shape[1]))
    mask = cv2.resize(mask, (0, 0), fx=1 / scale, fy=1 / scale, interpolation=cv2.INTER_LINEAR)
    return mask

def shift_image(img, dx, dy):
    img = np.roll(img, dy, axis=0)
    img = np.roll(img, dx, axis=1)
    if dy>0:
        img[:dy, :] = 0
    elif dy<0:
        img[dy:, :] = 0
    if dx>0:
        img[:, :dx] = 0
    elif dx<0:
        img[:, dx:] = 0
    return img

def hologram_effect(img):
    # add a blue tint
    holo = cv2.applyColorMap(img, cv2.COLORMAP_WINTER)
    # add a halftone effect
    bandLength, bandGap = 2, 3
    for y in range(holo.shape[0]):
        if y % (bandLength+bandGap) < bandLength:
            holo[y,:,:] = holo[y,:,:] * np.random.uniform(0.1, 0.3)
    # add some ghosting
    holo_blur = cv2.addWeighted(holo, 0.2, shift_image(holo.copy(), 5, 5), 0.8, 0)
    holo_blur = cv2.addWeighted(holo_blur, 0.4, shift_image(holo.copy(), -5, -5), 0.6, 0)
    # combine with the original color, oversaturated
    out = cv2.addWeighted(img, 0.5, holo_blur, 0.6, 0)
    return out

def run():
    # setup access to the *real* webcam
    height, width = 720, 1280
    video_getter = VideoGet('/dev/video0', width, height, 60).start()

    # setup the fake camera
    fake = pyfakewebcam.FakeWebcam('/dev/video20', width, height)

    # load the virtual background
    background_static = cv2.imread("background.jpg")
    if background_static is None:
        background_static = np.zeros((height,width,3), np.uint8)
        background_static[:, :, :] = (255, 255, 200)

    # load screen capture
    sct = mss.mss()
    monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}

    # initial config
    pause = False
    gaussian = True
    duplicate = False
    people = True
    invert = False
    hologram = False
    desktop = False

    # hologram
    #pause = False
    #gaussian = True
    #duplicate = False
    #people = True
    #invert = False
    #hologram = True
    #desktop = False

    # desktop share
    #pause = False
    #gaussian = False
    #duplicate = False
    #people = True
    #invert = False
    #hologram = False
    #desktop = True

    cv2.imshow("preview", background_static)
    frames = collections.deque([])
    boomeranglen = 2

    dilateit = 2
    t = 0
    while True:
        lastt = t
        t = time.time()

        if not pause:
            if video_getter.stopped:
                break
            frame = video_getter.frame['raw'].copy()
        else:
            frame = boomerang[len(boomerang)-1-boomerangidx]['frame'].copy()
            if boomerangidx == 0 or boomerangidx == len(boomerang) - 1:
                boomerangidx, boomeranglastidx = boomeranglastidx, boomerangidx
            else:
                tmp = boomerangidx
                boomerangidx += 1 if boomerangidx >= boomeranglastidx else -1
                boomeranglastidx = tmp

        # save recent frames for use in boomerang
        frames.append({'frame': frame.copy(), 'time': t})
        while frames[0]['time'] + boomeranglen < t:
            frames.popleft()

        # smoothing option
        if gaussian:
            #frame = cv2.GaussianBlur(frame, (5,5), 0)
            frame = cv2.bilateralFilter(frame,9,75,75)
            #frame = cv2.bilateralFilter(frame,9,125,125)

        # duplicating option
        if duplicate:
            sub = frame[:, int(frame.shape[1]*1/4):int(frame.shape[1]*3/4), :]
            frame = cv2.hconcat([sub, sub])

        # get user mask
        mask = None
        if people:
            while mask is None:
                try:
                    mask = get_mask(frame)
                except:
                    print("mask request failed, retrying")
        else:
            mask = np.ones((frame.shape[0], frame.shape[1]), np.uint8)
        # post process mask
        if hologram:
            mask = cv2.dilate(mask, np.ones((10,10), np.uint8) , iterations=4)
        else:
            mask = cv2.erode(mask, np.ones((10,10), np.uint8) , iterations=1)
            mask = cv2.dilate(mask, np.ones((10,10), np.uint8) , iterations=dilateit)
        mask = cv2.blur(mask.astype(float), (30,30))

        # invert option
        if invert:
            frame = cv2.bitwise_not(frame)

        # hologram option
        if hologram:
            frame = hologram_effect(frame)
        
        # desktop option, default to background image
        if desktop:
            background = np.array(sct.grab(monitor))
            x,y,w,h = cv2.getWindowImageRect("preview")
            if w > 0:
                cv2.rectangle(background, (x,y), (x+w,y+h), (70, 70, 70), -1)
        else:
            background = background_static
        background_scaled = cv2.resize(background, (width, height))
        # composite the foreground and background
        inv_mask = 1-mask
        for c in range(frame.shape[2]):
            frame[:,:,c] = frame[:,:,c]*mask + background_scaled[:,:,c]*inv_mask

        cv2.imshow("preview", frame)
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        fake.schedule_frame(frame)
        key = cv2.waitKey(1)
        if key == 27:
            break;
        elif key == ord(' '):
            pause = not pause
            if pause:
                boomerangidx = 1
                boomeranglastidx = 0
                boomerang = frames.copy()
            else:
                del boomerang
        elif key == ord('g'):
            gaussian = not gaussian
        elif key == ord('d'):
            duplicate = not duplicate
        elif key == ord('p'):
            people = not people
        elif key == ord('i'):
            invert = not invert
        elif key == ord('h'):
            hologram = not hologram
        elif key == 13: # Enter
            desktop = not desktop
        elif key == -1:
            pass
        elif key == ord('+'):
            dilateit += 1
        elif key == ord('-'):
            dilateit = max(1, dilateit-1)
        else:
            print(key)

        # pause after frame to adapt to original capture for boomerang
        if pause:
            # sleep until t + delta
            future = t + abs(boomerang[boomerangidx]['time'] - boomerang[boomeranglastidx]['time'])
            sleep = future - time.time()
            if sleep > 0:
                time.sleep(sleep)
        print(1 / (time.time() - t))

    video_getter.stop()
    cv2.destroyAllWindows()

if __name__ == '__main__':
    run()

