import sys
import time
 
import cv2
import mss
import numpy as np
import pygetwindow as gw

import subprocess
import platform


class GameWindow():
    def __init__(self, title):
        self.game_title = title
        self.window = self.find_game()
        
    
    def find_game(self):
        windows = gw.getWindowsWithTitle(self.game_title)
    
        if not windows:
            raise RuntimeError(f"{self.game_title} not running")
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
        self.window = windows[0]
        
        return windows[0]

    def activate_game(self):
        self.window.activate()
        time.sleep(0.5)

class ComputerVisionWindow():
    def __init__(self):
        self.calibrated = False
        self.drawing = False
        self.colors_picked = False
        self.display = None
        self.frame = None
        self.tracking_windows = []
        self.calibration_number = 0
        self.hsv = None
        self.color_maps = [None, cv2.COLORMAP_INFERNO, cv2.COLORMAP_JET, cv2.COLORMAP_HOT, cv2.COLORMAP_COOL, cv2.COLORMAP_SPRING, cv2.COLORMAP_SUMMER, cv2.COLORMAP_AUTUMN, cv2.COLORMAP_WINTER]
        self.current_color_map_index = 0
        self.display_modes = ["normal", "backprojection"]
        self.current_display_mode = 0 
    
    def calibrate_window(self, tracking_window):
        self.tracking_windows.append(tracking_window)
        cv2.namedWindow("calibration")
        cv2.setMouseCallback("calibration", self.mouse_callback)
        while not tracking_window.calibrated:
            cv2.imshow("calibration", self.display)
            key = cv2.waitKey(1) & 0xFF
        cv2.destroyWindow("calibration")
        
        cv2.namedWindow("pick colors")
        cv2.setMouseCallback("pick colors", self.pick_colors_callback)
        while not self.colors_picked:
            cv2.imshow("pick colors", self.frame[tracking_window.initial_y:tracking_window.initial_y+tracking_window.initial_h, tracking_window.initial_x:tracking_window.initial_x+tracking_window.initial_w])
            key = cv2.waitKey(1) & 0xFF
        
        cv2.destroyWindow("pick colors")
        self.colors_picked = True
        self.calibrated = True
        tracking_window.track_window = (tracking_window.initial_x, tracking_window.initial_y, tracking_window.initial_w, tracking_window.initial_h)
        tracking_window.camshift_track_window = (tracking_window.initial_x, tracking_window.initial_y, tracking_window.initial_w, tracking_window.initial_h)
        tracking_window.meanshift_track_window = (tracking_window.initial_x, tracking_window.initial_y, tracking_window.initial_w, tracking_window.initial_h)

    def mouse_callback(self, event, x, y, flags, param):
        tracking_window = self.tracking_windows[self.calibration_number]
        
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            tracking_window.start_point = (x, y)
            tracking_window.current_point = (x, y)

        elif event == cv2.EVENT_MOUSEMOVE and self.drawing:
            tracking_window.current_point = (x, y)

            self.display = self.frame.copy()
            cv2.rectangle(
                self.display,
                tracking_window.start_point,
                tracking_window.current_point,
                (0, 255, 0),
                2
            )

        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            tracking_window.current_point = (x, y)

            cv2.rectangle(
                self.display,
                tracking_window.start_point,
                tracking_window.current_point,
                (0, 255, 0),
                2
            )      
            
            tracking_window.calibrated = True
            tracking_window.initial_x = tracking_window.start_point[0]
            tracking_window.initial_y = tracking_window.start_point[1]
            tracking_window.initial_w = abs(tracking_window.current_point[0] - tracking_window.start_point[0])
            tracking_window.initial_h = abs(tracking_window.current_point[1] - tracking_window.start_point[1])

    def pick_colors_callback(self, event, x, y, flags, param):
        tracking_window = self.tracking_windows[self.calibration_number]

        if event == cv2.EVENT_LBUTTONDOWN:
            # Get the pixel color at the clicked position
            pixel_color = self.frame[tracking_window.initial_y + y, tracking_window.initial_x + x]
            hsv_color = self.rgb_to_hsv(pixel_color[::-1])  # Convert BGR to RGB before converting to HSV
            print(f"Clicked color (BGR): {pixel_color}, (HSV): {hsv_color}")

            # Define a range around the clicked color
            lower_bound = np.array([
                max(0, hsv_color[0] - 10),
                50,  # Minimum saturation to avoid very dull colors
                max(0, hsv_color[2] - 10)
                ], dtype=np.uint8
            )
            upper_bound = np.array([
                min(179, hsv_color[0] + 10), 
                min(255, hsv_color[1] + 10), 
                min(255, hsv_color[2] + 10)
                ], dtype=np.uint8
            )

            tracking_window.lower.append(lower_bound)
            tracking_window.upper.append(upper_bound)

            if len(tracking_window.lower) >= int(tracking_window.required_colors):  # Assuming we want to pick the specified number of colors
                self.colors_picked = True
                
    def rgb_to_hsv(self, rgb):
        pixel = np.uint8([[rgb]])
        return cv2.cvtColor(pixel, cv2.COLOR_RGB2HSV)[0, 0]
    
    def draw_tracking_window(self, frame, tracking_window):
        if not tracking_window.hide:
            if tracking_window.current_tracking_method_index == 0:
                x, y, w, h = tracking_window.camshift_track_window
                
                pts = cv2.boxPoints(tracking_window.track_box)
                pts = np.round(pts).astype(np.int32)
                cv2.polylines(
                    frame,
                    [pts],
                    True,
                    (0, 255, 0),  # Green
                    2
                )
            else:
                x, y, w, h = tracking_window.meanshift_track_window
                
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

