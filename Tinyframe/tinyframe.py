#!/usr/bin/env python3
"""
TinyFrame Python Wrapper - A Python interface to the TinyFrame protocol library
"""

import os
import sys
import time
import threading
import ctypes
import logging
from ctypes import c_bool, c_char_p, c_int, c_uint8, c_uint16, c_uint32, POINTER, CFUNCTYPE
import serial
import serial.tools.list_ports

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TinyFrame")
# Define callback function type for frame listeners
# Parameters: type, data, len, frame_id
LISTENER_CALLBACK = CFUNCTYPE(None, c_uint8, POINTER(c_uint8), c_uint32, c_uint16)

class TinyFrame:
    """
    Python wrapper for the TinyFrame protocol library
    """
    def __init__(self, max_types=256):
        """
        Initialize the TinyFrame wrapper
        
        Args:
            max_types (int): Maximum number of message types to support
        """
        self.max_types = max_types
        self.lib = None
        self.port = None
        self._callbacks = {}  # Store Python callbacks by type
        self._c_callbacks = {}  # Store C function pointers by type
        self._reader_thread = None
        self._stop_thread = False
        
        # Load the appropriate library for this platform
        self._load_library()
        
        # Initialize TinyFrame
        if not self.lib.tf_init(max_types):
            raise RuntimeError("Failed to initialize TinyFrame library")
    
    def _load_library(self):
        """Load the appropriate TinyFrame library for this platform"""
        # Determine the platform-specific library name and search paths
        if sys.platform == 'win32':
            lib_name = 'tinyframe_python.dll'
            search_paths = ['lib', 'bin', '.']
        elif sys.platform.startswith('linux') or sys.platform == 'darwin':
            lib_name = 'libtinyframe_python.so'
            search_paths = ['lib', '.']
        else:
            raise RuntimeError(f"Unsupported platform: {sys.platform}")
        
        # Search for the library
        for path in search_paths:
            try:
                lib_path = os.path.join(path, lib_name)
                if os.path.exists(lib_path):
                    self.lib = ctypes.CDLL(lib_path)
                    break
            except OSError:
                continue
        
        if self.lib is None:
            raise RuntimeError(f"Could not find {lib_name} in any of the search paths: {search_paths}")
        
        # Define function prototypes
        self.lib.tf_init.argtypes = [c_int]
        self.lib.tf_init.restype = c_bool
        
        self.lib.tf_open_port.argtypes = [c_char_p, c_int]
        self.lib.tf_open_port.restype = c_bool
        
        self.lib.tf_close_port.argtypes = []
        self.lib.tf_close_port.restype = None
        
        self.lib.tf_register_listener.argtypes = [c_uint8, LISTENER_CALLBACK]
        self.lib.tf_register_listener.restype = c_bool
        
        self.lib.tf_send.argtypes = [c_uint8, POINTER(c_uint8), c_uint32]
        self.lib.tf_send.restype = c_bool
        
        self.lib.tf_accept.argtypes = [POINTER(c_uint8), c_uint32]
        self.lib.tf_accept.restype = None
        
        self.lib.tf_read_and_process.argtypes = []
        self.lib.tf_read_and_process.restype = c_int
        
        self.lib.tf_cleanup.argtypes = []
        self.lib.tf_cleanup.restype = None
    
    def find_port(self, description_keywords=None):
        """
        Find a serial port based on description keywords
        
        Args:
            description_keywords (list): List of strings to search for in port descriptions
                
        Returns:
            str: Port name or None if not found
        """
        if description_keywords is None:
            description_keywords = ["USB-Enhanced-SERIAL", "Silicon Labs", "CP2102"]  # Prioritize USB-Enhanced-SERIAL
        
        ports = list(serial.tools.list_ports.comports())
        
        if not ports:
            print("No COM ports found")
            return None
            
        print("Available ports:")
        for port in ports:
            print(f"  {port.device} - {port.description}")
        
        # First, specifically look for USB-Enhanced-SERIAL
        for port in ports:
            if "USB-Enhanced-SERIAL" in port.description:
                print(f"Found USB-Enhanced-SERIAL device: {port.device}")
                return port.device
                
        # Then look for other keywords
        if sys.platform == 'win32':
            for port in ports:
                for keyword in description_keywords:
                    if keyword in port.description:
                        print(f"Found port matching '{keyword}': {port.device}")
                        return port.device
        elif sys.platform.startswith('linux'):
            for port in ports:
                for keyword in description_keywords:
                    if keyword in port.description:
                        print(f"Found port matching '{keyword}': {port.device}")
                        return port.device
        
        # If no matching port found, return the first available port
        if ports:
            print(f"No port matching description keywords found. Using first available: {ports[0].device}")
            return ports[0].device
        
        return None
    
    def open_port(self, port=None, baud_rate=115200, description_keywords=None):
        """
        Open a serial port for communication
        
        Args:
            port (str): Port name (e.g., 'COM1', '/dev/ttyUSB0')
            baud_rate (int): Baud rate
            description_keywords (list): If port is None, use these keywords to find a port
            
        Returns:
            bool: True if port was opened successfully
        """
        # If no port specified, try to find one
        if port is None:
            port = self.find_port(description_keywords)
            if port is None:
                print("Could not find a suitable COM port")
                return False
        
        # Open the port
        if self.lib.tf_open_port(port.encode('utf-8'), baud_rate):
            self.port = port
            return True
        return False
    
    def close_port(self):
        """Close the serial port"""
        if self.port:
            self._stop_reader_thread()
            self.lib.tf_close_port()
            self.port = None
    
    def register_listener(self, type_id, callback):
        """
        Register a callback for a specific message type
        
        Args:
            type_id (int): Message type ID
            callback (function): Callback function taking (type_id, data, length, frame_id)
                
        Returns:
            bool: True if listener was registered successfully
        """
        if type_id >= self.max_types:
            raise ValueError(f"Type ID {type_id} is out of range (max: {self.max_types-1})")
        
        # Store the Python callback in our dictionary
        self._callbacks[type_id] = callback
        
        # Check if we already have a generic listener registered
        if not hasattr(self, '_generic_listener_registered') or not self._generic_listener_registered:
            # Create a single generic listener that will dispatch to the appropriate callback
            def generic_listener_wrapper(type_id, data, length, frame_id):
                if length > 0:
                    # Convert the C data pointer to Python bytes
                    data_bytes = bytes(data[:length])
                    # Dispatch to the appropriate callback based on the type_id
                    if type_id in self._callbacks and self._callbacks[type_id] is not None:
                        self._callbacks[type_id](type_id, data_bytes, length, frame_id)
                else:
                    if type_id in self._callbacks and self._callbacks[type_id] is not None:
                        self._callbacks[type_id](type_id, b'', 0, frame_id)
            
            # Create a C function pointer from our wrapper
            self._c_generic_listener = LISTENER_CALLBACK(generic_listener_wrapper)
            
            # Register the generic listener for all used type IDs
            for i in range(self.max_types):
                if i < 20:  # Only register for the first 20 types to avoid exceeding TinyFrame's limit
                    result = self.lib.tf_register_listener(i, self._c_generic_listener)
                    if result:
                        self._generic_listener_registered = True
            
            return self._generic_listener_registered
        
        return True
    
    def send(self, type_id, data):
        """
        Send a frame with the specified type and data
        
        Args:
            type_id (int): Message type ID
            data (bytes): Data to send
                
        Returns:
            bool: True if the message was sent successfully
        """
        if not isinstance(data, bytes):
            data = bytes(data)
        
        data_len = len(data)
        data_array = (c_uint8 * data_len)(*data)
        
        return self.lib.tf_send(type_id, data_array, data_len)
    
    def accept(self, data):
        """
        Process received data
        
        Args:
            data (bytes): Received data
        """
        if not isinstance(data, bytes):
            data = bytes(data)
        
        data_len = len(data)
        data_array = (c_uint8 * data_len)(*data)
        
        self.lib.tf_accept(data_array, data_len)
    
    def _reader_loop(self):
        """Background thread for reading from the serial port"""
        while not self._stop_thread:
            bytes_read = self.lib.tf_read_and_process()
            if bytes_read <= 0:
                # Nothing read, sleep a bit
                time.sleep(0.01)
    
    def start_reader_thread(self):
        """Start a background thread for reading from the serial port"""
        if self._reader_thread is not None and self._reader_thread.is_alive():
            return  # Thread already running
        
        self._stop_thread = False
        self._reader_thread = threading.Thread(target=self._reader_loop)
        self._reader_thread.daemon = True
        self._reader_thread.start()
    
    def _stop_reader_thread(self):
        """Stop the background reader thread"""
        if self._reader_thread is not None and self._reader_thread.is_alive():
            self._stop_thread = True
            self._reader_thread.join(timeout=1.0)
            self._reader_thread = None
    
    def cleanup(self):
        """Clean up resources"""
        self._stop_reader_thread()
        if self.port:
            self.close_port()
        self.lib.tf_cleanup()
        self._callbacks.clear()
        self._c_callbacks.clear()
    
    def __del__(self):
        """Destructor to ensure resources are cleaned up"""
        self.cleanup()


# Example usage
if __name__ == "__main__":
    def message_callback(type_id, data, length, frame_id):
        print(f"Received message type {type_id}, frame ID {frame_id}, length {length}")
        print(f"Data: {data.hex()}")
    
    try:
        # Create TinyFrame instance
        tf = TinyFrame(max_types=256)
        
        # Find and open a port
        if not tf.open_port(baud_rate=115200):
            print("Failed to open port")
            sys.exit(1)
        
        # Register listeners
        tf.register_listener(1, message_callback)  # Listen for message type 1
        
        # Start reader thread
        tf.start_reader_thread()
        
        # Main loop
        print("TinyFrame initialized. Press Ctrl+C to exit.")
        while True:
            # Send a test message every 5 seconds
            tf.send(1, b'Hello, TinyFrame!')
            time.sleep(5)
    
    except KeyboardInterrupt:
        print("\nExiting...")
    finally:
        if 'tf' in locals():
            tf.cleanup()