import serial
import struct
import numpy as np
import time
import math
import ctypes
from collections import deque
import os
import subprocess

def create_ccitt32_lib():
    """Create the ccitt32 library exactly as specified by Aeron"""
    c_code = """
    #include <stdint.h>
    
    uint32_t ccitt32_crcinit = 0xFFFFFFFF;
    
    static uint32_t crctab[256] = {
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
    };
    
    uint32_t ccitt32_updcrc(uint32_t icrc, uint8_t *icp, int icnt)
    {
    #define M1 0xffffff
    #define M2 0xffffff00
        uint32_t crc = icrc;
        uint8_t *cp = icp;
        int cnt = icnt;
    
        while(cnt--) {
            crc=((crc<<8)&M2)^crctab[((crc>>24)&0xff)^*cp++];
        }
    
        return(crc);
    }
    """
    
    with open("ccitt32.c", "w") as f:
        f.write(c_code)
    
    # Compile the C file
    # subprocess.run(["gcc", "-shared", "-o", "libccitt32.so", "-fPIC", "ccitt32.c"])
    subprocess.run(["gcc", "-shared", "-o", "libccitt32.dll", "-fPIC", "ccitt32.c"])

    return os.path.abspath("libccitt32.dll")


class CastorIMU:
    def __init__(self, port, baudrate=921600):
        """Initialize the Castor IMU head tracking system"""
        self.ser = serial.Serial(port, baudrate, timeout=1)
        self.ser.reset_input_buffer()  # Clear any pending data
        
        # Load the ccitt32 library
        lib_path = create_ccitt32_lib()
        self.ccitt_lib = ctypes.CDLL(lib_path)
        
        # Define argument and return types for ccitt32_updcrc
        self.ccitt_lib.ccitt32_updcrc.argtypes = [
            ctypes.c_uint32,  # icrc
            ctypes.POINTER(ctypes.c_uint8),  # icp
            ctypes.c_int  # icnt
        ]
        self.ccitt_lib.ccitt32_updcrc.restype = ctypes.c_uint32
        
        # Orientation state
        self.roll = 0.0
        self.pitch = 0.0
        self.yaw = 0.0
        
        # Filter parameters - REDUCED alpha for better responsiveness
        self.filter_alpha = 0.85  # Changed from 0.98 for more responsiveness
        
        # REDUCED deadband to detect smaller movements
        self.deadband = 0.05     # Changed from 0.5 to allow detecting slow movements
        
        # REDUCED moving average window to be more responsive
        self.ma_window_size = 3  # Changed from 5 to reduce lag
        
        # Moving average filter buffers
        self.gyro_buffer = {axis: deque([0]*self.ma_window_size, maxlen=self.ma_window_size) for axis in ['x', 'y', 'z']}
        self.accel_buffer = {axis: deque([0]*self.ma_window_size, maxlen=self.ma_window_size) for axis in ['x', 'y', 'z']}
        self.incli_buffer = {axis: deque([0]*self.ma_window_size, maxlen=self.ma_window_size) for axis in ['x', 'y', 'z']}
        
        self.prev_time = time.time()
        self.debug_mode = False  # Set to True for debugging output
        self.data_debug_mode = False  # For printing raw sensor values
        
    def calculate_crc32(self, data_bytes):
        """Calculate CRC32 using the ccitt32_updcrc function"""
        # Create a ctypes array from the data_bytes
        c_arr = (ctypes.c_uint8 * len(data_bytes))(*data_bytes)
        c_ptr = ctypes.cast(c_arr, ctypes.POINTER(ctypes.c_uint8))
        
        # Call ccitt32_updcrc with the initial value 0xFFFFFFFF
        crc = self.ccitt_lib.ccitt32_updcrc(0xFFFFFFFF, c_ptr, len(data_bytes))
        
        return crc
    
    def read_datagram(self):
        """Read a complete 0x93 datagram from the serial port"""
        # First, synchronize by finding 0x93 identifier
        while True:
            byte = self.ser.read(1)
            if not byte:  # Timeout
                return None
            if byte[0] == 0x93:
                break
        
        # Read the remaining 39 bytes (33 data + 4 CRC + 2 CRLF)
        remaining_data = self.ser.read(39)
        if len(remaining_data) < 39:
            if self.debug_mode:
                print(f"Incomplete datagram: read only {len(remaining_data)} of 39 bytes")
            return None
        
        # Combine the identifier and the data
        complete_datagram = bytearray([0x93]) + remaining_data
        
        if self.debug_mode:
            print("Raw datagram:", " ".join(f"{b:02x}" for b in complete_datagram))
        
        return complete_datagram
    
    def validate_datagram(self, datagram):
        """Validate CRC of a 0x93 datagram according to Aeron's instructions"""
        if len(datagram) < 40:
            if self.debug_mode:
                print(f"Invalid datagram length: {len(datagram)} bytes, expected 40")
            return False
        
        # First byte is 0x93 identifier
        if datagram[0] != 0x93:
            if self.debug_mode:
                print(f"Invalid datagram identifier: 0x{datagram[0]:02x}, expected 0x93")
            return False
        
        # Extract received CRC32 (bytes 34-37)
        received_crc = int.from_bytes(datagram[34:38], byteorder='big')
        
        # Create temporary buffer with the first 34 bytes (includes 0x93 identifier)
        temp_buffer = bytearray(datagram[:34])
        
        # Add 2 padding zeros to make it 36 bytes
        temp_buffer.extend([0, 0])
        
        # Calculate CRC32
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
        
        # if self.data_debug_mode:
        #     print(f"Raw gyro: X={gyro['x']:.4f}, Y={gyro['y']:.4f}, Z={gyro['z']:.4f}")
        #     print(f"Raw accel: X={accel['x']:.4f}, Y={accel['y']:.4f}, Z={accel['z']:.4f}")
        #     print(f"Raw incli: X={incli['x']:.4f}, Y={incli['y']:.4f}, Z={incli['z']:.4f}")
        
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
    
    def parse_24bit_value(self, byte_array, scale_factor):
        """Parse a signed 24-bit value and scale it appropriately"""
        # Convert to a 24-bit integer (assuming big-endian)
        value = int.from_bytes(byte_array, byteorder='big', signed=False)
        
        # Handle two's complement for negative values
        if value & 0x800000:
            value = value - 0x1000000
        
        # Scale the value
        return value / scale_factor
    
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
    
    def close(self):
        """Close the serial connection"""
        self.ser.close()


