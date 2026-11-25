import sys
import time
 
import cv2
import mss
import numpy as np
import pygetwindow as gw

import subprocess
import platform

import keyboard


class SourceWindow():
    def __init__(self, title, file):
        self.source_title = title
        self.window = self.find_source()
        self.config_file = file
    
    def find_source(self):
        """
        Find the source window by its title.
        
        Resizes the source window to a provided size if available, otherwise resizes to default.
        """
        windows = gw.getWindowsWithTitle(self.source_title)
    
        if not windows:
            raise RuntimeError(f"{self.source_title} not running")
        if windows[0].isMinimized:
            windows[0].restore()
            time.sleep(0.5)
            
        try:
            size = open(self.config_file, "r")
            dims = size.readlines()
            if dims[2] == "y":
                windows[0].resizeTo(int(dims[0]), int(dims[1]))
            size.close()
        except:
            windows[0].resizeTo(800, 600)
            
        windows[0].moveTo(0, 0)
        self.window = windows[0]
        
        return windows[0]

    def activate_source(self):
        """
        Focuses the source window
        """
        self.window.activate()
        time.sleep(0.5)

class ComputerVisionWindow():
    def __init__(self):
        self.drawing = False
        self.display = None
        self.frame = None
        self.tracking_windows = {}
        self.tracking_window_id = 0
        self.hsv = None
        self.color_maps = [None, cv2.COLORMAP_INFERNO, cv2.COLORMAP_JET, cv2.COLORMAP_HOT, cv2.COLORMAP_COOL, cv2.COLORMAP_SPRING, cv2.COLORMAP_SUMMER, cv2.COLORMAP_AUTUMN, cv2.COLORMAP_WINTER]
        self.color_map_names = {None: "Grayscale", cv2.COLORMAP_INFERNO: "Inferno", cv2.COLORMAP_JET: "Jet", cv2.COLORMAP_HOT: "Hot", cv2.COLORMAP_COOL: "Cool", cv2.COLORMAP_SPRING: "Spring", cv2.COLORMAP_SUMMER: "Summer", cv2.COLORMAP_AUTUMN: "Autumn", cv2.COLORMAP_WINTER: "Winter"}
        self.current_color_map_id = 0
        self.display_modes = ["normal", "backprojection"]
        self.current_display_mode = 0 
        self.color_change = None
        
    
    def calibrate_window(self, tracking_window, color_change=None):

        original_id = self.tracking_window_id
        self.tracking_window_id = tracking_window.id
        self.color_change = color_change
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
        if color_change:
            cv2.moveWindow("pick colors", x, y)
        else:
            cv2.moveWindow("pick colors", tracking_window.initial_x + x, tracking_window.initial_y + y)
        
        cv2.setMouseCallback("pick colors", self.pick_colors_callback)
        while not tracking_window.colors_picked:
            if color_change:
                cv2.imshow("pick colors", self.frame)
            else:
                cv2.imshow("pick colors", self.frame[tracking_window.initial_y:tracking_window.initial_y+tracking_window.initial_h, tracking_window.initial_x:tracking_window.initial_x+tracking_window.initial_w])
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                exit()
                
        
        cv2.destroyWindow("pick colors")
        
        self.tracking_window_id = original_id
        tracking_window.colors_picked = True
        tracking_window.calibrated = True
        tracking_window.track_window = (tracking_window.initial_x, tracking_window.initial_y, tracking_window.initial_w, tracking_window.initial_h)
        tracking_window.camshift_track_window = (tracking_window.initial_x, tracking_window.initial_y, tracking_window.initial_w, tracking_window.initial_h)
        tracking_window.meanshift_track_window = (tracking_window.initial_x, tracking_window.initial_y, tracking_window.initial_w, tracking_window.initial_h)

    def mouse_callback(self, event, x, y, flags, param):
        tracking_window = self.tracking_windows[self.tracking_window_id]
        
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
            
            if tracking_window.start_point[0] < tracking_window.current_point[0]:
                tracking_window.initial_x = tracking_window.start_point[0]
            else:
                tracking_window.initial_x = tracking_window.current_point[0]
            
            if tracking_window.start_point[1] < tracking_window.current_point[1]:
                tracking_window.initial_y = tracking_window.start_point[1]
            else:
                tracking_window.initial_y = tracking_window.current_point[1]
                
            if tracking_window.initial_x < 0:
                tracking_window.initial_x = 0
            elif tracking_window.initial_x >= self.frame.shape[1]:
                tracking_window.initial_x = self.frame.shape[1] - 1                
            if tracking_window.initial_y < 0:
                tracking_window.initial_y = 0
            elif tracking_window.initial_y >= self.frame.shape[0]:
                tracking_window.initial_y = self.frame.shape[0] - 1

            tracking_window.initial_w = abs(tracking_window.current_point[0] - tracking_window.start_point[0])
            tracking_window.initial_h = abs(tracking_window.current_point[1] - tracking_window.start_point[1])
            

    def pick_colors_callback(self, event, x, y, flags, param):
        tracking_window = self.tracking_windows[self.tracking_window_id]

        if event == cv2.EVENT_LBUTTONDOWN:
            # Get the pixel color at the clicked position
            if self.color_change:
                pixel_color = self.frame[y, x]
            else:
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
                self.color_change = None
                
    def rgb_to_hsv(self, rgb):
        pixel = np.uint8([[rgb]])
        return cv2.cvtColor(pixel, cv2.COLOR_RGB2HSV)[0, 0]
    
    def draw_tracking_window(self, frame, tracking_window):
        
        if not tracking_window.hide:
            if tracking_window.tracking_method[tracking_window.current_tracking_method_id] == "CamShift":
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
    def __init__(self, required_colors, id):
        self.term_crit = (
            cv2.TERM_CRITERIA_EPS | cv2.TERM_CRITERIA_COUNT,
            10,
            1,
        )
        self.id = id
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
        self.x = 0
        self.y = 0
        self.w = 0
        self.h = 0
        self.center_x = 0
        self.center_y = 0
        self.track_box = None
        self.required_colors = required_colors
        self.tracking_method = ["MeanShift", "CamShift"]
        self.current_tracking_method_id = 0
        
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
        self.label = f"Tracking Window {self.id}"
        
        self.next = None
        self.prev = None

    
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

        if self.tracking_method[self.current_tracking_method_id] == "MeanShift": 
            
            if not self.hide:
                self.x, self.y, self.w, self.h = self.meanshift_track_window
                cv2.rectangle(
                    self.dest,
                    (self.x, self.y),
                    (self.x + self.w, self.y + self.h),
                    (255, 0, 0),  # Blue 
                    2
                )
                
                # Draw the center point
                self.center_x = self.x + self.w // 2
                self.center_y = self.y + self.h // 2

                cv2.circle(
                    self.dest,
                    (self.center_x, self.center_y),
                    4,
                    (255, 0, 0),  # Blue
                    -1
                )         
                cv2.putText(
                    self.dest,
                    self.label,
                    (self.x, self.y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 0),
                    2
                )  
        else:
            if not self.hide:
                self.x, self.y, self.w, self.h = self.camshift_track_window
                self.center_x = self.x + self.w // 2
                self.center_y = self.y + self.h // 2
                cv2.circle(
                    self.dest,
                    (self.center_x, self.center_y),
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
                    (self.x, self.y - 10),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (255, 0, 0),
                    2
                )  

