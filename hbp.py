
import os
import random
import time
 
import cv2
import mss
import numpy as np
import pygetwindow as gw
import pydirectinput
from scipy.special import softmax
import pickle


WINDOW_TITLE = "Steep"

def find_steep():
    windows = gw.getWindowsWithTitle(WINDOW_TITLE)
 
    if not windows:
        raise RuntimeError("Steep not running")
    if windows[0].isMinimized:
        windows[0].restore()
        time.sleep(0.5)
        
    try:
        size = open("game_window_size.txt", "r")
        dims = size.readlines()
        windows[0].resizeTo(int(dims[0]), int(dims[1]))
    except:
        size = open("game_window_size.txt", "w")
        size.write(f"{str(windows[0].width)}\n")
        size.write(f"{str(windows[0].height)}\n")
    size.close()
    windows[0].moveTo(0, 0)
    
    return windows[0]
 
 
def rgb_to_hsv(rgb):
    pixel = np.uint8([[rgb]])
    return cv2.cvtColor(pixel, cv2.COLOR_RGB2HSV)[0, 0]
 
 
def build_mask(hsv, lower, upper):
    #(7)

    lower_jacket = np.array(lower[0], dtype=np.uint8)
    upper_jacket = np.array(upper[0], dtype=np.uint8)

    lower_pants = np.array(lower[1], dtype=np.uint8)
    upper_pants = np.array(upper[1], dtype=np.uint8)
    
    lower_bag = np.array(lower[2], dtype=np.uint8)
    upper_bag = np.array(upper[2], dtype=np.uint8)
    

    jacket = cv2.inRange(hsv, lower_jacket, upper_jacket)
    pants = cv2.inRange(hsv, lower_pants, upper_pants)
    bag = cv2.inRange(hsv, lower_bag, upper_bag)
    
    mask = cv2.bitwise_or(pants, jacket)
    mask = cv2.bitwise_or(mask, bag)
    return mask
 
def is_frame_black(frame, threshold):
    mean_val = cv2.mean(frame)  
    return max(mean_val[:3]) < threshold