class TrackingWindow():
    def __init__(self, required_colors):
        self.term_crit = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            10,
            1,
        )
        self.calibrated = False
        self.lower = []
        self.upper = []
        self.initial_x = 0
        self.initial_y = 0
        self.initial_w = 0
        self.initial_h = 0
        self.start_point = (0, 0)
        self.current_point = (0, 0)
        self.track_window = (0, 0, 0, 0)
        self.camshift_track_window = (0, 0, 0, 0)
        self.meanshift_track_window = (0, 0, 0, 0)
        self.track_box = None
        self.required_colors = required_colors
        self.tracking_method = ["CamShift", "MeanShift"]
        self.current_tracking_method_index = 0
        
        self.roi = None
        self.roi_hist = None
        self.roi_mask = None
        self.roi_hsv = None
        self.live_mask = None
        self.sv_floor = None
        self.SV_FLOOR_LOWER = (0, 60, 60)
        self.SV_FLOOR_UPPER = (179, 255, 255)
        self.dest = None
        
        self.selected = False
        self.hide = False

    
    def update_roi(self, frame):
        x, y, w, h = self.track_window
        self.roi = frame[y:y+h, x:x+w]
        self.roi_hsv = cv2.cvtColor(self.roi, cv2.COLOR_BGR2HSV)
        self.live_mask = self.build_mask(self.roi_hsv, self.lower, self.upper, self.required_colors)
        self.sv_floor = cv2.inRange(self.roi_hsv, self.SV_FLOOR_LOWER, self.SV_FLOOR_UPPER)
        self.live_mask = cv2.bitwise_and(self.live_mask, self.sv_floor)
        self.roi_mask = self.live_mask
        self.roi_hist = cv2.calcHist([self.roi_hsv], [0, 1], self.roi_mask, [30, 32], [0, 180, 0, 256])
        cv2.normalize(self.roi_hist, self.roi_hist, 0, 255, cv2.NORM_MINMAX)
            
    def build_mask(self, hsv, lower, upper, required_colors):
        for i in range(required_colors):
            lower_bound = np.array(lower[i], dtype=np.uint8)
            upper_bound = np.array(upper[i], dtype=np.uint8)
            range_mask = cv2.inRange(hsv, lower_bound, upper_bound)
            if i == 0:
                combined_mask = range_mask
            else:
                combined_mask = cv2.bitwise_or(combined_mask, range_mask)
        return combined_mask
    
    def draw_tracking_window(self):
        self.track_box, self.camshift_track_window = cv2.CamShift(self.dest, self.camshift_track_window, self.term_crit)
        _, self.meanshift_track_window = cv2.meanShift(self.dest, self.meanshift_track_window, self.term_crit)

        if self.current_tracking_method_index == 0: 
            
            if not self.hide:
                x, y, w, h = self.camshift_track_window
                center_x = x + w // 2
                center_y = y + h // 2
                cv2.circle(
                    self.dest,
                    (center_x, center_y),
                    4,
                    (255, 0, 0),  # Blue 
                    -1
                )
                
                pts = cv2.boxPoints(self.track_box);
                pts = np.round(pts).astype(np.int32)
                hbp = cv2.polylines(
                        self.dest,
                        [pts],
                        True,
                        255,
                        2
                    )
        else:
            
            if not self.hide:
                x, y, w, h = self.meanshift_track_window
                cv2.rectangle(
                    self.dest,
                    (x, y),
                    (x + w, y + h),
                    (255, 0, 0),  # Green 
                    2
                )
                
                # Draw the center point
                center_x = x + w // 2
                center_y = y + h // 2

                cv2.circle(
                    self.dest,
                    (center_x, center_y),
                    4,
                    (255, 0, 0),  # Blue 
                    -1
                )

