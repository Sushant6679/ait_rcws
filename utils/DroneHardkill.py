##11111
from PyQt5.QtCore import QThread, pyqtSignal
import socket
import struct
from api.sdk.datdefs import *
from api.camera_communication import CameraCommunication
from collections import deque
import threading
import time
import numpy as np
from pydash import throttle
import math
from numba import njit, prange

class Cue:
    def __init__(self, sensor, target_id, az, el, range_val, fire):
        self.sensor = sensor
        self.target_id = target_id
        self.az = az
        self.el = el
        self.range = range_val
        self.fire = fire

# def format_angles(azimuth, elevation):
#     print("*"*50)
#     print(f"[INFO] GOT NEW AZ, EL: {azimuth, elevation}")
#     if azimuth > 180:
#         azimuth -= 360
#     if azimuth < -180:
#         azimuth += 180
#     if elevation > 45:
#         elevation = 40
#     if elevation < -5:
#         elevation = -5
    
#     return azimuth, elevation

def format_angles(raw_az, raw_el):
    """
    Convert azimuth (0–360) and elevation (0–360) into:
      - Azimuth: -180 to 180
      - Elevation: -5 to 45 (clamped)
    """
    # --- Normalize azimuth ---
    az = ((raw_az + 180) % 360) - 180  # maps 0–360 to -180–180

    # --- Normalize elevation ---
    el = raw_el % 360  # keep it within 0–360 first

    # You can decide how to interpret elevation > 180
    # For now, assume 0–180 maps directly, others wrap around
    if el > 180:
        el -= 360  # make it negative if beyond 180 (e.g., 350 -> -10)

    # Clamp elevation to allowed physical range
    el = max(-5, min(45, el))

    return az, el


@njit
def simulate_projectile_for_target_no_self(initial_velocity, angle_degrees, height, target_x, target_y, dt=0.0001, g=9.81, k=0.000898):
    angle = np.radians(angle_degrees)
    v0x = initial_velocity * np.cos(angle)
    v0y = initial_velocity * np.sin(angle)

    x, y = 0, height
    vx, vy = v0x, v0y
    x_threshold = 0.2
    bullet_closer = False
    Ys = []

    while y >= 0 and x <= target_x:
        v = np.sqrt(vx**2 + vy**2)
        ax = -k * v * vx
        ay = -g - k * v * vy

        vx += ax * dt
        vy += ay * dt

        x += vx * dt
        y += vy * dt

        if abs(x - target_x) < x_threshold:
            if bullet_closer:
                Ys.append(y)
            else:
                bullet_closer = True
                x_threshold = 0.01
                dt = 0.00000001

    if Ys:
        return sum(Ys)/len(Ys)
    else:
        return -1

def calculate_angle(x, y):
    slope = (y - 1.5 - 0.15) / x
    return math.degrees(math.atan(slope))

def simulate_all_angles(initial_velocity, height, target_x, target_y, angles):
    results = np.empty(len(angles))
    for i in prange(len(angles)):
        results[i] = simulate_projectile_for_target_no_self(
            initial_velocity,
            angles[i],
            height,
            target_x,
            target_y
        )
    return results

def get_closest_positive_key_by_value(dictionary, target_value):
    valid_items = {k: v for k, v in dictionary.items() if v >= target_value}
    if not valid_items:
        return None
    return min(valid_items, key=lambda k: valid_items[k] - target_value)

def find_launch_angle(azimuth, elevation, range):
    range_table = {
        500: 0.28, 550:0.32, 600:0.37, 650:0.42, 700:0.478, 750:0.53,
        800:0.596, 850:0.66, 900:0.736, 950:0.815, 1000:0.9, 1050:0.99,
        1100:1.08, 1150:1.18, 1200:1.28, 1250:1.389, 1300:1.5, 1350:1.61, 1400:1.73
    }
    results = []
    Results = []
    target_x = range * math.cos(math.radians(elevation))
    target_y = range * math.sin(math.radians(elevation))
    height = 0
    initial_velocity = 840
    angle_min = round(calculate_angle(target_x, target_y), 2)
    
    if angle_min is None:
        return None

    if target_y < 5:
        increment = 1
    elif target_y < 10:
        increment = 1
    elif target_y < 15:
        increment = 1.5
    elif target_y < 20:
        increment = 2
    elif target_y < 30:
        increment = 2
    else:
        increment = 2.5

    angle_max = angle_min + increment
    tolerance = 0.01
    input_range = np.arange(angle_min, angle_max, tolerance)

    results = simulate_all_angles(initial_velocity, height, target_x, target_y, input_range)
    for angle, y_result in zip(input_range, results):
        if y_result != -1.0:
            Results.append((angle, y_result))
        else:
            Results.append(None)
            
    results = [r for r in Results if r is not None]
    if not results:
        closest_key = min(range_table.keys(), key=lambda k: abs(k - target_x))
        corr_el = range_table[closest_key]
        return corr_el
    results_dict = dict(results)
    corr_el = get_closest_positive_key_by_value(results_dict, target_y)
    return corr_el


