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
        self.drawing = False
        self.display = None
        self.frame = None
        self.tracking_windows = []
        self.tracking_window_index = 0
        self.hsv = None
        self.color_maps = [None, cv2.COLORMAP_INFERNO, cv2.COLORMAP_JET, cv2.COLORMAP_HOT, cv2.COLORMAP_COOL, cv2.COLORMAP_SPRING, cv2.COLORMAP_SUMMER, cv2.COLORMAP_AUTUMN, cv2.COLORMAP_WINTER]
        self.color_map_names = {None: "Grayscale", cv2.COLORMAP_INFERNO: "Inferno", cv2.COLORMAP_JET: "Jet", cv2.COLORMAP_HOT: "Hot", cv2.COLORMAP_COOL: "Cool", cv2.COLORMAP_SPRING: "Spring", cv2.COLORMAP_SUMMER: "Summer", cv2.COLORMAP_AUTUMN: "Autumn", cv2.COLORMAP_WINTER: "Winter"}
        self.current_color_map_index = 0
        self.display_modes = ["normal", "backprojection"]
        self.current_display_mode = 0 
        
    
    def calibrate_window(self, tracking_window):
        original_index = self.tracking_window_index
        self.tracking_window_index = tracking_window.index
        cv2.namedWindow("calibration")
        x, y, width, height = cv2.getWindowImageRect("calibration")

        cv2.setMouseCallback("calibration", self.mouse_callback)
        while not tracking_window.calibrated:
            cv2.imshow("calibration", self.display)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                exit()
            
        cv2.destroyWindow("calibration")
        
        cv2.namedWindow("pick colors")
        cv2.moveWindow("pick colors", tracking_window.initial_x + x, tracking_window.initial_y + y)
        
        cv2.setMouseCallback("pick colors", self.pick_colors_callback)
        while not tracking_window.colors_picked:
            cv2.imshow("pick colors", self.frame[tracking_window.initial_y:tracking_window.initial_y+tracking_window.initial_h, tracking_window.initial_x:tracking_window.initial_x+tracking_window.initial_w])
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                exit()
                
        
        cv2.destroyWindow("pick colors")
        
        self.tracking_window_index = original_index
        tracking_window.colors_picked = True
        tracking_window.calibrated = True
        tracking_window.track_window = (tracking_window.initial_x, tracking_window.initial_y, tracking_window.initial_w, tracking_window.initial_h)
        tracking_window.camshift_track_window = (tracking_window.initial_x, tracking_window.initial_y, tracking_window.initial_w, tracking_window.initial_h)
        tracking_window.meanshift_track_window = (tracking_window.initial_x, tracking_window.initial_y, tracking_window.initial_w, tracking_window.initial_h)

    def mouse_callback(self, event, x, y, flags, param):
        tracking_window = self.tracking_windows[self.tracking_window_index]
        
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
        tracking_window = self.tracking_windows[self.tracking_window_index]

        if event == cv2.EVENT_LBUTTONDOWN:
            # Get the pixel color at the clicked position
            pixel_color = self.frame[tracking_window.initial_y + y, tracking_window.initial_x + x]
            hsv_color = self.rgb_to_hsv(pixel_color[::-1])  # Convert BGR to RGB before converting to HSV
            print(f"Clicked color (BGR): {pixel_color}, (HSV): {hsv_color}")

            # Define a range around the clicked color
            lower_bound = np.array([
                max(0, int(hsv_color[0]) - 10),
                50,  # Minimum saturation to avoid very dull colors
                max(0, int(hsv_color[2]) - 10)
                ], dtype=np.uint8
            )
            upper_bound = np.array([
                min(179, int(hsv_color[0]) + 10), 
                min(255, int(hsv_color[1]) + 10), 
                min(255, int(hsv_color[2]) + 10)
                ], dtype=np.uint8
            )

            tracking_window.lower.append(lower_bound)
            tracking_window.upper.append(upper_bound)


        elif event == cv2.EVENT_LBUTTONUP:
            if len(tracking_window.lower) >= int(tracking_window.required_colors):  # Assuming we want to pick the specified number of colors
                tracking_window.colors_picked = True 
                
    def rgb_to_hsv(self, rgb):
        pixel = np.uint8([[rgb]])
        return cv2.cvtColor(pixel, cv2.COLOR_RGB2HSV)[0, 0]
    
    def draw_tracking_window(self, frame, tracking_window):
        
        if not tracking_window.hide:
            if tracking_window.tracking_method[tracking_window.current_tracking_method_index] == "CamShift":
                x, y, w, h = tracking_window.camshift_track_window
                
                pts = cv2.boxPoints(tracking_window.track_box)
                pts = np.round(pts).astype(np.int32)
                if not tracking_window.selected:
                    cv2.polylines(
                        frame,
                        [pts],
                        True,
                        (0, 0, 255),  # Red
                        2
                    )
                    cv2.putText(
                        frame,
                        tracking_window.label,
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 255),
                        2
                    )
                else:
                    cv2.polylines(
                        frame,
                        [pts],
                        True,
                        (0, 255, 0),  # Green
                        2
                    )
                    # Label the selected tracking window
                    cv2.putText(
                        frame,
                        tracking_window.label,
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2
                    )
            else:
                x, y, w, h = tracking_window.meanshift_track_window
                
                if not tracking_window.selected:
                    cv2.rectangle(
                        frame,
                        (x, y),
                        (x + w, y + h),
                        (0, 0, 255),  # Red 
                        2
                    )
                    cv2.putText(
                        frame,
                        tracking_window.label,
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 0, 255),
                        2
                    )
                else:
                    cv2.rectangle(
                        frame,
                        (x, y),
                        (x + w, y + h),
                        (0, 255, 0),  # Green 
                        2
                    )
                    cv2.putText(
                        frame,
                        tracking_window.label,
                        (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.6,
                        (0, 255, 0),
                        2
                    )
                        
            # Draw the center point
            center_x = x + w // 2
            center_y = y + h // 2

            if not tracking_window.selected:
                cv2.circle(
                    frame,
                    (center_x, center_y),
                    4,
                    (0, 0, 255),  # Red
                    -1
                )
            else:
                cv2.circle(
                    frame,
                    (center_x, center_y),
                    4,
                    (0, 255, 0),  # Green
                    -1
                )

class TrackingWindow():
    def __init__(self, required_colors, index):
        self.term_crit = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            10,
            1,
        )
        self.index = index
        self.calibrated = False
        self.colors_picked = False
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
        self.tracking_method = ["MeanShift", "CamShift"]
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
        self.label = f"Tracking Window {self.index + 1}"

    
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

        if self.tracking_method[self.current_tracking_method_index] == "MeanShift": 
            
            if not self.hide:
                x, y, w, h = self.meanshift_track_window
                cv2.rectangle(
                    self.dest,
                    (x, y),
                    (x + w, y + h),
                    (255, 0, 0),  # Blue 
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
                cv2.putText(
                    self.dest,
                    self.label,
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 0),
                    2
                )  
        else:
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
                        (255, 0, 0),  # Blue
                        2
                    )
                cv2.putText(
                    self.dest,
                    self.label,
                    (x, y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 0),
                    2
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
        
    def process_key(self, key, tracking_window, computer_vision_window):    
        message = None    
        if key == ord("c"):
            computer_vision_window.current_color_map_index = (computer_vision_window.current_color_map_index + 1) % len(computer_vision_window.color_maps)
            message = f"Switched to color map: {computer_vision_window.color_map_names[computer_vision_window.color_maps[computer_vision_window.current_color_map_index]]}"

        elif key == ord("d"):
            computer_vision_window.current_display_mode = (computer_vision_window.current_display_mode + 1) % len(computer_vision_window.display_modes)
            message = f"Switched to display mode: {computer_vision_window.display_modes[computer_vision_window.current_display_mode]}"

        elif key == ord("t"):
            tracking_window.current_tracking_method_index = (tracking_window.current_tracking_method_index + 1) % len(tracking_window.tracking_method)
            message = f"Switched to tracking method: {tracking_window.tracking_method[tracking_window.current_tracking_method_index]}"
        
        elif key == ord("h"):
            tracking_window.hide = not tracking_window.hide
            if tracking_window.hide:
                message = "Tracking window hidden"
            else:
                message = "Tracking window shown"

        elif key == ord("s"):
            tracking_window.selected = not tracking_window.selected

            message = f"Window: {tracking_window.label}. Deselected"
            computer_vision_window.tracking_window_index = (computer_vision_window.tracking_window_index + 1) % len(computer_vision_window.tracking_windows)
            tracking_window = computer_vision_window.tracking_windows[computer_vision_window.tracking_window_index]
            tracking_window.selected = True
        
        elif key == ord("l"):
            original_label = tracking_window.label
            tracking_window.label = input("Enter new label for the selected tracking window: ")
            message = f"Window {original_label} label changed to: {tracking_window.label}"
            
            
        self.update_terminal(tracking_window, computer_vision_window, message=message)
    
    def update_terminal(self, tracking_window, computer_vision_window, message=None):
        self.clear_screen()
        print(f"Current Window: {tracking_window.label} (Index: {tracking_window.index + 1})")
        if message:
            print(f"Message: {message}")
        if tracking_window.calibrated:
            print(f"  Initial Position: ({tracking_window.initial_x}, {tracking_window.initial_y})")
            print(f"  Initial Size: ({tracking_window.initial_w}, {tracking_window.initial_h})")
            print(f"  HSV Lower Bounds: {tracking_window.lower}")
            print(f"  HSV Upper Bounds: {tracking_window.upper}")
            print(f"  Tracking Method: {tracking_window.tracking_method[tracking_window.current_tracking_method_index]}")
            print(f"  Current Color Map: {computer_vision_window.color_map_names[computer_vision_window.color_maps[computer_vision_window.current_color_map_index]]}")
            print(f"  Label: {tracking_window.label}")
            print(f"  Calibrated: {tracking_window.calibrated}")
            print(f"  Colors Picked: {tracking_window.colors_picked}")
            print(f"  Selected: {tracking_window.selected}")
            print(f"  Hide: {tracking_window.hide}\n")
            print("Controls: [c] Change Color Map | [d] Change Display Mode | [t] Change Tracking Method | [h] Hide/Show Window | [s] Select/Deselect Window | [l] Change Label | [q] Quit")
            
        else:
            print("Tracking window not calibrated yet.")


def main():
    
    if len(sys.argv) > 1:
        game_title = sys.argv[1]
        number_of_objects = int(sys.argv[2])
        required_colors = int(sys.argv[3])
        
    else:
        raise RuntimeError("Game title not provided. Please provide the game title as a command line argument.")
    
    # Find the game window and activate it
    game = GameWindow(game_title)
    game.find_game()
    game.activate_game()

    computer_vision_window = ComputerVisionWindow()
    terminal = Terminal()
    
    for index in range(number_of_objects):
        tracking_window = TrackingWindow(required_colors, index)
        computer_vision_window.tracking_windows.append(tracking_window)
        terminal.tracking_windows.append(tracking_window)
        
    tracking_window = computer_vision_window.tracking_windows[0]
    computer_vision_window.tracking_window_index = 0
    tracking_window.selected = True
    
    t = time.time()
    
    initial_print = True
    
    
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
                    computer_vision_window.hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    
                    for window in computer_vision_window.tracking_windows:
                        if not window.calibrated:
                            terminal.update_terminal(window, computer_vision_window)
                            
                            computer_vision_window.display = frame
                            computer_vision_window.calibrate_window(window)
                            window.update_roi(frame)

                    

                        window.dest = cv2.calcBackProject(
                                                [computer_vision_window.hsv], 
                                                [0, 1], 
                                                window.roi_hist, 
                                                [0,180, 0, 256], 
                                                1
                                            )

                        
                        # Draw the tracking rectangle
                        window.draw_tracking_window()
                        computer_vision_window.draw_tracking_window(frame, window)
                    tracking_window = computer_vision_window.tracking_windows[computer_vision_window.tracking_window_index]
                        
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

                    if key != 255 or initial_print:  
                        initial_print = False
                        terminal.process_key(key, tracking_window, computer_vision_window)
    
        finally:
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()