class Terminal():
    def __init__(self):
        self.clear_screen()
        self.key = None
        self.tracking_windows = {}
        self.control_layer = 0
        self.next_available_id = 0
        self.frame = None
        self.head = None
        self.end = None   
        self.source_window = None     
        self.verbose = False
    
    def clear_screen(self):
        # Determine the command based on the OS
        command = "cls" if platform.system() == "Windows" else "clear"
        
        # Run the command
        subprocess.run([command], shell=True)
        
    def process_key(self, key, tracking_window, computer_vision_window):    
        message = None    
        if key == ord("c") or key == ord("C"):
            computer_vision_window.current_color_map_id = (computer_vision_window.current_color_map_id + 1) % len(computer_vision_window.color_maps)
            message = f"Switched to color map: {computer_vision_window.color_map_names[computer_vision_window.color_maps[computer_vision_window.current_color_map_id]]}"

        elif key == ord("d") or key == ord("D"):
            computer_vision_window.current_display_mode = (computer_vision_window.current_display_mode + 1) % len(computer_vision_window.display_modes)
            message = f"Switched to display mode: {computer_vision_window.display_modes[computer_vision_window.current_display_mode]}"

        elif key == ord("t") or key == ord("T"):
            tracking_window.current_tracking_method_id = (tracking_window.current_tracking_method_id + 1) % len(tracking_window.tracking_method)
            message = f"Switched to tracking method: {tracking_window.tracking_method[tracking_window.current_tracking_method_id]}"
        
        elif key == ord("h") or key == ord("H"):
            tracking_window.hide = not tracking_window.hide
            if tracking_window.hide:
                message = "Tracking window hidden"
            else:
                message = "Tracking window shown"

        elif keyboard.is_pressed("left"):
            if len(computer_vision_window.tracking_windows) > 1:
                tracking_window.selected = False
                
                if tracking_window.prev:
                    tracking_window.prev.selected = True
                    tracking_window = tracking_window.prev
                    message = f"Selected window: {tracking_window.label}"
                else:
                    self.end.selected = True
                    tracking_window = self.end
                    message = f"Selected window: {tracking_window.label}"
                    
                computer_vision_window.tracking_window_id = tracking_window.id
        
        elif keyboard.is_pressed("right"):
            if len(computer_vision_window.tracking_windows) > 1:
                tracking_window.selected = False
                
                if tracking_window.next:
                    tracking_window.next.selected = True
                    tracking_window = tracking_window.next
                    message = f"Selected window: {tracking_window.label}"
                else:
                    self.head.selected = True
                    tracking_window = self.head
                    message = f"Selected window: {tracking_window.label}"
                computer_vision_window.tracking_window_id = tracking_window.id

        
        elif key == ord("n") or key == ord("N"):
            self.clear_screen()
            print("Adding a new tracking window...")
            input_required_colors = input("Enter the number of colors to track for the new window: ")
            try:
                required_colors = int(input_required_colors)
                new_tracking_window = TrackingWindow(required_colors, self.next_available_id)
                computer_vision_window.tracking_windows[self.next_available_id] = new_tracking_window
                self.tracking_windows[self.next_available_id] = new_tracking_window
                self.update_terminal(new_tracking_window, computer_vision_window)
                
                computer_vision_window.display = self.frame
                computer_vision_window.calibrate_window(new_tracking_window)
                new_tracking_window.update_roi(self.frame)
                self.next_available_id += 1
                
                if self.end:
                    new_tracking_window.prev = self.end
                    self.end.next = new_tracking_window
                self.end = new_tracking_window
                message = f"Added new tracking window: {new_tracking_window.label} with {required_colors}-color mask."
                
                
            except ValueError:
                message = "Invalid input. Please enter a valid integer."
        
        elif key == ord("x") or key == ord("X"):
            if len(computer_vision_window.tracking_windows) > 1:

                removed_window = computer_vision_window.tracking_windows[computer_vision_window.tracking_window_id]
                if removed_window.prev:
                    if removed_window.next:
                        removed_window.prev.next = removed_window.next
                        removed_window.next.prev = removed_window.prev
                    else:
                        removed_window.prev.next = None
                        self.end = removed_window.prev
                    removed_window.prev.selected = True
                    computer_vision_window.tracking_window_id = removed_window.prev.id
                    tracking_window = removed_window.prev
                    
                elif removed_window.next:
                    removed_window.next.prev = None
                    removed_window.next.selected = True
                    computer_vision_window.tracking_window_id = removed_window.next.id
                    tracking_window = removed_window.next
                                                        
                computer_vision_window.tracking_windows.pop(removed_window.id, None)
                self.tracking_windows.pop(removed_window.id, None)
                message = f"Removed tracking window: {removed_window.label}"
                
                
            elif len(computer_vision_window.tracking_windows) == 1:
                message = "Cannot remove the last tracking window. At least one tracking window must remain."


        elif key == ord("l") or key == ord("L"):
            original_label = tracking_window.label
            new_label = input("Enter new label for the selected tracking window: ")
            if new_label == "":
                message = "Label cannot be blank."
            else:
                message = f"Window {original_label} label changed to: {tracking_window.label}"
        
        elif key == ord("r") or key == ord("R"):
            print(f"Resetting tracking window: {tracking_window.label}")
            tracking_window.calibrated = False
            tracking_window.colors_picked = False
            tracking_window.lower = []
            tracking_window.upper = []
            self.update_terminal(tracking_window, computer_vision_window)
            computer_vision_window.display = self.frame
            computer_vision_window.calibrate_window(tracking_window)
            tracking_window.update_roi(self.frame)
            
            message = f"Reset calibration for window: {tracking_window.label}"
        
        elif key == ord("s") or key == ord("S"):
            try:
                self.source_window.source_title = input("Enter new title for the source window: ")
                self.source_window.window = self.source_window.find_source()
                message = f"Source window title changed to: {self.source_window.source_title}"
            except:
                message = "Error occurred while changing source window title."

        elif key == ord("e") or key == ord("E"):
            print("If no name is provided, no file will be exported.")
            file_name = input("Enter the name of the .txt file to export source window size [omit .txt]: ")
            
            reuse = input(f"Reuse the current source dimensions ({self.source_window.window.width} width, {self.source_window.window.height} height) during your next session? [Y] or [N]. ")
            
            if file_name == "" or reuse == "":
                message = "No file specified, or reuse not specified."
            else:
                try:
                    size = open(file_name + ".txt", "w")
                    size.write(f"{str(self.source_window.window.width)}\n")
                    size.write(f"{str(self.source_window.window.height)}\n")
                    if reuse.lower() == 'y':
                        size.write(f"{reuse.lower()}\n")
                    size.close()
                    message = f"Source window size exported to: {file_name}"
                except:
                    message = "Error occurred while exporting."
        
        elif key == ord("m") or key == ord("M"):
            print(f"Resetting the mask for tracking window: {tracking_window.label}")
            print(f"The old mask consisted of {tracking_window.required_colors} colors.")
            colors = input("How many colors will you pick for the new mask? ")
            try:
                int(colors)
                tracking_window.colors_picked = False
                tracking_window.required_colors = int(colors)
                tracking_window.lower = []
                tracking_window.upper = []
                computer_vision_window.calibrate_window(tracking_window, color_change=True)
                message = f"Created {tracking_window.label}'s new mask "
            except:
                message = "Invalid input for # of colors."

        
        elif key == ord("v") or key == ord("V"):
            self.verbose = not self.verbose

        self.update_terminal(tracking_window, computer_vision_window, message=message)
    
    def update_terminal(self, tracking_window, computer_vision_window, message=None):
        self.clear_screen()
        print(f"Current Source Window:        {self.source_window.window.title}")
        print(f"Current Tracking Window:      {tracking_window.label} (ID: {tracking_window.id})")
        print(f"Head of Tracking Window List: {self.head.label if self.head else 'None'} (ID: {self.head.id if self.head else 'None'})")
        print(f"End of Tracking Window List:  {self.end.label if self.end else 'None'} (ID: {self.end.id if self.end else 'None'})")

        if message:
            print(f"Message: {message}")
        if tracking_window.calibrated:
            if self.verbose:
                print(f'''
    Window Label:     {tracking_window.label}
    Tracking Method:  {tracking_window.tracking_method[tracking_window.current_tracking_method_id]}

    Current Color Map:     {computer_vision_window.color_map_names[computer_vision_window.color_maps[computer_vision_window.current_color_map_id]]}
    Mask HSV Lower Bounds: {tracking_window.lower}
    Mask HSV Upper Bounds: {tracking_window.upper}
   
    Hidden:        {tracking_window.hide}
    Selected:      {tracking_window.selected}
    Calibrated:    {tracking_window.calibrated}
    Colors Picked: {tracking_window.colors_picked}
    
    Source Window Dimensions: {self.source_window.window.width} width, {self.source_window.window.height} height

  
Next Tracking Window:     {tracking_window.next.label if tracking_window.next else 'None'} (ID: {tracking_window.next.id if tracking_window.next else 'None'})
Previous Tracking Window: {tracking_window.prev.label if tracking_window.prev else 'None'} (ID: {tracking_window.prev.id if tracking_window.prev else 'None'})
Total # Tracking Windows: {len(computer_vision_window.tracking_windows)}
  ''')
            
        else:
            print("Tracking window not calibrated yet.")

        print('''
Controls: 
[C] Change Color Map | [D] Change Display Mode | [M] Change Current Mask
[N] Add New Window | [X] Remove Current Window | [H] Hide/Show Window
[T] Change Tracking Method | [L] Change Label | [R] Reset Calibration
[S] Change Source | [E] Export Source Window Size | [V] View/Hide Current Window Details
[Left Arrow] Select Previous Window | [Right Arrow] Select Next Window
[Q] Quit
            ''')

