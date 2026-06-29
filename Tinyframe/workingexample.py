#!/usr/bin/env python3
"""
TinyFrame Example - Handles updated motor status structure and heartbeat
"""

import sys
import time
import logging
import struct
from tinyframe import TinyFrame

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TinyFrameExample")

# Define message types
MSG_TYPE_MOTOR = 1   # Motor status structure
MSG_TYPE_HEARTBEAT = 5  # Heartbeat

# Structure formats
MOTOR_STATUS_FORMAT = "<iib"  # panData (int32), tiltData (int32), subIdx (int8)
HEARTBEAT_FORMAT = "<b"     # Heartbeat value (1 byte char/int8)

# Flag to control sending (set to False to disable sending)
SEND_ENABLED = True

# Velocity increment after each iteration
VELOCITY_INCREMENT = 2000

# Subindex values to cycle through
SUB_IDX_VALUES = [1, 2, 4, 8, 16, 32, 64, 128]

# Callback function for motor status messages
def handle_motor_message(type_id, data, length, frame_id):
    """Handle motor status structures"""
    logger.info(f"Received motor status message, frame ID {frame_id}, length {length}")
    
    # Print raw data for debugging
    logger.info(f"Raw data (hex): {data.hex()}")
    
    # Expected length for MotorStatus structure
    expected_status_len = struct.calcsize(MOTOR_STATUS_FORMAT)
    
    logger.info(f"Expected MotorStatus length: {expected_status_len} bytes, received: {length} bytes")
    
    # Try to decode as MotorStatus
    if length >= struct.calcsize(MOTOR_STATUS_FORMAT):
        try:
            # Unpack the structure as MotorStatus
            pan_data, tilt_data, sub_idx = struct.unpack(
                MOTOR_STATUS_FORMAT, data[:struct.calcsize(MOTOR_STATUS_FORMAT)]
            )
            
            # Print structure details
            logger.info("┌─────── MOTOR STATUS ───────┐")
            logger.info(f"│ Pan Data:  {pan_data}")
            logger.info(f"│ Tilt Data: {tilt_data}")
            logger.info(f"│ Sub Index: {sub_idx}")
            logger.info("└────────────────────────────┘")
            return
        except Exception as e:
            logger.debug(f"Failed to decode as MotorStatus: {e}")
    
    # Try to decode as a partial structure if full decode failed
    if length >= 4:
        try:
            (first_field,) = struct.unpack("<i", data[:4])
            logger.info("┌─────── PARTIAL STATUS ───────┐")
            logger.info(f"│ First Field: {first_field}")
            logger.info("│ (Only received first 4 bytes)")
            logger.info("└───────────────────────────────┘")
            return
        except Exception as e:
            logger.debug(f"Failed to decode as partial status: {e}")
    
    # If we get here, all decoding attempts failed
    logger.warning("Could not decode structure with any known format")

# Callback function for heartbeat messages
def handle_heartbeat(type_id, data, length, frame_id):
    """Handle heartbeat messages"""
    logger.info(f"Received heartbeat message, frame ID {frame_id}, length {length}")
    
    # Print raw data for debugging
    logger.info(f"Raw data (hex): {data.hex()}")
    
    # Try different approaches to decode the heartbeat
    
    # 1. First try: if it's a single byte value (like 0x01, 0x02, etc.)
    if length == 1:
        try:
            # Direct byte value
            heartbeat_value = data[0]
            
            # Print structure details
            logger.info("┌─────── HEARTBEAT ───────┐")
            logger.info(f"│ Raw Value: {heartbeat_value}")
            
            # If it's an ASCII digit (0x30-0x39), convert to number
            if 48 <= heartbeat_value <= 57:  # ASCII '0' to '9'
                digit_value = heartbeat_value - 48  # Convert ASCII to digit
                logger.info(f"│ ASCII Value: '{chr(heartbeat_value)}' (Digit: {digit_value})")
            
            logger.info("└─────────────────────────┘")
            return
        except Exception as e:
            logger.debug(f"Failed to decode 1-byte heartbeat: {e}")
    
    # 2. Second try: decode as standard format
    if length >= struct.calcsize(HEARTBEAT_FORMAT):
        try:
            # Unpack the structure as Heartbeat
            (heartbeat_value,) = struct.unpack(
                HEARTBEAT_FORMAT, data[:struct.calcsize(HEARTBEAT_FORMAT)]
            )
            
            # Print structure details
            logger.info("┌─────── HEARTBEAT ───────┐")
            logger.info(f"│ Value: {heartbeat_value}")
            logger.info("└─────────────────────────┘")
            return
        except Exception as e:
            logger.debug(f"Failed to decode as Heartbeat: {e}")
    
    # If we get here, decoding failed
    logger.warning("Could not decode heartbeat")

def main():
    """Main application entry point"""
    port = None  # Set your port here if needed, e.g., '/dev/ttyUSB0'
    baud_rate = 115200
    
    try:
        # Create TinyFrame instance
        logger.info("Initializing TinyFrame...")
        tf = TinyFrame(max_types=256)
        
        # Find and open a port
        if port:
            logger.info(f"Opening specified port: {port}")
            success = tf.open_port(port=port, baud_rate=baud_rate)
        else:
            logger.info("Searching for a suitable port...")
            success = tf.open_port(baud_rate=baud_rate)
        
        if not success:
            logger.error("Failed to open port")
            return 1
        
        # Register message handlers
        logger.info("Registering message handlers...")
        tf.register_listener(MSG_TYPE_MOTOR, handle_motor_message)
        tf.register_listener(MSG_TYPE_HEARTBEAT, handle_heartbeat)
        
        # Start reader thread
        logger.info("Starting reader thread...")
        tf.start_reader_thread()
        
        # Main loop
        logger.info("TinyFrame initialized. Press Ctrl+C to exit.")
        counter = 0
        
        # Initialize velocities
        base_pan_vel = 8000
        heartbeat_counter = 1
        
        while True:
            if SEND_ENABLED:
                # Calculate velocity with increment
                # pan_data = base_pan_vel + (counter * VELOCITY_INCREMENT)
                # tilt_data = base_pan_vel + (counter * VELOCITY_INCREMENT) // 2

                pan_data = base_pan_vel
                tilt_data = base_pan_vel #+ (counter * VELOCITY_INCREMENT) // 2

                
                # Fixed subIdx value of 1
                sub_idx = 1
                
                # Pack the motor status structure
                status_data = struct.pack(
                    MOTOR_STATUS_FORMAT,
                    pan_data, tilt_data, sub_idx
                )
                
                # Print structure details before sending
                logger.info("┌─────── SENDING MOTOR STATUS ───────┐")
                logger.info(f"│ Pan Data:  {pan_data}")
                logger.info(f"│ Tilt Data: {tilt_data}")
                logger.info(f"│ Sub Index: {sub_idx}")
                logger.info(f"│ Total bytes: {len(status_data)}")
                logger.info("└───────────────────────────────────┘")
                
                # Send the status
                if tf.send(MSG_TYPE_MOTOR, status_data):
                    logger.debug("Motor status sent successfully")
                else:
                    logger.warning("Failed to send motor status")
                
                counter += 1
            
            time.sleep(2)
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Error: {e}")
        return 1
    finally:
        logger.info("Cleaning up...")
        if 'tf' in locals():
            tf.cleanup()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())