class PTZController:
    """Controller for PTZ camera movement based on head orientation"""
    def __init__(self, ip_address="192.168.1.100", username="admin", password="admin"):
        """Initialize the PTZ controller"""
        self.ip_address = ip_address
        self.username = username
        self.password = password
        self.connected = False
        
        # Movement scaling factors (adjust as needed)
        self.pan_scale = 1.0   # Scale factor for left/right movement
        self.tilt_scale = 0.8  # Scale factor for up/down movement
        
        # Last sent positions to avoid sending duplicate commands
        self.last_pan = 0.0
        self.last_tilt = 0.0
        
        # Minimum change required to send a new command
        self.min_change = 0.1  # In degrees
        
        # Connect to PTZ camera (implement actual connection here)
        # self.connect()
        
    def connect(self):
        """Connect to the PTZ camera (implement based on your camera's protocol)"""
        # Placeholder - replace with actual connection code
        print(f"Connecting to PTZ camera at {self.ip_address}...")
        self.connected = True
        print("Connected to PTZ camera.")
    
    def update(self, yaw, pitch):
        """Update the PTZ camera position based on head orientation"""
        if not self.connected:
            return False
            
        # Scale movement
        pan = -yaw * self.pan_scale   # Negative to match natural head movement
        tilt = -pitch * self.tilt_scale
        
        # Check if movement is significant enough to send a command
        if (abs(pan - self.last_pan) > self.min_change or
            abs(tilt - self.last_tilt) > self.min_change):
            
            # Send command to camera (implement based on your camera's protocol)
            print(f"PTZ Command: Pan: {pan:.2f}, Tilt: {tilt:.2f}")
            
            # Update last sent values
            self.last_pan = pan
            self.last_tilt = tilt
            return True
        
        return False
    
    def close(self):
        """Close the connection to the PTZ camera"""
        if self.connected:
            print("Disconnecting from PTZ camera.")
            self.connected = False


def main():
    # Initialize IMU with your port (change to match your setup)
    port = 'COM8'  # Change this to your serial port
    
    print(f"Initializing IMU on port {port}...")
    imu = CastorIMU(port)
    
    # Enable these for debugging
    imu.debug_mode = False
    imu.data_debug_mode = True  # Set to True to print raw sensor values
    
    # Optionally initialize PTZ control
    # ptz = PTZController()
    
    try:
        print("Starting head tracking. Press Ctrl+C to exit.")
        print("Roll, Pitch, Yaw (degrees)")
        
        # Main loop
        while True:
            data = imu.read_and_process()
            
            if data:
                orientation = data['orientation']
                
                # Print orientation values including raw values
                print(f"Roll: {orientation['roll']:.2f} (raw: {orientation['raw_roll']:.2f}), "
                      f"Pitch: {orientation['pitch']:.2f} (raw: {orientation['raw_pitch']:.2f}), "
                      f"Yaw: {orientation['yaw']:.2f} (raw: {orientation['raw_yaw']:.2f})")
                
                # Update PTZ camera if enabled
                # ptz.update(orientation['yaw'], orientation['pitch'])
            
            # time.sleep(0.001)  # Small delay
            
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        imu.close()
        # if 'ptz' in locals():
        #     ptz.close()


if __name__ == "__main__":
    main()