def mouse_callback(event, x, y, flags, param):
    global drawing, start_point, current_point, display, frame, calibrated, initial_x, initial_y, initial_w, initial_h

    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        start_point = (x, y)
        current_point = (x, y)

    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        current_point = (x, y)

        display = frame.copy()
        cv2.rectangle(
            display,
            start_point,
            current_point,
            (0, 255, 0),
            2
        )

    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        current_point = (x, y)

        cv2.rectangle(
            display,
            start_point,
            current_point,
            (0, 255, 0),
            2
        )
        
        cv2.circle(
            display,
            (start_point[0] + ((current_point[0] - start_point[0]) // 2), start_point[1] + ((current_point[1] - start_point[1]) // 2)),
            4,
            (0, 255, 0),
            -1
        )

        ##("Selected ROI:", start_point, current_point)
        
        
        calibrated = True
        initial_x = start_point[0]
        initial_y = start_point[1]
        initial_w = abs(current_point[0] - start_point[0])
        initial_h = abs(current_point[1] - start_point[1])




def main():
    try:
        rgb_steep_rider = [(81, 48, 60), (81, 48, 60), (81, 48, 60)]
        
        HSVs = []
        for color in rgb_steep_rider:
            HSVs.append(rgb_to_hsv(color))
        
        lower = []
        upper = []
        for hsv_val in HSVs:
            l = np.array([
                max(0, int(hsv_val[0]) - 10),
                max(0, int(hsv_val[1]) - 5),
                max(0, int(hsv_val[2]) - 50)
            ], dtype=np.uint8)
            lower.append(l)
        
            u = np.array([
                min(179, int(hsv_val[0]) + 10),
                min(255, int(hsv_val[1]) + 30),
                min(255, int(hsv_val[2]) + 20)
            ], dtype=np.uint8)
            upper.append(u)
        
        
        # Finds the steep window
        steep = find_steep()
        

        
        steep.activate()
        time.sleep(1)

        # Create the OpenCV display window
   #     cv2.namedWindow("compvis capture", cv2.WINDOW_NORMAL)
        
        # Termination critea for the tracking window
        term_crit = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            10,
            1,
        )
        
        # HSV filter to remove extremely dark/bright pixels
        SV_FLOOR_LOWER = (0, 60, 60)
        SV_FLOOR_UPPER = (179, 255, 255)

        random.seed(0)
        
        global drawing, display, calibrated
        drawing = False

        calibrated = False

        t = time.time()

        loaded = False
        with mss.MSS() as screenshotter:
            try:
            

                while True:
                    if (time.time() - t) > 1/60:
                        t = time.time()
                        global frame, initial_x, initial_h, initial_w, initial_y
                        
                        # Get the current steep window position and size
                        left = steep.left 
                        top = steep.top
                        width = steep.width
                        height = steep.height
            
                        if width <= 0 or height <= 0:
                            time.sleep(0.1)
                            continue
                        
                        
                            
            
                        monitor = {
                            "left": left,
                            "top": top,
                            "width": width,
                            "height": height,
                        }
            
                        # Capture the steep window
                        screenshot = screenshotter.grab(monitor)
            
                        # Convert screenshot image to an OpenCV BGR image
                        frame = np.array(screenshot)
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                      #  hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

            
                        # Convert the full frame to HSV

                        if not calibrated:
                            display = frame

                                

                            cv2.namedWindow("calibration")
                            cv2.setMouseCallback("calibration", mouse_callback)
                            ##("lol")
                            while not calibrated:
                                cv2.imshow("calibration", display)
                                key = cv2.waitKey(1) & 0xFF

                            
                            cv2.destroyWindow("calibration")
                            track_window = (
                                initial_x,
                                initial_y,
                                initial_w,
                                initial_h,
                            )
                            
                            
                            f2 = open("calibration.txt", "w")
                            f2.write(f"{str(initial_x)}\n")
                            f2.write(f"{str(initial_y)}\n")
                            f2.write(f"{str(initial_w)}\n")
                            f2.write(f"{str(initial_h)}\n")

                            time.sleep(1)

                            calibrated = True
                            f2.close

                            x, y, w, h = track_window

                            roi = frame[y:y+h, x:x+w]
                            hsv_roi =  cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)

                            live_mask = build_mask(hsv_roi, lower, upper)
                            sv_floor = cv2.inRange(hsv_roi, SV_FLOOR_LOWER, SV_FLOOR_UPPER)

                            live_mask = cv2.bitwise_and(live_mask, sv_floor)

                            #(5)

                            roi_mask = live_mask
                            
                            roi_hist = cv2.calcHist([hsv_roi], [0], roi_mask, [180], [0, 180])

                            cv2.normalize(roi_hist,roi_hist,0,255,cv2.NORM_MINMAX)


                        # color mask for Madeline's pixels
                        #live_mask = build_mask(hsv, lower, upper)
                        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

                        dst = cv2.calcBackProject([hsv],[0],roi_hist,[0,180],1)

            
                        #sv_floor = cv2.inRange(hsv, SV_FLOOR_LOWER, SV_FLOOR_UPPER)
                        #projection = cv2.bitwise_and(live_mask, sv_floor)
            
                        # Move the tracking window using MeanShift
                        trackBox, track_window = cv2.CamShift(
                            dst,
                            track_window,
                            term_crit
                        )

                        meanshift_trackBox, meanshift_track_window = cv2.meanShift(
                            dst,
                            track_window,
                            term_crit
                        )
                        
                        dst = cv2.applyColorMap(dst, cv2.COLORMAP_INFERNO)

                        
                        
                        x, y, w, h = track_window
                                                
   
                        # Draw the tracking rectangle
                        cv2.rectangle(
                            frame,
                            (x, y),
                            (x + w, y + h),
                            (0, 255, 0),  # Green 
                            2
                        )
            
                        # Draw the center point
                        center_x = x + w // 2
                        center_y = y + h // 2
            
                        cv2.circle(
                            frame,
                            (center_x, center_y),
                            4,
                            (255, 0, 0),  # Blue 
                            -1
                        )
            
                        cv2.rectangle(
                            dst,
                            (x, y),
                            (x + w, y + h),
                            (255, 0, 0),
                            2
                        )
            
                        cv2.circle(
                            dst,
                            (center_x, center_y),
                            4,
                            (255, 0, 0),
                            -1
                        )
                        
                        pts = cv2.boxPoints(trackBox);
                        pts = np.round(pts).astype(np.int32)
                        hbp = cv2.polylines(dst,[pts],True,255,2)
                        
                        
                        cv2.imshow("projection", dst)

                       
                        # q or Esc to quit
                        key = cv2.waitKey(1) & 0xFF
            
                        if key == ord("q") or key == 27:

                            break
                        

                        
                    
        
            finally:
                cv2.destroyAllWindows()
    except:
        
        cv2.destroyAllWindows()
if __name__ == "__main__":
    main()