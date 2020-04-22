# Caman

## Description
Caman creates a fake virtual webcam for applications such as zoom or skype to have fun / show presence.

# Requirements
## [BodyPix](https://blog.tensorflow.org/2019/11/updated-bodypix-2.html)
## [pyfakewebcam](https://github.com/jremmons/pyfakewebcam)

# How to Run
Follow [this tutorial](https://elder.dev/posts/open-source-virtual-background/
) first.

## Linux

### With primusrun
0. Force enabling discrete graphics card with  
`sudo tee /proc/acpi/bbswitch <<< ON`
1. Stop any instance of v4l2loopback  
`sudo modprobe -r v4l2loopback`
2. Start v4l2loopback for fake webcam  
`sudo modprobe v4l2loopback devices=1 video_nr=20 card_label="v4l2loopback" exclusive_caps=1`
3. Start BodyPix node server  
`LD_LIBRARY_PATH=/opt/cuda/lib:$LD_LIBRARY_PATH TF_FORCE_GPU_ALLOW_GROWTH=true node app.js`
4. Start Caman  
`python caman.py`

# Features
- Boomerang  
  Stop webcam and fake presence by playing the last 2 seconds back and forth.
- Virtual Background
- Desktop Share
- Filters
  - Smoothing
  - Hologram effect
  - Invert
- Fun
  - Duplicate camera
