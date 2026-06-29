import serial
import time
import struct
import sys
import serial.tools.list_ports

class RS485WindSpeedTransmitter:
    def __init__(self, port=None, baudrate=9600):
        if port is None:
            port = self.detect_port()
        # if port is None:
        #     raise ValueError("No suitable port found for the Anemometer")
        
        self.ser = serial.Serial(
            port=port,
            baudrate=baudrate,
            bytesize=serial.EIGHTBITS,
            parity=serial.PARITY_NONE,
            stopbits=serial.STOPBITS_ONE,
            timeout=1
        )

    @classmethod
    def detect_port(cls):
        """Automatically detect the serial port across different operating systems."""
        ports = serial.tools.list_ports.comports(include_links=False)
        
        # if sys.platform == 'win32':
        #     # Windows-specific detection
        #     for port in ports:
        #         if "Silicon Labs" in port.description or "Silicon" in port.description:
        #             print(f"Found Silicon device at {port.device}")
        #             return port.device
        if sys.platform == 'win32':
            # Windows-specific detection
            for port in ports:
                if "Prolific PL2303GC" in port.description or "Prolific USB" in port.description:
                    print(f"Found Prolific device at {port.device}")
                    return port.device
        elif sys.platform.startswith('linux'):
            # Linux-specific detection
            for port in ports:
                print(f"Checking port: {port.device} - {port.description}")
                if "USB-Serial Controller" in port.description:
                    print(f"Found USB-Serial Controller device at {port.device}")
                    return port.device
        else:
            # Generic detection for other platforms
            for port in ports:
                if any(keyword in port.description for keyword in ["Prolific", "USB-Serial Controller"]):
                    print(f"Found matching device at {port.device}")
                    return port.device
        return None

    def crc16(self, data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 0x0001:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    def modify_address(self, old_address, new_address):
        command = bytearray([old_address, 0x10, 0x10, 0x00, 0x00, 0x01, 0x02, 0x00, new_address])
        crc = self.crc16(command)
        command += struct.pack('<H', crc)
        
        self.ser.write(command)
        time.sleep(0.1)
        response = self.ser.read(8)
        
        if len(response) == 8 and response[0] == old_address and response[1] == 0x10:
            print("Address modified successfully.")
            return True
        else:
            print("Address modification failed!")
            return False

    def read_wind_speed(self, address):
        try:
            command = bytearray([address, 0x03, 0x00, 0x00, 0x00, 0x01])
            crc = self.crc16(command)
            command += struct.pack('<H', crc)
            
            # print(f"Sending command: {command.hex()}")
            
            # Flush input buffer before sending command
            self.ser.reset_input_buffer()
            
            self.ser.write(command)
            time.sleep(0.1)  # Slightly increased timeout
            
            # Read more bytes to ensure we capture the full response
            response = self.ser.read(10)
            
            # print(f"Response received: {response.hex() if response else 'None'}, Length: {len(response)}")
            
            # Look for the pattern [address, 0x03] anywhere in the response
            found_start = -1
            for i in range(len(response) - 1):
                if response[i] == address and response[i+1] == 0x03:
                    found_start = i
                    break
            
            if found_start >= 0 and found_start + 6 <= len(response):
                # Extract the response starting from the found position
                actual_response = response[found_start:found_start+7]
                wind_speed = struct.unpack('>H', actual_response[3:5])[0] / 10.0
                # print(f"Found valid response starting at position {found_start}")
                return wind_speed
            else:
                print("Could not find valid response pattern")
                # Print the bytes we're looking for
                print(f"Looking for pattern: {address:02x} 03")
                return None
        except Exception as e:
            print(f"Error reading wind speed: {e}")
            return None

def main():
    try:
        sensor = RS485WindSpeedTransmitter()
        address = 2
        while True:
            wind_speed = sensor.read_wind_speed(address)
            if wind_speed is not None:
                print(f"Wind Speed: {wind_speed:.1f} m/s")
            else:
                print("Please check whether the sensor connection is normal")
                break
            time.sleep(0.05)
    except ValueError as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()