def main():

    if len(sys.argv) == 4:
        try:
            source_title = sys.argv[1]
            number_of_objects = int(sys.argv[2])
            required_colors = int(sys.argv[3])
            
            if len(sys.argv) == 5:
                config_file = sys.argv[4]
            else:
                config_file = None
        except:
            print("\nERROR\n")
            print("Intended use: python .\\main.py [source window title] [# tracking windows] [# mask colors] [optional config file]\n")    
            exit()        
        
    else:
        raise RuntimeError("Source title not provided. Please provide the source title as a command line argument.")
    
    # Find the source window and activate it
    source = SourceWindow(source_title, config_file)
    source.find_source()
    source.activate_source()

    computer_vision_window = ComputerVisionWindow()
    terminal = Terminal()
    terminal.source_window = source
    
    previous_window = None
    
    for id in range(number_of_objects):
        tracking_window = TrackingWindow(required_colors, id)
        computer_vision_window.tracking_windows[id] = tracking_window
        terminal.tracking_windows[id] = tracking_window
        if previous_window:
            previous_window.next = tracking_window
            tracking_window.prev = previous_window
        previous_window = tracking_window
    
    terminal.head = computer_vision_window.tracking_windows[0]
    terminal.end = computer_vision_window.tracking_windows[id]
    tracking_window = computer_vision_window.tracking_windows[0]
    computer_vision_window.tracking_window_id = 0
    tracking_window.selected = True
    terminal.next_available_id = number_of_objects
    
    t = time.time()
    
    initial_print = True
    
    
    with mss.MSS() as screenshotter:
        try:
            while True:
                if (time.time() - t) > 1/60:
                    t = time.time()
                    
                    # Get the current source window position and size
                    left = source.window.left 
                    top = source.window.top
                    width = source.window.width
                    height = source.window.height
                    if width <= 0 or height <= 0:
                        raise RuntimeError("Source window is minimized or not visible")
        
                    monitor = {
                        "left": left,
                        "top": top,
                        "width": width,
                        "height": height,
                    }
        
                    # Capture the source window
                    screenshot = screenshotter.grab(monitor)
        
                    # Convert screenshot image to an OpenCV BGR image
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                    computer_vision_window.frame = frame
                    terminal.frame = frame
                    computer_vision_window.hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                    
                    for window in computer_vision_window.tracking_windows.values():
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
                    tracking_window = computer_vision_window.tracking_windows[computer_vision_window.tracking_window_id]
                        
                    if computer_vision_window.color_maps[computer_vision_window.current_color_map_id] is not None:
                                            tracking_window.dest = cv2.applyColorMap(tracking_window.dest, computer_vision_window.color_maps[computer_vision_window.current_color_map_id])                                            
                
                    if computer_vision_window.display_modes[computer_vision_window.current_display_mode] == "backprojection":
                        cv2.imshow("projection", tracking_window.dest)
                    else:
                        cv2.imshow("projection", frame)

                    # q or Esc to quit
                    key = cv2.waitKey(1) & 0xFF
                    
                    if key == ord("q") or key == 27 or keyboard.is_pressed("q") or keyboard.is_pressed("Q"):
                        break

                    if key != 255 or initial_print:  
                        initial_print = False
                        terminal.process_key(key, tracking_window, computer_vision_window)
    
        finally:
            cv2.destroyAllWindows()

if __name__ == "__main__":
    main()