class Terminal():
    def __init__(self):
        self.clear_screen()
        self.key = None
        self.tracking_windows = []
    
    def clear_screen(self):
        # Determine the command based on the OS
        command = "cls" if platform.system() == "Windows" else "clear"
        
        # Run the command
        subprocess.run([command], shell=True)


def main():
    
    if len(sys.argv) > 1:
        game_title = sys.argv[1]
        required_colors = int(sys.argv[2])
        
    else:
        raise RuntimeError("Game title not provided. Please provide the game title as a command line argument.")
    
    # Find the game window and activate it
    game = GameWindow(game_title)
    game.find_game()
    game.activate_game()

    computer_vision_window = ComputerVisionWindow()

    t = time.time()
    
    terminal = Terminal()
    
    with mss.MSS() as screenshotter:
        try:
            while True:
                if (time.time() - t) > 1/60:
                    t = time.time()
                    
                    # Get the current game window position and size
                    left = game.window.left 
                    top = game.window.top
                    width = game.window.width
                    height = game.window.height
                    if width <= 0 or height <= 0:
                        raise RuntimeError("Game window is minimized or not visible")
        
                    monitor = {
                        "left": left,
                        "top": top,
                        "width": width,
                        "height": height,
                    }
        
                    # Capture the game window
                    screenshot = screenshotter.grab(monitor)
        
                    # Convert screenshot image to an OpenCV BGR image
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    computer_vision_window.frame = frame

                    if not computer_vision_window.calibrated:
                        
                        tracking_window = TrackingWindow(required_colors)
                        computer_vision_window.display = frame
                        computer_vision_window.calibrate_window(tracking_window)
                        tracking_window.update_roi(frame)

                    computer_vision_window.hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

                    tracking_window.dest = cv2.calcBackProject(
                                            [computer_vision_window.hsv], 
                                            [0, 1], 
                                            tracking_window.roi_hist, 
                                            [0,180, 0, 256], 
                                            1
                                        )

                    
                    # Draw the tracking rectangle
                    tracking_window.draw_tracking_window()
                    computer_vision_window.draw_tracking_window(frame, tracking_window)
                    
                    if computer_vision_window.color_maps[computer_vision_window.current_color_map_index] is not None:
                                            tracking_window.dest = cv2.applyColorMap(tracking_window.dest, computer_vision_window.color_maps[computer_vision_window.current_color_map_index])                                            
                
                    if computer_vision_window.display_modes[computer_vision_window.current_display_mode] == "backprojection":
                        cv2.imshow("projection", tracking_window.dest)
                    else:
                        cv2.imshow("projection", frame)

                    # q or Esc to quit
                    key = cv2.waitKey(1) & 0xFF
        
                    if key == ord("q") or key == 27:
                        break
                    
                    if key == ord("c"):
                        computer_vision_window.current_color_map_index = (computer_vision_window.current_color_map_index + 1) % len(computer_vision_window.color_maps)

                    if key == ord("d"):
                        computer_vision_window.current_display_mode = (computer_vision_window.current_display_mode + 1) % len(computer_vision_window.display_modes)

                    if key == ord("t"):
                        tracking_window.current_tracking_method_index = (tracking_window.current_tracking_method_index + 1) % len(tracking_window.tracking_method)
                        print(f"Switched to tracking method: {tracking_window.tracking_method[tracking_window.current_tracking_method_index]}")
                    
                    if key == ord("h"):
                        tracking_window.hide = not tracking_window.hide
                        if tracking_window.hide:
                            print("Tracking window hidden")
                        else:
                            print("Tracking window shown")
                
    
        finally:
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()