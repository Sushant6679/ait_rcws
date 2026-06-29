import serial.tools.list_ports
import serial
import math
import time
import sys
import struct
import numpy as np
from collections import deque
import os
from PyQt5.QtCore import pyqtSignal, QThread
import threading


class AutoPilotController(QThread):
    # Make sure to define this exactly as expected by the Main.py
    # stab_change = pyqtSignal(float, float, float, float, float, float)
    
    def __init__(self, port=None, baud=921600):
        super().__init__()
        self.data_lock = threading.Lock()
        self.latest_data = {
            'rollspeed': 0.0, 'pitchspeed': 0.0, 'yawspeed': 0.0,
            'roll': 0.0, 'pitch': 0.0, 'yaw': 0.0,
            'timestamp': 0.0, 'new_data': False,
            'packet_count': 0, 'packets_per_second': 0,
            'total_packets_per_second': 0  # Includes invalid packets
        }
        self.port = port
        self.baud = baud
        self.connected = False
        self.running = False

        # Initialize CRC32 lookup table (Pure Python - no external C file needed)
        self.crc_table = self._generate_crc_table()
        
        # Initialize serial connection
        self.ser = None
        
        # Orientation state
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        
        # Filter parameters
        self.filter_alpha = 0.85  # Responsiveness parameter
        self.deadband = 0.05      # Minimum change to register
        self.ma_window_size = 3   # Moving average window size
        
        # Moving average filter buffers
        self.gyro_buffer = {axis: deque([0]*self.ma_window_size, maxlen=self.ma_window_size) for axis in ['x', 'y', 'z']}
        self.accel_buffer = {axis: deque([0]*self.ma_window_size, maxlen=self.ma_window_size) for axis in ['x', 'y', 'z']}
        self.incli_buffer = {axis: deque([0]*self.ma_window_size, maxlen=self.ma_window_size) for axis in ['x', 'y', 'z']}
        
        self.prev_time = time.time()
        self.debug_mode = False

    def _generate_crc_table(self):
        """Generate the CRC32 lookup table - same as the original C implementation"""
        return [
            0x00000000, 0x04c11db7, 0x09823b6e, 0x0d4326d9,
            0x130476dc, 0x17c56b6b, 0x1a864db2, 0x1e475005,
            0x2608edb8, 0x22c9f00f, 0x2f8ad6d6, 0x2b4bcb61,
            0x350c9b64, 0x31cd86d3, 0x3c8ea00a, 0x384fbdbd,
            0x4c11db70, 0x48d0c6c7, 0x4593e01e, 0x4152fda9,
            0x5f15adac, 0x5bd4b01b, 0x569796c2, 0x52568b75,
            0x6a1936c8, 0x6ed82b7f, 0x639b0da6, 0x675a1011,
            0x791d4014, 0x7ddc5da3, 0x709f7b7a, 0x745e66cd,
            0x9823b6e0, 0x9ce2ab57, 0x91a18d8e, 0x95609039,
            0x8b27c03c, 0x8fe6dd8b, 0x82a5fb52, 0x8664e6e5,
            0xbe2b5b58, 0xbaea46ef, 0xb7a96036, 0xb3687d81,
            0xad2f2d84, 0xa9ee3033, 0xa4ad16ea, 0xa06c0b5d,
            0xd4326d90, 0xd0f37027, 0xddb056fe, 0xd9714b49,
            0xc7361b4c, 0xc3f706fb, 0xceb42022, 0xca753d95,
            0xf23a8028, 0xf6fb9d9f, 0xfbb8bb46, 0xff79a6f1,
            0xe13ef6f4, 0xe5ffeb43, 0xe8bccd9a, 0xec7dd02d,
            0x34867077, 0x30476dc0, 0x3d044b19, 0x39c556ae,
            0x278206ab, 0x23431b1c, 0x2e003dc5, 0x2ac12072,
            0x128e9dcf, 0x164f8078, 0x1b0ca6a1, 0x1fcdbb16,
            0x018aeb13, 0x054bf6a4, 0x0808d07d, 0x0cc9cdca,
            0x7897ab07, 0x7c56b6b0, 0x71159069, 0x75d48dde,
            0x6b93dddb, 0x6f52c06c, 0x6211e6b5, 0x66d0fb02,
            0x5e9f46bf, 0x5a5e5b08, 0x571d7dd1, 0x53dc6066,
            0x4d9b3063, 0x495a2dd4, 0x44190b0d, 0x40d816ba,
            0xaca5c697, 0xa864db20, 0xa527fdf9, 0xa1e6e04e,
            0xbfa1b04b, 0xbb60adfc, 0xb6238b25, 0xb2e29692,
            0x8aad2b2f, 0x8e6c3698, 0x832f1041, 0x87ee0df6,
            0x99a95df3, 0x9d684044, 0x902b669d, 0x94ea7b2a,
            0xe0b41de7, 0xe4750050, 0xe9362689, 0xedf73b3e,
            0xf3b06b3b, 0xf771768c, 0xfa325055, 0xfef34de2,
            0xc6bcf05f, 0xc27dede8, 0xcf3ecb31, 0xcbffd686,
            0xd5b88683, 0xd1799b34, 0xdc3abded, 0xd8fba05a,
            0x690ce0ee, 0x6dcdfd59, 0x608edb80, 0x644fc637,
            0x7a089632, 0x7ec98b85, 0x738aad5c, 0x774bb0eb,
            0x4f040d56, 0x4bc510e1, 0x46863638, 0x42472b8f,
            0x5c007b8a, 0x58c1663d, 0x558240e4, 0x51435d53,
            0x251d3b9e, 0x21dc2629, 0x2c9f00f0, 0x285e1d47,
            0x36194d42, 0x32d850f5, 0x3f9b762c, 0x3b5a6b9b,
            0x0315d626, 0x07d4cb91, 0x0a97ed48, 0x0e56f0ff,
            0x1011a0fa, 0x14d0bd4d, 0x19939b94, 0x1d528623,
            0xf12f560e, 0xf5ee4bb9, 0xf8ad6d60, 0xfc6c70d7,
            0xe22b20d2, 0xe6ea3d65, 0xeba91bbc, 0xef68060b,
            0xd727bbb6, 0xd3e6a601, 0xdea580d8, 0xda649d6f,
            0xc423cd6a, 0xc0e2d0dd, 0xcda1f604, 0xc960ebb3,
            0xbd3e8d7e, 0xb9ff90c9, 0xb4bcb610, 0xb07daba7,
            0xae3afba2, 0xaafbe615, 0xa7b8c0cc, 0xa379dd7b,
            0x9b3660c6, 0x9ff77d71, 0x92b45ba8, 0x9675461f,
            0x8832161a, 0x8cf30bad, 0x81b02d74, 0x857130c3,
            0x5d8a9099, 0x594b8d2e, 0x5408abf7, 0x50c9b640,
            0x4e8ee645, 0x4a4ffbf2, 0x470cdd2b, 0x43cdc09c,
            0x7b827d21, 0x7f436096, 0x7200464f, 0x76c15bf8,
            0x68860bfd, 0x6c47164a, 0x61043093, 0x65c52d24,
            0x119b4be9, 0x155a565e, 0x18197087, 0x1cd86d30,
            0x029f3d35, 0x065e2082, 0x0b1d065b, 0x0fdc1bec,
            0x3793a651, 0x3352bbe6, 0x3e119d3f, 0x3ad08088,
            0x2497d08d, 0x2056cd3a, 0x2d15ebe3, 0x29d4f654,
            0xc5a92679, 0xc1683bce, 0xcc2b1d17, 0xc8ea00a0,
            0xd6ad50a5, 0xd26c4d12, 0xdf2f6bcb, 0xdbee767c,
            0xe3a1cbc1, 0xe760d676, 0xea23f0af, 0xeee2ed18,
            0xf0a5bd1d, 0xf464a0aa, 0xf9278673, 0xfde69bc4,
            0x89b8fd09, 0x8d79e0be, 0x803ac667, 0x84fbdbd0,
            0x9abc8bd5, 0x9e7d9662, 0x933eb0bb, 0x97ffad0c,
            0xafb010b1, 0xab710d06, 0xa6322bdf, 0xa2f33668,
            0xbcb4666d, 0xb8757bda, 0xb5365d03, 0xb1f740b4,
        ]

    def calculate_crc32(self, data_bytes):
        """Pure Python CRC32 calculation - identical algorithm to C version"""
        crc = 0xFFFFFFFF  # Initial value (ccitt32_crcinit)
        
        for byte in data_bytes:
            # Extract the high byte and XOR with current byte
            tbl_idx = ((crc >> 24) & 0xFF) ^ byte
            # Shift left by 8 and XOR with table value
            crc = ((crc << 8) & 0xFFFFFF00) ^ self.crc_table[tbl_idx]
            # Ensure we stay within 32-bit bounds
            crc &= 0xFFFFFFFF
        
        return crc

    def detect_port(self):
        ports = serial.tools.list_ports.comports(include_links=False)
        
        if sys.platform == 'win32':
            # Windows-specific detection
            for port in ports:
                if 'USB Serial Device' in port.description:
                    return port.device
        elif sys.platform.startswith('linux'):
            # Linux-specific detection
            for port in ports:
                if 'USB' in port.description:
                    return port.device
        else:
            # Generic detection for other platforms
            for port in ports:
                if any(keyword in port.description for keyword in ['USB Serial Device']):
                    return port.device
        
        return None

    def connect_to_port(self):
        """Optimized connection method for high-speed data"""
        # Clean up any existing connection first
        if hasattr(self, 'ser') and self.ser is not None:
            try:
                if self.ser.is_open:
                    self.ser.close()
            except:
                pass
            self.ser = None
        
        self.port = self.port or self.detect_port()
        if self.port:
            try:
                # Initialize the serial connection with optimized settings for high-speed data
                self.ser = serial.Serial(
                    port=self.port, 
                    baudrate=self.baud,
                    timeout=0.001,  # Very short timeout for non-blocking reads
                    write_timeout=0.001,
                    bytesize=serial.EIGHTBITS,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    xonxoff=False,  # Disable software flow control
                    rtscts=False,   # Disable hardware flow control
                    dsrdtr=False    # Disable DSR/DTR flow control
                )
                
                time.sleep(0.1)  # Shorter stabilization time
                
                if self.ser.is_open:
                    # Set larger buffer sizes for high-speed data
                    if hasattr(self.ser, 'set_buffer_size'):
                        self.ser.set_buffer_size(rx_size=8192, tx_size=8192)
                    
                    # Clear any stale data
                    self.ser.reset_input_buffer()
                    self.ser.reset_output_buffer()
                    
                    self.connected = True
                    print(f"Connected to Castor IMU on {self.port} with optimized settings")
                else:
                    raise Exception("Serial port failed to open")
                    
            except Exception as e:
                print(f"Failed to connect to Castor IMU on {self.port}: {e}")
                self.connected = False
                self.ser = None
        else:
            print("No suitable port found for Castor IMU")
            self.connected = False
            self.ser = None
    
    def read_datagram(self):
        """Read a complete 0x93 datagram from the serial port - optimized for high speed"""
        if not self.ser or not self.ser.is_open:
            return None
            
        try:
            # Check how much data is available
            bytes_available = self.ser.in_waiting
            
            # If we have less than a full datagram, wait briefly
            if bytes_available < 40:
                time.sleep(0.0001)  # 0.1ms wait
                bytes_available = self.ser.in_waiting
            
            # If still not enough data, return None to avoid blocking
            if bytes_available < 40:
                return None
            
            # Read in larger chunks to reduce system calls
            chunk_size = min(bytes_available, 200)  # Read up to 5 datagrams worth
            data_chunk = self.ser.read(chunk_size)
            
            if not data_chunk:
                return None
            
            # Find 0x93 identifier in the chunk
            for i in range(len(data_chunk)):
                if data_chunk[i] == 0x93:
                    # Check if we have a complete datagram
                    remaining_needed = 40 - (len(data_chunk) - i)
                    if remaining_needed > 0:
                        # Read the remaining bytes
                        additional_data = self.ser.read(remaining_needed)
                        if len(additional_data) < remaining_needed:
                            continue  # Incomplete datagram
                        complete_datagram = data_chunk[i:] + additional_data
                    else:
                        complete_datagram = data_chunk[i:i+40]
                    
                    if len(complete_datagram) == 40:
                        return bytearray(complete_datagram)
            
            return None
                
        except Exception as e:
            print(f"Error reading datagram: {e}")
            return None
    
    def validate_datagram(self, datagram):
        """Validate CRC of a 0x93 datagram - Pure Python implementation"""
        if len(datagram) < 40:
            return False
        
        # First byte is 0x93 identifier
        if datagram[0] != 0x93:
            if self.debug_mode:
                print(f"Invalid datagram identifier: 0x{datagram[0]:02x}, expected 0x93")
            return False
        
        # Extract received CRC32 (bytes 34-37)
        received_crc = int.from_bytes(datagram[34:38], byteorder='big')
        
        # Create buffer with the first 34 bytes plus 2 padding zeros
        temp_buffer = datagram[:34] + bytes([0, 0])
        
        # Calculate CRC32 using pure Python implementation
        calculated_crc = self.calculate_crc32(temp_buffer)
        
        if self.debug_mode:
            print(f"Received CRC: 0x{received_crc:08x}")
            print(f"Calculated CRC: 0x{calculated_crc:08x}")
        
        # Compare CRCs
        if calculated_crc != received_crc:
            # Try with different endianness
            received_crc_alt = int.from_bytes(datagram[34:38], byteorder='little')
            if calculated_crc == received_crc_alt:
                if self.debug_mode:
                    print("CRC matches with little-endian byte order!")
                return True
            
            if self.debug_mode:
                print(f"CRC mismatch: calculated=0x{calculated_crc:08x}, received=0x{received_crc:08x}")
            return False
        
        return True
    
    def parse_24bit_value(self, byte_array, scale_factor):
        """Parse a signed 24-bit value and scale it appropriately"""
        # Convert to a 24-bit integer (assuming big-endian)
        value = int.from_bytes(byte_array, byteorder='big', signed=False)
        
        # Handle two's complement for negative values
        if value & 0x800000:
            value = value - 0x1000000
        
        # Scale the value
        return value / scale_factor
    
    def parse_sensor_data(self, datagram):
        """Parse all sensor data from the datagram"""
        # Gyro data: bytes 1-9 (3 bytes per axis)
        gyro = {
            'x': self.parse_24bit_value(datagram[1:4], scale_factor=2**14),
            'y': self.parse_24bit_value(datagram[4:7], scale_factor=2**14),
            'z': self.parse_24bit_value(datagram[7:10], scale_factor=2**14)
        }
        
        # Accelerometer data: bytes 11-19
        accel = {
            'x': self.parse_24bit_value(datagram[11:14], scale_factor=2**16),
            'y': self.parse_24bit_value(datagram[14:17], scale_factor=2**16),
            'z': self.parse_24bit_value(datagram[17:20], scale_factor=2**16)
        }
        
        # Inclinometer data: bytes 21-29
        incli = {
            'x': self.parse_24bit_value(datagram[21:24], scale_factor=2**22),
            'y': self.parse_24bit_value(datagram[24:27], scale_factor=2**22),
            'z': self.parse_24bit_value(datagram[27:30], scale_factor=2**22)
        }
        
        # Status bytes
        status = {
            'gyro': datagram[10],
            'accel': datagram[20],
            'incli': datagram[30]
        }
        
        # Apply moving average filter
        filtered_gyro = self.apply_moving_avg(gyro, self.gyro_buffer)
        filtered_accel = self.apply_moving_avg(accel, self.accel_buffer)
        filtered_incli = self.apply_moving_avg(incli, self.incli_buffer)
        
        return {
            'gyro': filtered_gyro,
            'accel': filtered_accel,
            'incli': filtered_incli,
            'status': status,
            'raw_gyro': gyro  # Store raw values for diagnostics
        }
    
    def apply_moving_avg(self, values, buffer):
        """Apply moving average filter to sensor values"""
        for axis, value in values.items():
            buffer[axis].append(value)
        
        # Calculate the moving average
        return {
            axis: sum(buffer[axis]) / len(buffer[axis])
            for axis in values.keys()
        }
    
    def calculate_orientation(self, sensor_data, dt):
        """Calculate orientation using complementary filter"""
        gyro = sensor_data['gyro']
        accel = sensor_data['accel']
        incli = sensor_data['incli']
        
        # Calculate accel-based angles
        accel_pitch = math.atan2(-accel['x'], math.sqrt(accel['y']**2 + accel['z']**2)) * 180.0 / math.pi
        accel_roll = math.atan2(accel['y'], accel['z']) * 180.0 / math.pi
        
        # Calculate inclinometer-based angles
        incli_pitch = math.atan2(-incli['x'], math.sqrt(incli['y']**2 + incli['z']**2)) * 180.0 / math.pi
        incli_roll = math.atan2(incli['y'], incli['z']) * 180.0 / math.pi
        
        # Blend the angle measurements (weighted towards inclinometer for stability)
        stable_pitch = 0.7 * incli_pitch + 0.3 * accel_pitch
        stable_roll = 0.7 * incli_roll + 0.3 * accel_roll
        
        # Complementary filter
        self.pitch = self.filter_alpha * (self.pitch + gyro['y'] * dt) + (1 - self.filter_alpha) * stable_pitch
        self.roll = self.filter_alpha * (self.roll + gyro['x'] * dt) + (1 - self.filter_alpha) * stable_roll
        self.yaw += gyro['z'] * dt  # Pure integration for yaw
        
        # Apply deadband to reduce jitter - ONLY FOR DISPLAY, not for calculation
        display_roll = self.roll if abs(self.roll) > self.deadband else 0.0
        display_pitch = self.pitch if abs(self.pitch) > self.deadband else 0.0
        display_yaw = self.yaw if abs(self.yaw) > self.deadband else 0.0
        
        return {
            'roll': display_roll,
            'pitch': display_pitch,
            'yaw': display_yaw,
            'raw_roll': self.roll,  # Store raw values (unaffected by deadband)
            'raw_pitch': self.pitch,
            'raw_yaw': self.yaw
        }
    
    def read_and_process(self):
        """Read a datagram, validate it, and process the sensor data"""
        # Read a complete datagram
        datagram = self.read_datagram()
        if not datagram:
            return None
        
        # Validate the datagram's CRC
        if not self.validate_datagram(datagram):
            return None
            
        # Parse sensor data
        sensor_data = self.parse_sensor_data(datagram)
        
        # Calculate time delta
        current_time = time.time()
        dt = current_time - self.prev_time
        self.prev_time = current_time
        
        # Calculate orientation
        orientation = self.calculate_orientation(sensor_data, dt)
        
        return {
            'orientation': orientation,
            'sensor_data': sensor_data,
            'dt': dt
        }

    def run(self):
        self.running = True
        print("AutoPilot run() method started")
        
        # Performance monitoring
        last_perf_time = time.time()
        packet_count = 0
        valid_packet_count = 0
        
        while self.running:
            if not self.connected:
                self.connect_to_port()
                if not self.connected:
                    time.sleep(1)  # Shorter retry interval
                    continue

            print("Entering main data loop")
            while self.connected and self.running:
                try:
                    # Read multiple datagrams in a burst to catch up
                    processed_this_loop = 0
                    max_per_loop = 5  # Process up to 5 packets per loop iteration
                    
                    while processed_this_loop < max_per_loop and self.running:
                        datagram = self.read_datagram()
                        if not datagram:
                            break
                        
                        packet_count += 1
                        
                        # Validate the datagram's CRC
                        if not self.validate_datagram(datagram):
                            # Skip invalid datagrams, don't count as processed
                            continue
                        
                        valid_packet_count += 1
                        
                        # Parse sensor data
                        sensor_data = self.parse_sensor_data(datagram)
                        
                        # Calculate time delta
                        current_time = time.time()
                        dt = current_time - self.prev_time
                        self.prev_time = current_time
                        
                        # Calculate orientation
                        orientation = self.calculate_orientation(sensor_data, dt)
                        
                        # Extract values
                        rollspeed = float(sensor_data['raw_gyro']['x'])
                        pitchspeed = float(sensor_data['raw_gyro']['y'])
                        yawspeed = float(sensor_data['raw_gyro']['z'])
                        
                        roll = float(orientation['raw_roll'])
                        pitch = float(orientation['raw_pitch'])
                        yaw = float(orientation['raw_yaw'])
                        
                        # Update shared data (only update with latest packet to avoid UI flooding)
                        with self.data_lock:
                            self.latest_data.update({
                                'rollspeed': round(rollspeed, 2),
                                'pitchspeed': round(pitchspeed, 2),
                                'yawspeed': round(yawspeed, 2),
                                'roll': round(roll, 2),
                                'pitch': round(pitch, 2),
                                'yaw': round(yaw, 2),
                                'timestamp': time.time(),
                                'new_data': True,
                                'packet_count': valid_packet_count
                            })
                        
                        processed_this_loop += 1
                    
                    # Performance monitoring - update every second
                    current_time = time.time()
                    if current_time - last_perf_time >= 1.0:
                        # Calculate rates
                        total_pps = packet_count  # Total packets received
                        valid_pps = valid_packet_count  # Valid packets processed
                        
                        # Share the processing rate with UI
                        with self.data_lock:
                            self.latest_data['packets_per_second'] = valid_pps
                            self.latest_data['total_packets_per_second'] = total_pps
                        
                        # Console output for debugging
                        if total_pps != valid_pps:
                            print(f"Processed {valid_pps} valid packets ({total_pps} total, {total_pps - valid_pps} invalid) in last second")
                        else:
                            print(f"Processed {valid_pps} packets in last second")
                        
                        # Reset counters
                        packet_count = 0
                        valid_packet_count = 0
                        last_perf_time = current_time
                    
                    # Very short sleep to prevent CPU maxing but maintain responsiveness
                    if processed_this_loop == 0:
                        time.sleep(0.0001)  # 0.1ms when no packets processed
                    
                except Exception as e:
                    print(f"Error in main loop: {e}")
                    self.connected = False
                    if self.ser and self.ser.is_open:
                        try:
                            self.ser.close()
                        except:
                            pass
                    self.ser = None
                    break
        
        print("AutoPilot run() method ended")

    def close(self):
        """Close the serial connection"""
        print("Closing AutoPilot controller...")
        self.running = False
        self.connected = False
        
        # Properly close serial connection
        if hasattr(self, 'ser') and self.ser is not None:
            try:
                if self.ser.is_open:
                    self.ser.close()
                    print("Serial port closed successfully")
            except Exception as e:
                print(f"Error closing serial port: {e}")
            finally:
                self.ser = None
        
        # Stop the thread
        if self.isRunning():
            self.requestInterruption()
            self.wait(2000)  # Wait up to 2 seconds for thread to finish
            if self.isRunning():
                print("Thread didn't stop gracefully, terminating...")
                self.terminate()
                self.wait(1000)


if __name__ == "__main__":
    controller = AutoPilotController()
    controller.start()