class HardkillDrone(QThread):
    """Enhanced drone hardkill thread with robust connection management"""
    connection_lost = pyqtSignal(str)
    connected = pyqtSignal()
    status_update = pyqtSignal(str)
    reconnecting = pyqtSignal(str)

    def __init__(self, video_player, camera, server_ip="192.168.1.64", server_port=9010, parent=None):
        super().__init__(parent)
        self.server_ip = server_ip
        self.server_port = server_port
        self.video_player = video_player
        self.camera = camera
        
        # Packet sizes
        self.received_packet_size = 18  # Incoming radar data
        self.send_packet_size = 14  # Outgoing ACK
        
        # Threading control
        self.running = True
        self.stop_requested = False
        self.currently_connected = False
        
        # Connection settings
        self.max_reconnect_attempts = 0  # 0 means infinite
        self.reconnect_delay = 5.0  # seconds
        self.connection_timeout = 10.0
        
        # Data management
        self.data_lock = threading.Lock()
        self.current_cue = None
        self.previous_cue = Cue(0, 0, 0, 0, 0, 0)
        self.new_cue_available = False
        
        # Tracking state
        self.firing = False
        self._range = -1
        self.current_sensor = None
        self.current_target_id = -1
        self.track_status = False
        self.curr_state = "WAIT"
        
        # Timing
        self.last_send_time = 0
        self.send_interval = 1.0  # Send ACK every 1 second
        
        # State machine variables
        self.detection_times = 0
        self.track_fail_count = 0
        self.go_to_cue_start_time = None
        self.gun_prev_az = None
        self.gun_prev_el = None
        
        # Velocity tracking
        self.drone_velX = 0
        self.drone_velY = 0
        self.previous_gun_azimuth = None
        self.previous_gun_elevation = None
        self.last_time = None
        self.update_pid = False

    def receive_exact(self, sock, size):
        """Receive exactly 'size' bytes from the socket"""
        data = b''
        while len(data) < size:
            chunk = sock.recv(size - len(data))
            if not chunk:
                raise ConnectionError("Connection closed by server.")
            data += chunk
        return data

    def update_cue(self, new_cue):
        """Thread-safe cue update"""
        with self.data_lock:
            if (abs(new_cue.az - self.previous_cue.az) != 0 or 
                abs(new_cue.el - self.previous_cue.el) != 0 or 
                abs(new_cue.fire - self.previous_cue.fire) != 0 or
                abs(new_cue.range - self.previous_cue.range) != 0 or
                new_cue.sensor != self.previous_cue.sensor or
                new_cue.target_id != self.previous_cue.target_id):
                
                self.current_cue = new_cue
                self.new_cue_available = True
                self.current_sensor = new_cue.sensor
                self.current_target_id = new_cue.target_id
                self._range = new_cue.range
                self.previous_cue = new_cue
                
                sensor_type = "EO/IR" if new_cue.sensor == 0 else "RADAR"
                fire_status = "ENABLE" if new_cue.fire == 1 else "DISABLE"
                print(f"[INFO] New cue - Sensor: {sensor_type}, Target ID: {new_cue.target_id}, "
                      f"Az: {new_cue.az:.2f}°, El: {new_cue.el:.2f}°, Range: {new_cue.range}m, Fire: {fire_status}")

    def get_current_cue(self):
        """Thread-safe cue retrieval"""
        with self.data_lock:
            cue = self.current_cue
            new_available = self.new_cue_available
            self.new_cue_available = False
            return cue, new_available

    def create_ack_packet(self):
        """
        Create ACK packet with format: HhffBB
        H = header (uint16) - 0xA556
        h = target_id (int16)
        f = gun_azimuth (float)
        f = gun_elevation (float)
        B = firing status (uint8)
        B = track_status (uint8)
        """
        header = 0xA556
        target_id = self.current_target_id
        gun_azimuth = self.video_player._gun_azimuth
        gun_elevation = self.video_player._gun_elevation
        fire_status = int(self.firing)
        track_status = int(self.track_status)
        
        packet = struct.pack('<HhffBB', header, target_id, gun_azimuth, 
                           gun_elevation, fire_status, track_status)
        return packet

    def send_ack(self, sock):
        """Send ACK packet to server"""
        try:
            packet = self.create_ack_packet()
            sock.send(packet)
            
            print(f"[SEND] ACK - Target ID: {self.current_target_id}, "
                  f"Az: {self.video_player._gun_azimuth:.2f}, "
                  f"El: {self.video_player._gun_elevation:.2f}, "
                  f"Fire: {int(self.firing)}, Track: {int(self.track_status)}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to send ACK: {e}")
            return False

    def should_send_ack(self):
        """Check if it's time to send ACK (every 1 second)"""
        current_time = time.time()
        if current_time - self.last_send_time >= self.send_interval:
            self.last_send_time = current_time
            return True
        return False

    def process_state_machine(self):
        """Run the drone tracking state machine"""
        current_cue, new_cue_found = self.get_current_cue()
        
        # Print current state
        print(f"[INFO] Current state: {self.curr_state}")
        if self.current_sensor is not None and self.current_target_id is not None:
            sensor_name = "EO/IR" if self.current_sensor == 0 else "RADAR"
            # Uncomment for verbose logging:
            print(f"[INFO] State: {self.curr_state}, Sensor: {sensor_name}, Target ID: {self.current_target_id}")
        
        # State machine logic
        if self.curr_state == "WAIT":
            # Reset range and target_id when waiting
            self._range = -1
            self.current_target_id = -1
            
            if new_cue_found and current_cue:
                self.go_to_cue_start_time = time.time()
                self.gun_prev_az = self.video_player._gun_azimuth
                self.gun_prev_el = self.video_player._gun_elevation
                self.curr_state = "GO_TO_CUE"

        elif self.curr_state == "GO_TO_CUE":
            if new_cue_found and current_cue:
                self.video_player.position_gun(current_cue.az, current_cue.el)
                print(current_cue.az, current_cue.el)
            if current_cue and abs(self.video_player._gun_azimuth - current_cue.az) < 0.03 and \
               abs(self.video_player._gun_elevation - current_cue.el) < 0.03:
                self.curr_state = "CHECK_DETECTION"
        
        elif self.curr_state == "CHECK_DETECTION":
            max_box = None
            try:
                target_data = self.video_player.detectionQueue.pop()
                x = target_data.left
                y = target_data.top
                max_box = Rect(x, y, x+40, y+40)
            except:
                pass

            if max_box:
                self.video_player.start_track(tracking_mode=0)
                self.detection_times = 0
                self.curr_state = "CHECK_TRACK_STATUS"
            else:
                self.detection_times += 1
                if self.detection_times >= 5:
                    self.video_player.stop_track()
                    self.curr_state = "WAIT"
                    self.detection_times = 0
        
        elif self.curr_state == "CHECK_TRACK_STATUS":
            self.track_status = self.camera.get_track_status(VideoType_e.VT_IRD)
            
            if self.track_status:
                self.track_fail_count = 0
                self.update_pid = True
                
                # Handle fire command
                if current_cue:
                    if current_cue.fire and not self.firing:
                        self.video_player.trig(0)
                        self.firing = True
                    elif not current_cue.fire and self.firing:
                        self.video_player.trigoff()
                        self.firing = False
                
                # Check if new cue is significantly different
                if new_cue_found and current_cue:
                    if abs(self.video_player._gun_azimuth - current_cue.az) > 3 or \
                       abs(self.video_player._gun_elevation - current_cue.el) > 3:
                        self.video_player.stop_track()
                        self.curr_state = "WAIT"
            else:
                self.track_fail_count += 1
                if self.track_fail_count > 40:
                    self.video_player.stop_track()
                    self.track_fail_count = 0
                    self.curr_state = "WAIT"
                else:
                    self.curr_state = "CHECK_DETECTION"

    def attempt_connection(self):
        """Attempt to establish connection to the server"""
        try:
            print(f"[INFO] Attempting connection to {self.server_ip}:{self.server_port}")
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.connection_timeout)
            sock.connect((self.server_ip, self.server_port))
            sock.settimeout(0.1)  # Non-blocking with short timeout
            
            print(f"[SUCCESS] Connected to {self.server_ip}:{self.server_port}")
            self.currently_connected = True
            self.connected.emit()
            return sock
            
        except Exception as e:
            print(f"[ERROR] Connection attempt failed: {e}")
            if 'sock' in locals():
                try:
                    sock.close()
                except:
                    pass
            return None

    def connection_loop(self, sock):
        """Main communication loop for an established connection"""
        self.last_send_time = time.time()
        
        # Initialize state machine
        self.video_player.stop_track()
        self.curr_state = "WAIT"
        
        while self.running and not self.isInterruptionRequested() and not self.stop_requested:
            try:
                # Try to receive data
                try:
                    data = self.receive_exact(sock, self.received_packet_size)
                    print(data)
                    # Unpack received data
                    header, sensor, target_id, azimuth, elevation, range_val, fire_cmd = \
                        struct.unpack('<HBhfffB', data)
                    
                    # Validate header
                    if header != 0xA5A5:
                        print(f"[WARNING] Invalid header: 0x{header:04X}")
                        continue
                    
                    # Validate sensor and fire command
                    if sensor not in [0, 1]:
                        print(f"[WARNING] Invalid sensor: {sensor}")
                        continue
                    
                    if fire_cmd not in [0, 1]:
                        print(f"[WARNING] Invalid fire command: {fire_cmd}")
                        continue
                    
                    # Format angles
                    azimuth, elevation = format_angles(azimuth, elevation)
                    print(azimuth, elevation)
                    # Create and update cue
                    new_cue = Cue(sensor, target_id, azimuth, elevation, range_val, fire_cmd)
                    self.update_cue(new_cue)
                    print(new_cue)
                except socket.timeout:
                    # Timeout is expected - allows checking other conditions
                    pass
                except ConnectionError as ce:
                    print(f"[ERROR] Connection lost during receive: {ce}")
                    raise ce
                except struct.error as se:
                    print(f"[ERROR] Struct unpacking error: {se}")
                    continue
                
                # Process state machine
                self.process_state_machine()
                
                # Send ACK periodically
                if self.should_send_ack():
                    try:
                        self.send_ack(sock)
                    except Exception as send_error:
                        print(f"[ERROR] Failed to send ACK: {send_error}")
                        raise ConnectionError("Failed to send ACK")
                
                # Small sleep to prevent CPU overuse
                time.sleep(0.01)
                
            except Exception as e:
                print(f"[ERROR] Communication error: {e}")
                raise e

    def run(self):
        """Main thread with automatic reconnection logic"""
        reconnect_attempt = 0
        
        while self.running and not self.isInterruptionRequested() and not self.stop_requested:
            sock = None
            try:
                # Attempt connection
                if not self.currently_connected:
                    if reconnect_attempt > 0:
                        self.reconnecting.emit(f"Reconnection attempt #{reconnect_attempt}")
                        print(f"[INFO] Reconnection attempt #{reconnect_attempt}")
                    
                    sock = self.attempt_connection()
                    
                    if sock is None:
                        reconnect_attempt += 1
                        if self.max_reconnect_attempts > 0 and \
                           reconnect_attempt >= self.max_reconnect_attempts:
                            print(f"[ERROR] Max reconnection attempts reached")
                            self.connection_lost.emit("Max reconnection attempts reached")
                            break
                        
                        print(f"[INFO] Waiting {self.reconnect_delay}s before retry...")
                        # Use small sleep intervals for responsive shutdown
                        for _ in range(int(self.reconnect_delay * 10)):
                            if self.stop_requested or not self.running:
                                break
                            time.sleep(0.1)
                        continue
                    else:
                        reconnect_attempt = 0
                
                # Run main communication loop
                print("COneection calling again")
                self.connection_loop(sock)
                
            except Exception as e:
                print(f"[ERROR] Connection error: {e}")
                self.currently_connected = False
                
                if sock:
                    try:
                        sock.close()
                    except:
                        pass
                
                if not self.stop_requested:
                    print(f"[INFO] Will reconnect in {self.reconnect_delay}s...")
                    
                    for _ in range(int(self.reconnect_delay * 10)):
                        if self.stop_requested or not self.running:
                            break
                        time.sleep(0.1)
                else:
                    break
        
        # Cleanup
        if sock:
            try:
                sock.close()
            except:
                pass
        
        # Stop tracking on exit
        self.video_player.stop_track()
        
        self.currently_connected = False
        print("[INFO] Drone hardkill stopped")

    def stop(self):
        """Stop the drone hardkill thread"""
        print("[INFO] Stop requested for drone hardkill")
        self.stop_requested = True
        self.running = False
        self.currently_connected = False
        
        # Stop tracking
        self.video_player.stop_track()
        
        if self.isRunning():
            self.requestInterruption()
            self.wait(3000)  # Wait up to 3 seconds
            if self.isRunning():
                print("[WARNING] Thread didn't stop gracefully, terminating...")
                self.terminate()
                self.wait(1000)
        
        print("[INFO] Drone hardkill stopped")


if __name__ == "__main__":
    print("DroneHardkill must be instantiated with video_player and camera objects")
