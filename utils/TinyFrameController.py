#!/usr/bin/env python3
"""
TinyFrameGunController - A replacement for ModbusGunController using TinyFrame protocol

This controller communicates with an ESP32 that controls pan/tilt motors and trigger systems
for a Remote Controlled Weapon System (RCWS) using the TinyFrame protocol.
"""

import struct
import time
import threading
import logging
import os
import sys

if __name__ == '__main__':
    # When running the file directly
    import tinyframe
    TinyFrame = tinyframe.TinyFrame
else:
    # When imported from another module
    from .tinyframe import TinyFrame

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("TinyFrameGunController")

# Define message types to match ESP32 firmware
MSG_TYPE_MOTOR_STATUS = 1    # For motor position/status updates (send and receive)
MSG_TYPE_MOTOR_CONFIG = 2    # For motor configuration
MSG_TYPE_MOTOR_DIAGNOSTICS = 3  # For motor diagnostics
MSG_TYPE_MISC_CONTROL = 4    # For trigger, track, stabilization control
MSG_TYPE_HEARTBEAT = 5       # For heartbeat monitoring
MSG_TYPE_ACK = 6           # For acknowledgment messages

# SubIndex values for Type 1 (MotorStatus_t)
SUBIDX_POSITION = 1         # Position mode
SUBIDX_CSVELOCITY = 2       # Cyclic Synchronous Velocity mode
SUBIDX_PROFILE_VEL = 4      # Profile velocity mode
SUBIDX_SET_PROFILE_VEL = 8  # Setting Profile velocity
SUBIDX_KP = 16
SUBIDX_KI = 32
SUBIDX_KD = 64
SUBIDX_RANGE = 126

# SubIndex values for Type 2 (MotorConfig_t)
SUBIDX_READ_PAN_CONFIG = 1
SUBIDX_READ_TILT_CONFIG = 2
SUBIDX_WRITE_PAN_MOTION = 4
SUBIDX_WRITE_TILT_MOTION = 8
SUBIDX_WRITE_PAN_LIMITS = 16
SUBIDX_WRITE_TILT_LIMITS = 32

# SubIndex values for Type 3 (MotorDiagnostics_t)
SUBIDX_READ_DIAGNOSTICS = 1
MSG_TYPE_INCLINOMETER = 7

# SubIndex values for Type 4 (Misc_t)
SUBIDX_TRIGGER = 1
SUBIDX_TRACK = 2
SUBIDX_STAB = 4
SUBIDX_FIRING_RATE = 8  # Updated for firing rate
SUBIDX_ROUNDS = 16      # Shifted due to new field
SUBIDX_BRAKE = 32       # Shifted due to new field
SUBIDX_LOGIN = 64       # Shifted due to new field
SUBIDX_CANLINE = 128    # New field for CAN line control

class TinyFrameGunController:
    """
    TinyFrame implementation of gun controller for RCWS
    
    This class replaces the ModbusGunController with a TinyFrame-based implementation
    for communication with the ESP32 controller that drives the RCWS motors.
    """
    def __init__(self, function=None, function_error=None, parent=None, pan_params=None, tilt_params=None, config_screen=None, logout_function=None, inclinometer_callback=None):
        """
        Initialize the gun controller
        
        Args:
            function: Callback function for position updates (pan, tilt)
            function_error: Callback function for errors (error_msg)
            parent: Parent object
            pan_params: Pan motor parameters object
            tilt_params: Tilt motor parameters object
            config_screen: Configuration screen object
            logout_function: Function to call for logout
        """
        self.position_callback = function
        self.error_callback = function_error
        self.inclinometer_callback = inclinometer_callback
        self.parent = parent
        self.pan_params = pan_params
        self.tilt_params = tilt_params
        self.config_screen = config_screen
        self.logout_function = logout_function

        self.pan_error = 0.0
        self.tilt_error = 0.0
        self.profile_speed = {
            'pan': 0,
            'tilt': 0,
            'timestamp': 0
        }
        
        # Acknowledgment tracking
        self.ack_received = False
        self.ack_event = threading.Event()
        self.last_command_id = 0  # To identify which command got acknowledged
        
        # Track current diagnostic request type (1=PAN, 2=TILT)
        self.diagnostic_request_type = 0
        
        # Global storage for received values
        self.motor_status = {
            'pan': 0,
            'tilt': 0,
            'timestamp': 0
        }
        
        self.motor_config = {
            'pan': {
                'profileSpeed': 0,
                'profileAcceleration': 0,
                'profileDeceleration': 0,
                'maxSpeed': 0,
                'maxPositionError': 0,
                'maxSpeedError': 0,
                'maxPositionLimit': 0,
                'minPositionLimit': 0,
                'arc': 0  # Changed from boolean to uint8_t
            },
            'tilt': {
                'profileSpeed': 0,
                'profileAcceleration': 0,
                'profileDeceleration': 0,
                'maxSpeed': 0,
                'maxPositionError': 0,
                'maxSpeedError': 0,
                'maxPositionLimit': 0,
                'minPositionLimit': 0,
                'arc': 0  # Changed from boolean to uint8_t
            }
        }
        
        self.motor_diagnostics = {
            'pan': {
                'actualMotorCurrrent': 0,
                'DCBusVoltage': 0,
                'continuousCurrent': 0,
                'peakCurrent': 0,
                'peakCurrentDuration': 0,
                'PositionLoopGain': 0,
                'SpeedLoopGain': 0,
                'SpeedLoopIntegral': 0,
                'ErrorCode': 0,
                'maxMotorCurrent': 0,
                'StruckSpeed': 0,
                'StruckCurrent': 0,
                'StruckTime': 0
            },
            'tilt': {
                'actualMotorCurrrent': 0,
                'DCBusVoltage': 0,
                'continuousCurrent': 0,
                'peakCurrent': 0,
                'peakCurrentDuration': 0,
                'PositionLoopGain': 0,
                'SpeedLoopGain': 0,
                'SpeedLoopIntegral': 0,
                'ErrorCode': 0,
                'maxMotorCurrent': 0,
                'StruckSpeed': 0,
                'StruckCurrent': 0,
                'StruckTime': 0
            }
        }
        
        # Updated storage structure for Misc_t with new canlineopen field
        self.misc_control = {
            'trigger': 0,
            'track': 0,
            'stab': 0,
            'firingRate': 550,    # Firing rate field
            'noOfRounds': 0,
            'motorBrake': 0,
            'login': 0,         # Login field
            'canlineopen': 0,   # New canlineopen field
            'timestamp': 0
        }

        self.inclinometer_data = {
            'x': 0.0,
            'y': 0.0,
            'z': 0.0,
            'timestamp': 0
        }
        
        self.heartbeat = {
            'value': 0,
            'timestamp': 0,
            'active': False
        }
        
        # Initialize state variables
        self.last_move_time = None
        self.flag = None
        self.zero = None
        self.brake_time = time.time()
        self.connected = False
        
        # Initialize TinyFrame
        try:
            self.tf = TinyFrame(max_types=256)
            logger.info("TinyFrame initialized")
        except Exception as e:
            self._handle_error(f"Failed to initialize TinyFrame: {str(e)}")
            return
        
        # Register message handlers
        try:
            self.tf.register_listener(MSG_TYPE_MOTOR_STATUS, self._handle_motor_status)
            self.tf.register_listener(MSG_TYPE_MOTOR_CONFIG, self._handle_motor_config)
            self.tf.register_listener(MSG_TYPE_MOTOR_DIAGNOSTICS, self._handle_motor_diagnostics)
            self.tf.register_listener(MSG_TYPE_MISC_CONTROL, self._handle_misc_control)
            self.tf.register_listener(MSG_TYPE_HEARTBEAT, self._handle_heartbeat)
            self.tf.register_listener(MSG_TYPE_ACK, self._handle_ack)
            self.tf.register_listener(MSG_TYPE_INCLINOMETER, self._handle_inclinometer)
            logger.info("Registered message handlers")
        except Exception as e:
            self._handle_error(f"Failed to register message handlers: {str(e)}")
            return
        
        # Find and open serial port
        try:
            if self.tf.open_port(baud_rate=115200):
                self.connected = True
                logger.info("Serial port opened successfully")
            else:
                self._handle_error("Failed to open serial port")
                return
        except Exception as e:
            self._handle_error(f"Error opening serial port: {str(e)}")
            return
            
        # Start reader thread
        try:
            self.tf.start_reader_thread()
            logger.info("Reader thread started")
        except Exception as e:
            self._handle_error(f"Failed to start reader thread: {str(e)}")
            return
        
        if self.connected:
            login_result = self.login_and_configure()
            if login_result:
                logger.info("login_and_configure command sent successfully during initialization")
            else:
                logger.warning("login_and_configure to send login command during initialization")
        self.num_rounds = None
    def _handle_error(self, error_msg):
        """
        Handle errors by logging and calling the error callback if available
        
        Args:
            error_msg: Error message
        """
        logger.error(error_msg)
        if self.error_callback:
            self.error_callback(error_msg)
    
    def _handle_inclinometer(self, type_id, data, length, frame_id):
        """
        Handle inclinometer data messages from the device
        
        Args:
            type_id: Message type ID
            data: Message data
            length: Message length
            frame_id: Message frame ID
        """
        try:
            if length < 12:  # Size of Incl_t structure (3 floats = 12 bytes)
                logger.warning(f"Received inclinometer data with insufficient data length: {length}")
                return
                
            # Unpack the structure: float x, float y, float z
            x, y, z = struct.unpack('<fff', data[:12])
            
            logger.debug(f"Inclinometer data: X={x}, Y={y}, Z={z}")
            
            # Store values globally
            self.inclinometer_data['x'] = x
            self.inclinometer_data['y'] = y
            self.inclinometer_data['z'] = z
            self.inclinometer_data['timestamp'] = time.time()
            
            # Call callback if defined
            if self.inclinometer_callback:
                self.inclinometer_callback(x, y, z)
                
        except Exception as e:
            self._handle_error(f"Error processing inclinometer data: {str(e)}")

    # def _handle_motor_status(self, type_id, data, length, frame_id):
    #     """
    #     Handle motor status messages from the device with enhanced diagnostics integration

    #     Args:
    #         type_id: Message type ID
    #         data: Message data
    #         length: Message length
    #         frame_id: Message frame ID
    #     """
    #     try:
    #         if length < 9:  # Minimum size for the structure (8 bytes for two int32_t plus 1 byte for subIdx)
    #             logger.warning(f"Received motor status with insufficient data length: {length}")
    #             return
                
    #         # Unpack the structure: int32_t panData, int32_t tiltData, int8_t subIdx
    #         pan_data, tilt_data, sub_idx = struct.unpack('<iib', data[:9])
            
    #         logger.debug(f"Motor status: Pan={pan_data}, Tilt={tilt_data}, SubIdx={sub_idx}")
    #         # logger.info(f"Motor status: Pan={pan_data}, Tilt={tilt_data}")
    #         # Store values globally
    #         self.motor_status['pan'] = pan_data
    #         self.motor_status['tilt'] = tilt_data
    #         self.motor_status['timestamp'] = time.time()

    #         # Convert position to angle
    #         pan_angle = self._position_to_angle(pan_data)
    #         tilt_angle = self._position_to_angle(-tilt_data)
            
    #         # Update the UI via callback if this is a position update
    #         if self.position_callback and sub_idx == 0:
    #             self.position_callback(pan_angle, tilt_angle)
            
    #         # Update parameters if needed - Enhanced to update position and speed
    #         if self.pan_params:
    #             self.pan_params.update_param("Actual Position", pan_data)
                
    #             # Calculate and update speed if we have previous position data
    #             if hasattr(self, '_prev_pan_position') and hasattr(self, '_prev_pan_timestamp'):
    #                 time_diff = time.time() - self._prev_pan_timestamp
    #                 if time_diff > 0:
    #                     position_diff = pan_data - self._prev_pan_position
    #                     speed = position_diff / time_diff  # counts per second
    #                     self.pan_params.update_param("Actual Speed", int(speed))
                
    #             # Store current values for next speed calculation
    #             self._prev_pan_position = pan_data
    #             self._prev_pan_timestamp = time.time()
                
    #             # Apply updates
    #             self.pan_params.apply()
                
    #         if self.tilt_params:
    #             self.tilt_params.update_param("Actual Position", tilt_data)
                
    #             # Calculate and update speed if we have previous position data
    #             if hasattr(self, '_prev_tilt_position') and hasattr(self, '_prev_tilt_timestamp'):
    #                 time_diff = time.time() - self._prev_tilt_timestamp
    #                 if time_diff > 0:
    #                     position_diff = tilt_data - self._prev_tilt_position
    #                     speed = position_diff / time_diff  # counts per second
    #                     self.tilt_params.update_param("Actual Speed", int(speed))
                
    #             # Store current values for next speed calculation
    #             self._prev_tilt_position = tilt_data
    #             self._prev_tilt_timestamp = time.time()
                
    #             # Apply updates
    #             self.tilt_params.apply()
                
    #     except Exception as e:
    #         self._handle_error(f"Error processing motor status: {str(e)}")
    def _handle_motor_status(self, type_id, data, length, frame_id):
        """
        Handle motor status messages from the device with profile speed handling
        """
        try:
            if length < 9:  # Minimum size for the structure
                logger.warning(f"Received motor status with insufficient data length: {length}")
                return
             # Unpack the structure: int32_t panData, int32_t tiltData, int8_t subIdx
            pan_data, tilt_data, sub_idx = struct.unpack('<iib', data[:9])
            # print(f"[INFO] Sub Index: {sub_idx}")
            if sub_idx == 0:
                logger.debug(f"Motor status: Pan={pan_data}, Tilt={tilt_data}, SubIdx={sub_idx}")
                # Store values globally
                self.motor_status['pan'] = pan_data
                self.motor_status['tilt'] = tilt_data
                self.motor_status['timestamp'] = time.time()

                # Convert position to angle
                pan_angle = self._position_to_angle(pan_data)
                tilt_angle = self._position_to_angle(-tilt_data)
                # Update the UI via callback
                if self.position_callback:
                    self.position_callback(pan_angle, tilt_angle)
                # Update parameters if needed
                if self.pan_params:
                    self.pan_params.update_param("Actual Position", pan_data)
                    if hasattr(self, '_prev_pan_position') and hasattr(self, '_prev_pan_timestamp'):
                        time_diff = time.time() - self._prev_pan_timestamp
                        if time_diff > 0:
                            position_diff = pan_data - self._prev_pan_position
                            speed = position_diff / time_diff
                            self.pan_params.update_param("Actual Speed", int(speed))
                    self._prev_pan_position = pan_data
                    self._prev_pan_timestamp = time.time()
                    self.pan_params.apply()
                if self.tilt_params:
                    self.tilt_params.update_param("Actual Position", tilt_data)
                    if hasattr(self, '_prev_tilt_position') and hasattr(self, '_prev_tilt_timestamp'):
                        time_diff = time.time() - self._prev_tilt_timestamp
                        if time_diff > 0:
                            position_diff = tilt_data - self._prev_tilt_position
                            speed = position_diff / time_diff
                            self.tilt_params.update_param("Actual Speed", int(speed))
                    self._prev_tilt_position = tilt_data
                    self._prev_tilt_timestamp = time.time()
                    self.tilt_params.apply()

            # if sub_idx == SUBIDX_GET_PROFILE_VEL:  # Profile speed data
            #     # Store profile speed data
            #     self.profile_speed['pan'] = pan_data
            #     self.profile_speed['tilt'] = tilt_data
            #     self.profile_speed['timestamp'] = time.time()
            #     # print(f"Profile speeds - Pan: {pan_data}, Tilt: {tilt_data}")
            #     # Update parameters if available
            #     if self.pan_params:
            #         self.pan_params.update_param("Actual Speed", pan_data)
            #         self.pan_params.apply()
            #     if self.tilt_params:
            #         self.tilt_params.update_param("Actual Speed", tilt_data)
            #         self.tilt_params.apply()
        except Exception as e:
            self._handle_error(f"Error processing motor status: {str(e)}")
    
    def _handle_motor_config(self, type_id, data, length, frame_id):
        """
        Handle motor configuration messages from the device
        
        Args:
            type_id: Message type ID
            data: Message data
            length: Message length
            frame_id: Message frame ID
        """
        try:
            if length < 35:  # Size of MotorConfig_t structure: 4*6 + 4*2 + 1 + 2 = 35 bytes
                logger.warning(f"Received motor config with insufficient data length: {length}")
                return
                
            # Unpack the structure: All uint32_t except arc (uint8_t) and subIdx (uint16_t)
            unpacked = struct.unpack('<IIIIIIiiBH', data[:35])  # Format matches the 35 bytes we're receiving
            
            # Extract values
            profile_speed = unpacked[0]
            profile_accel = unpacked[1]
            profile_decel = unpacked[2]
            max_speed = unpacked[3]
            max_pos_error = unpacked[4]
            max_speed_error = unpacked[5]
            max_pos_limit = unpacked[6]
            min_pos_limit = unpacked[7]
            arc = unpacked[8]
            sub_idx = unpacked[9]
            
            logger.info(f"Motor config received with subIdx={sub_idx}")
            
            # Handle based on subIndex
            if sub_idx == SUBIDX_READ_PAN_CONFIG:
                # Store pan configuration
                self.motor_config['pan']['profileSpeed'] = profile_speed
                self.motor_config['pan']['profileAcceleration'] = profile_accel
                self.motor_config['pan']['profileDeceleration'] = profile_decel
                self.motor_config['pan']['maxSpeed'] = max_speed
                self.motor_config['pan']['maxPositionError'] = max_pos_error
                self.motor_config['pan']['maxSpeedError'] = max_speed_error
                self.motor_config['pan']['maxPositionLimit'] = max_pos_limit
                self.motor_config['pan']['minPositionLimit'] = min_pos_limit
                self.motor_config['pan']['arc'] = arc
                
                logger.info("Pan motor configuration updated")
                
            elif sub_idx == SUBIDX_READ_TILT_CONFIG:
                # Store tilt configuration
                self.motor_config['tilt']['profileSpeed'] = profile_speed
                self.motor_config['tilt']['profileAcceleration'] = profile_accel
                self.motor_config['tilt']['profileDeceleration'] = profile_decel
                self.motor_config['tilt']['maxSpeed'] = max_speed
                self.motor_config['tilt']['maxPositionError'] = max_pos_error
                self.motor_config['tilt']['maxSpeedError'] = max_speed_error
                self.motor_config['tilt']['maxPositionLimit'] = max_pos_limit
                self.motor_config['tilt']['minPositionLimit'] = min_pos_limit
                self.motor_config['tilt']['arc'] = arc
                
                logger.info("Tilt motor configuration updated")
            
            # No need to handle response for write operations (4, 8, 16, 32)
            
        except Exception as e:
            self._handle_error(f"Error processing motor configuration: {str(e)}")


    def _handle_motor_diagnostics(self, type_id, data, length, frame_id):
        """
        Handle motor diagnostics messages with complete parameter updates for all categories
        
        Args:
            type_id: Message type ID
            data: Message data
            length: Message length
            frame_id: Message frame ID
        """
        try:
            if length < 52:  # ESP32 is sending exactly 52 bytes
                logger.warning(f"Received motor diagnostics with insufficient data length: {length}")
                return
                
            # Log the raw data for debugging
            logger.info(f"Received diagnostic data: length={length}")
                
            # The format is 13 uint32_t fields (13 * 4 = 52 bytes)
            format_string = '<IIIIIIIIIIIII'  # 13 uint32_t fields only (52 bytes total)
            values = struct.unpack(format_string, data[:52])
            
            # Extract values
            actualMotorCurrent = values[0]
            DCBusVoltage = values[1]
            continuousCurrent = values[2]
            peakCurrent = values[3]
            peakCurrentDuration = values[4]
            positionLoopGain = values[5]
            speedLoopGain = values[6]
            speedLoopIntegral = values[7]
            errorCode = values[8]
            maxMotorCurrent = values[9]
            struckSpeed = values[10]
            struckCurrent = values[11]
            struckTime = values[12]
            
            logger.info(f"Current diagnostic request type: {self.diagnostic_request_type}")
            
            # Choose parameter set based on diagnostic request type
            params = None
            if self.diagnostic_request_type == 1:  # PAN
                params = self.pan_params
                diagnostic_data = self.motor_diagnostics['pan']
            elif self.diagnostic_request_type == 2:  # TILT
                params = self.tilt_params
                diagnostic_data = self.motor_diagnostics['tilt']
            else:
                logger.warning(f"Unknown diagnostic request type: {self.diagnostic_request_type}")
                return
                
            # Store in diagnostic data dictionary
            diagnostic_data['actualMotorCurrrent'] = actualMotorCurrent
            diagnostic_data['DCBusVoltage'] = DCBusVoltage
            diagnostic_data['continuousCurrent'] = continuousCurrent
            diagnostic_data['peakCurrent'] = peakCurrent
            diagnostic_data['peakCurrentDuration'] = peakCurrentDuration
            diagnostic_data['PositionLoopGain'] = positionLoopGain
            diagnostic_data['SpeedLoopGain'] = speedLoopGain
            diagnostic_data['SpeedLoopIntegral'] = speedLoopIntegral
            diagnostic_data['ErrorCode'] = errorCode
            diagnostic_data['maxMotorCurrent'] = maxMotorCurrent
            diagnostic_data['StruckSpeed'] = struckSpeed
            diagnostic_data['StruckCurrent'] = struckCurrent
            diagnostic_data['StruckTime'] = struckTime
            
            # Only update UI if we have valid parameter object
            if params:
                # CATEGORY: Error And State Codes
                params.update_param("Error Codes", errorCode)
                # For Operation State - A simple numeric value for now
                params.update_param("Operation State", 1 if errorCode == 0 else 0)
                # For State of achieving the target - A simple numeric value for now
                params.update_param("State of achieving the target", 1 if errorCode == 0 else 0)
                
                # CATEGORY: Electrical Parameters
                params.update_param("Actual Motor Current", actualMotorCurrent)
                params.update_param("DC Bus Voltage", DCBusVoltage)
                params.update_param("Continuous Current", continuousCurrent)
                params.update_param("Peak Current", peakCurrent)
                params.update_param("Peak Current Duration", peakCurrentDuration)
                params.update_param("MAX Motor Current", maxMotorCurrent)
                
                # CATEGORY: Struck Conditions - these need special attention
                params.update_param("Struck Current", struckCurrent)
                params.update_param("Struck Speed", struckSpeed)
                params.update_param("Struck Time", struckTime)
                
                # CATEGORY: Control And Feedback Gains - these need special attention
                params.update_param("Position Loop Gain", positionLoopGain)
                params.update_param("Speed Loop Gain", speedLoopGain)
                params.update_param("Speed Loop Integral", speedLoopIntegral)
                
                # Get motor configuration to update Position And Speed Limits
                config = None
                if self.diagnostic_request_type == 1 and hasattr(self, 'motor_config') and 'pan' in self.motor_config:
                    config = self.motor_config['pan']
                elif self.diagnostic_request_type == 2 and hasattr(self, 'motor_config') and 'tilt' in self.motor_config:
                    config = self.motor_config['tilt']
                    
                if config:
                    # CATEGORY: Position And Speed Limits
                    params.update_param("Position Limit (MIN)", config.get('minPositionLimit', 0))
                    params.update_param("Position Limit (MAX)", config.get('maxPositionLimit', 0))
                    params.update_param("MAX Speed", config.get('maxSpeed', 0))
                    params.update_param("Permissible MAX Position Error", config.get('maxPositionError', 0))
                    params.update_param("Permissible MAX Speed Error", config.get('maxSpeedError', 0))
                    
                    # CATEGORY: Target And Profile Parameters
                    params.update_param("Profile Acceleration", config.get('profileAcceleration', 0))
                    params.update_param("Profile Deceleration", config.get('profileDeceleration', 0))
                    params.update_param("Profile Speed", config.get('profileSpeed', 0))
                
                # Apply all updates to refresh the UI
                params.apply()
                logger.info(f"Updated all diagnostic parameters for {'PAN' if self.diagnostic_request_type == 1 else 'TILT'}")
                
        except Exception as e:
            self._handle_error(f"Error processing motor diagnostics: {str(e)}")
            logger.error(f"Exception details: {str(e)}", exc_info=True)
    
    # Updated handler for Misc_t structure with canlineopen field
    def _handle_misc_control(self, type_id, data, length, frame_id):
        """
        Handle miscellaneous control messages from the device
        
        Args:
            type_id: Message type ID
            data: Message data
            length: Message length
            frame_id: Message frame ID
        """
        try:
            if length < 12:  # Size of updated Misc_t structure (3 uint8_t fields + 1 uint32_t + 4 uint8_t fields + 1 uint8_t subIdx)
                logger.warning(f"Received misc control with insufficient data length: {length}")
                return
                
            # Unpack the structure: uint8_t trigger, uint8_t track, uint8_t stab, uint32_t firingRate, 
            # uint8_t noOfRounds, uint8_t motorBrake, uint8_t login, uint8_t canlineopen, uint8_t subIdx
            trigger, track, stab, firing_rate, no_of_rounds, motor_brake, login, canlineopen, sub_idx = struct.unpack('<BBBIBBBBB', data[:12])
            
            logger.debug(f"Misc control received: trigger={trigger}, track={track}, stab={stab}, " + 
                        f"firingRate={firing_rate}, noOfRounds={no_of_rounds}, motorBrake={motor_brake}, " +
                        f"login={login}, canlineopen={canlineopen}, subIdx={sub_idx}")
            
            # Store values globally
            self.misc_control['trigger'] = trigger
            self.misc_control['track'] = track
            self.misc_control['stab'] = stab
            self.misc_control['firingRate'] = firing_rate
            self.misc_control['noOfRounds'] = no_of_rounds
            self.misc_control['motorBrake'] = motor_brake
            self.misc_control['login'] = login
            self.misc_control['canlineopen'] = canlineopen
            self.misc_control['timestamp'] = time.time()
            
            # Handle specific subIdx values if needed
            
        except Exception as e:
            self._handle_error(f"Error processing misc control: {str(e)}")
            # Add more debug information
            if data and length > 0:
                logger.error(f"Misc control data (hex): {data[:min(length, 16)].hex()}")
    
    def _handle_heartbeat(self, type_id, data, length, frame_id):
        """
        Handle heartbeat messages from the device
        
        Args:
            type_id: Message type ID
            data: Message data
            length: Message length
            frame_id: Message frame ID
        """
        try:
            if length < 1:
                logger.warning("Received heartbeat with insufficient data length")
                return
            
            # Try to decode ASCII heartbeat
            try:
                heartbeat_value = int(data.decode('ascii').strip())
            except:
                heartbeat_value = data[0]  # Fallback to first byte as integer
            
            logger.debug(f"Heartbeat received: {heartbeat_value}")
            
            # Update heartbeat status
            self.heartbeat['value'] = heartbeat_value
            self.heartbeat['timestamp'] = time.time()
            self.heartbeat['active'] = True
            
        except Exception as e:
            self._handle_error(f"Error processing heartbeat: {str(e)}")
    
    def _handle_ack(self, type_id, data, length, frame_id):
        """
        Handle acknowledgment messages from the device
        
        Args:
            type_id: Message type ID
            data: Message data
            length: Message length
            frame_id: Message frame ID
        """
        logger.info(f"ACK raw data received: {data.hex()}, length: {length}, frame_id: {frame_id}")
        try:
            if length < 1:
                logger.warning("Received ACK with insufficient data length")
                return
            
            # Try to decode ASCII ACK
            try:
                ack_str = data.decode('ascii', errors='ignore').strip()
                logger.info(f"ACK received: {ack_str}")
                
                # Simple ACK handling - no command ID parsing needed
                if "ACK" in ack_str:
                    # Set the ACK flag and signal the event
                    self.ack_received = True
                    self.ack_event.set()
                else:
                    logger.warning(f"Received unexpected response: {ack_str}")
                    
            except Exception as e:
                logger.error(f"Error decoding ACK message: {e}")
                    
        except Exception as e:
            self._handle_error(f"Error processing ACK: {str(e)}")
    
    def _position_to_angle(self, position):
        """
        Convert position value to angle with consistent direction handling
        
        Args:
            position: Position value from motor encoder
            
        Returns:
            float: Angle in degrees (positive = clockwise, negative = counter-clockwise)
        """
        try:
            # Convert position to raw angle using the conversion factor
            raw_angle = position * 360 / (2**19)
            
            # Invert the sign to make clockwise positive and counter-clockwise negative
            # This gives us a consistent convention regardless of how the encoder reports
            normalized_angle = -raw_angle
            
            # Normalize to -180 to +180 range for consistent display
            normalized_angle = normalized_angle % 360
            if normalized_angle > 180:
                normalized_angle -= 360
                
            return normalized_angle
        except Exception as e:
            self._handle_error(f"Error converting position to angle: {str(e)}")
            return 0

    def format_angle_for_display(self, angle):
        """
        Format an angle for display with consistent -180 to +180 range
        
        Args:
            angle: Angle in degrees
            
        Returns:
            str: Formatted angle string for display
        """
        # Normalize to -180 to +180 range
        angle = angle % 360
        if angle > 180:
            angle -= 360
            
        # Format with sign and precision
        return "{:+7.2f}".format(angle)
    
    def _send_with_ack(self, msg_type, data, max_retries=2, timeout=0.5):
        """
        Send a command and wait for acknowledgment with optimized timeouts
        
        Args:
            msg_type: Message type
            data: Message data
            max_retries: Maximum number of retry attempts
            timeout: Timeout in seconds
            
        Returns:
            bool: True if ACK received, False if not
        """
        # No longer skipping ACK for velocity commands as requested
        
        for attempt in range(max_retries):
            # Reset ACK flag and event
            self.ack_received = False
            self.ack_event.clear()
            
            # Send the command
            if not self.tf.send(msg_type, data):
                logger.warning(f"Failed to send command (attempt {attempt+1}/{max_retries})")
                continue
                
            # Wait for ACK
            if self.ack_event.wait(timeout):
                if self.ack_received:
                    logger.debug(f"ACK received for command (attempt {attempt+1})")
                    return True
                
            logger.warning(f"No ACK received (attempt {attempt+1}/{max_retries})")
            
        # All retries failed
        logger.error(f"Failed to get ACK after {max_retries} attempts")
        return False
    
    def misc_control_command_no_ack(self, command_type, value=1):
        """
        General purpose function for miscellaneous control commands without waiting for ACK
        Used for time-sensitive commands like trigger
        
        Args:
            command_type: Type of command (SUBIDX_TRIGGER, SUBIDX_TRACK, SUBIDX_STAB, etc.)
            value: Value to set (0 or 1 typically, or an integer for firing rate)
            
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error(f"Cannot send misc command: Not connected")
            return False
            
        try:
            # Create misc command structure
            # Format: uint8_t trigger, uint8_t track, uint8_t stab, uint32_t firingRate, 
            # uint8_t noOfRounds, uint8_t motorBrake, uint8_t login, uint8_t canlineopen, uint8_t subIdx
            trigger = value if command_type == SUBIDX_TRIGGER else self.misc_control['trigger']
            track = value if command_type == SUBIDX_TRACK else self.misc_control['track']
            stab = value if command_type == SUBIDX_STAB else self.misc_control['stab']
            firing_rate = value if command_type == SUBIDX_FIRING_RATE else self.misc_control['firingRate']
            rounds = value if command_type == SUBIDX_ROUNDS else self.misc_control['noOfRounds']
            if self.num_rounds is not None:
                rounds = self.num_rounds
            brake = value if command_type == SUBIDX_BRAKE else self.misc_control['motorBrake']
            login = value if command_type == SUBIDX_LOGIN else self.misc_control['login']
            canlineopen = value if command_type == SUBIDX_CANLINE else self.misc_control['canlineopen']
            
            misc_data = struct.pack('<BBBIBBBBB',
                trigger,        # Trigger
                track,          # Track
                stab,           # Stab
                firing_rate,    # Firing rate
                rounds,         # Number of rounds
                brake,          # Motor brake
                login,          # Login
                canlineopen,    # CAN line open/closed
                command_type    # SubIdx for the operation
            )
            
            # Log the command being sent
            logger.debug(f"Sending misc command (no ACK): type={command_type}, value={value}")
            
            # Send command directly without waiting for ACK
            result = self.tf.send(MSG_TYPE_MISC_CONTROL, misc_data)
            
            # Update internal state if command was sent successfully
            if result and command_type == SUBIDX_TRIGGER:
                # Update trigger state
                self.misc_control['trigger'] = value
                self.flag = not value  # Toggle flag for trigger state
                
            return result
        except Exception as e:
            self._handle_error(f"Error sending misc command (no ACK): {str(e)}")
            return False


    def request_inclinometer_data(self, value=1):
        """
        Request inclinometer data from the device
        
        Args:
            value: Value to send as the request (default: 1)
            
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot request inclinometer data: Not connected")
            return False
            
        try:
            logger.info("Requesting inclinometer data")
            
            # Create a simple data packet with the value
            request_data = struct.pack('<B', value)
            
            logger.info(f"Sending inclinometer data request with value={value}")
            
            # Send the request with acknowledgment
            return self._send_with_ack(MSG_TYPE_INCLINOMETER, request_data)
        except Exception as e:
            self._handle_error(f"Error requesting inclinometer data: {str(e)}")
            return False
        
    def normalize_angle(self, angle):
        """
        Normalize angle to be between -180 and 180 degrees
        
        Args:
            angle: Angle in degrees
            
        Returns:
            float: Normalized angle between -180 and 180
        """
        angle = angle % 360
        if angle > 180:
            angle -= 360
        return angle

    def calculate_shortest_path(self, current_angle, target_angle):
        """
        Calculate the shortest path between two angles
        
        Args:
            current_angle: Current angle in degrees
            target_angle: Target angle in degrees
            
        Returns:
            float: Target angle adjusted for shortest path
        """
        # Normalize angles to be between -180 and 180
        current = self.normalize_angle(current_angle)
        target = self.normalize_angle(target_angle)
        
        # Calculate angle difference
        diff = target - current
        
        # Adjust for shortest path
        if diff > 180:
            diff -= 360
        elif diff < -180:
            diff += 360
        
        # Return the new target that represents the shortest path
        new_target = current + diff
        logger.info(f"Shortest path: Current={current}°, Target={target}°, Adjusted Target={new_target}°, Diff={diff}°")
        return new_target
    
    def send_range(self, rng):
        if not self.connected:
            self._handle_error("Cannot send range: Not connected")
            return False
        
        try:
            cmd_data = struct.pack('iib', 
                int(rng),
                0,
                SUBIDX_RANGE                      
            )
            
            logger.info(f"Sending range data: {rng}m to ESP32")
            return self.tf.send(MSG_TYPE_MOTOR_STATUS, cmd_data)
            
        except Exception as e:  # Added Exception as e
            self._handle_error(f"Error sending range data: {str(e)}")
            return False

    def send_PID_values(self, p, i, d):
        """
        Send error data to ESP32 using MotorStatus_t structure
        Args:
            pan_error: Pan error value (float)
            tilt_error: Tilt error value (float)
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot send error data: Not connected")
            return False
        try:
            # Create command structure
            p = int(p*100)
            i = int(i*100)
            d = int(d*100)
            cmd_data_p = struct.pack('<iib',
                p,            
                i,            
                SUBIDX_KP
            )
            # cmd_data_i = struct.pack('<iib',
            #     i,            
            #     0,            
            #     SUBIDX_KI
            # )
            # cmd_data_d = struct.pack('<iib',
            #     d,            
            #     0,            
            #     SUBIDX_KD
            # )
            # Send command directly without ACK
            return self.tf.send(MSG_TYPE_MOTOR_STATUS, cmd_data_p)
            # success = self.tf.send(MSG_TYPE_MOTOR_STATUS, cmd_data_i)
            # success = self.tf.send(MSG_TYPE_MOTOR_STATUS, cmd_data_d)
            # return True
        except Exception as e:
            self._handle_error(f"Error sending error data: {str(e)}")
            return False
 

    def move(self, pan, tilt, pan_speed=None, tilt_speed=None):
        """
        Move to absolute position with optimal path for multiturn motors
        
        Args:
            pan: Pan angle in degrees
            tilt: Tilt angle in degrees
            pan_speed: Optional pan profile speed in degrees/second
            tilt_speed: Optional tilt profile speed in degrees/second
            
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot move: Not connected")
            return False
        
        if self.misc_control['motorBrake'] == 1:
            logger.debug("Move command ignored: Motor brake is applied")
            return False
            
        if self.brake_time and self.brake_time > (time.time() - 0.5):
            logger.debug("Move command ignored: Brake recently applied")
            return False
            
        try:
            self.last_move_time = time.time()
            
            # Get current encoder positions
            current_pan_position = self.motor_status['pan']
            current_tilt_position = self.motor_status['tilt']
            
            current_pan_angle = self._position_to_angle(current_pan_position)
            current_tilt_angle = self._position_to_angle(-current_tilt_position)  # Note the sign inversion for tilt
            target_pan_angle = self.calculate_shortest_path(current_pan_angle, pan)
            target_tilt_angle = self.calculate_shortest_path(current_tilt_angle, tilt)
            
            # Calculate movement deltas in angles
            pan_diff = target_pan_angle - current_pan_angle
            tilt_diff = target_tilt_angle - current_tilt_angle
            
            # Convert to encoder counts (note the sign inversion due to how _position_to_angle works)
            pan_diff_counts = int(-(pan_diff * (2**19) / 360))
            tilt_diff_counts = int((tilt_diff * (2**19) / 360))  # Removed negative sign for tilt
            
            # Apply deltas to current positions to get target positions
            target_pan_position = current_pan_position + pan_diff_counts
            target_tilt_position = current_tilt_position + tilt_diff_counts
            
            logger.info(f"Current: Pan={current_pan_position}, Tilt={current_tilt_position}")
            logger.info(f"Moving by: Pan={pan_diff}° ({pan_diff_counts} counts), Tilt={tilt_diff}° ({tilt_diff_counts} counts)")
            logger.info(f"Target: Pan={target_pan_position}, Tilt={target_tilt_position}")
            
            # First set profile velocity if speed parameters are provided and different from current
            if pan_speed is not None and tilt_speed is not None:
                # Convert degrees/sec to cnts/sec for comparison
                pan_speed_cnts = int(pan_speed * (2**19) / 360)
                tilt_speed_cnts = int(tilt_speed * (2**19) / 360)
                
                # Only send command if values are different from current by more than the error margin
                error_margin = 200  # counts per second
                current_pan_speed = self.motor_config['pan']['profileSpeed']
                current_tilt_speed = self.motor_config['tilt']['profileSpeed']
                
                pan_diff = abs(current_pan_speed - pan_speed_cnts)
                tilt_diff = abs(current_tilt_speed - tilt_speed_cnts)
                
                if pan_diff > error_margin or tilt_diff > error_margin:
                    logger.info(f"Setting profile velocities before move: Pan={pan_speed}°/s, Tilt={tilt_speed}°/s")
                    
                    if not self.set_profile_velo(pan_speed, tilt_speed):
                        logger.warning("Failed to set profile velocities before move")
                else:
                    logger.debug(f"Skipping profile velocity command - speeds within margin")
            
            # Create command structure for absolute movement
            cmd_data = struct.pack('<iib',
                target_pan_position,  # Pan position
                target_tilt_position,  # Tilt position
                SUBIDX_POSITION  # SubIdx for position mode
            )
            
            # Send movement command with ACK handling
            return self._send_with_ack(MSG_TYPE_MOTOR_STATUS, cmd_data)
        except Exception as e:
            self._handle_error(f"Error sending move command: {str(e)}")
            return False

    def csvmove(self, pan_speed, tilt_speed):
        """
        Move with cyclic synchronous velocity control
        
        Args:
            pan_speed: Pan speed
            tilt_speed: Tilt speed
            
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot move: Not connected")
            return False
            
        if self.brake_time and self.brake_time > (time.time() - 0.2):
            logger.debug("CSV move command ignored: Brake recently applied")
            return False
            
        try:
            # Handle zero velocity commands specially
            if pan_speed == 0 and tilt_speed == 0:
                if self.zero is None or not self.zero:
                    self.zero = True
                elif self.zero:
                    return False
            else:
                self.zero = False
                
            # Limit pan speed
            if pan_speed > 90:
                pan_speed = 90
            if pan_speed < -90:
                pan_speed = -90
                
            # Limit tilt speed
            if tilt_speed > 90:
                tilt_speed = 90
            if tilt_speed < -90:
                tilt_speed = -90
                
            # Convert speeds to the format expected by the motor controller
            scaled_pan_speed = int(pan_speed * (2**19) / 360)
            scaled_tilt_speed = int(tilt_speed * (2**19) / 360)
                
            logger.info(f"Moving with CSV velocity: Pan speed={pan_speed}, Tilt speed={tilt_speed}")
                
            # Create command structure for CSV velocity movement
            # Format: int32_t panData, int32_t tiltData, int8_t subIdx
            cmd_data = struct.pack('<iib',
                scaled_pan_speed,     # Pan velocity (scaled)
                scaled_tilt_speed,    # Tilt velocity (scaled)
                SUBIDX_CSVELOCITY     # SubIdx for CSV velocity mode
            )
            
            # Update last move time
            self.last_move_time = time.time()
            
            # Send CSV velocity command directly without waiting for ACK
            return self.tf.send(MSG_TYPE_MOTOR_STATUS, cmd_data)
            
        except Exception as e:
            self._handle_error(f"Error sending CSV velocity move command: {str(e)}")
            return False
    
    def vmove(self, pan_speed, tilt_speed):
        """
        Move with profile velocity control
        
        Args:
            pan_speed: Pan speed
            tilt_speed: Tilt speed
            
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot move: Not connected")
            return False
            
        if self.misc_control['motorBrake'] == 1:
            logger.debug("Profile velocity move command ignored: Motor brake is applied")
            return False
    
        if self.brake_time and self.brake_time > (time.time() - 0.2):
            logger.debug("Profile velocity move command ignored: Brake recently applied")
            return False
            
        try:
            # Handle zero velocity commands specially
            if pan_speed == 0 and tilt_speed == 0:            
                if self.zero is None or not self.zero:
                    self.zero = True
                elif self.zero:
                    return False
            else:
                self.zero = False
            # Convert speeds to the format expected by the motor controller
            scaled_pan_speed = int(pan_speed * (2**19) / 360)
            scaled_tilt_speed = int(tilt_speed * (2**19) / 360)
                
            logger.info(f"Moving with profile velocity: Pan speed={pan_speed}, Tilt speed={tilt_speed}")
                
            # Create command structure for profile velocity movement
            # Format: int32_t panData, int32_t tiltData, int8_t subIdx
            cmd_data = struct.pack('<iib',
                scaled_pan_speed,     # Pan velocity (scaled)
                scaled_tilt_speed,    # Tilt velocity (scaled)
                SUBIDX_PROFILE_VEL    # SubIdx for profile velocity mode
            )
            
            # Update last move time
            self.last_move_time = time.time()
            
            # Send profile velocity command directly without waiting for ACK
            return self.tf.send(MSG_TYPE_MOTOR_STATUS, cmd_data)
            
        except Exception as e:
            self._handle_error(f"Error sending profile velocity move command: {str(e)}")
            return False
    
    def set_profile_velo(self, pan_velocity, tilt_velocity):
        """
        Set profile velocity for both motors
        
        Args:
            pan_velocity: Pan profile velocity in degrees/second
            tilt_velocity: Tilt profile velocity in degrees/second
            
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot set profile velocity: Not connected")
            return False
            
        try:
            logger.info(f"Setting profile velocity: Pan={pan_velocity}°/s, Tilt={tilt_velocity}°/s")
            
            # Convert from degrees/sec to the internal format (cnts/sec)
            pan_velocity_cnts = int(pan_velocity * (2**19) / 360)
            tilt_velocity_cnts = int(tilt_velocity * (2**19) / 360)
                
            # Create command structure for profile velocity setting
            # Format: int32_t panData, int32_t tiltData, int8_t subIdx
            cmd_data = struct.pack('<iib',
                pan_velocity_cnts,     # Pan profile velocity in cnts/sec
                tilt_velocity_cnts,    # Tilt profile velocity in cnts/sec
                SUBIDX_SET_PROFILE_VEL # SubIdx for setting profile velocity
            )
            
            # Send profile velocity setting command with ACK handling
            result = self._send_with_ack(MSG_TYPE_MOTOR_STATUS, cmd_data)
            
            # Update motor_config values if command was successful
            if result:
                self.motor_config['pan']['profileSpeed'] = pan_velocity_cnts
                self.motor_config['tilt']['profileSpeed'] = tilt_velocity_cnts
                logger.debug(f"Updated motor_config profile speeds: Pan={pan_velocity_cnts}, Tilt={tilt_velocity_cnts} cnts/sec")
                
            return result
        except Exception as e:
            self._handle_error(f"Error sending profile velocity setting command: {str(e)}")
            return False
    
    def misc_control_command(self, command_type, value=1):
        """
        General purpose function for miscellaneous control commands
        
        Args:
            command_type: Type of command (SUBIDX_TRIGGER, SUBIDX_TRACK, SUBIDX_STAB, SUBIDX_FIRING_RATE, 
                                         SUBIDX_ROUNDS, SUBIDX_BRAKE, SUBIDX_LOGIN, SUBIDX_CANLINE)
            value: Value to set (0 or 1 typically, or an integer for firing rate)
            
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error(f"Cannot send misc command: Not connected")
            return False
            
        try:
            # Create misc command structure
            # Format: uint8_t trigger, uint8_t track, uint8_t stab, uint32_t firingRate, 
            # uint8_t noOfRounds, uint8_t motorBrake, uint8_t login, uint8_t canlineopen, uint8_t subIdx
            trigger = value if command_type == SUBIDX_TRIGGER else self.misc_control['trigger']
            track = value if command_type == SUBIDX_TRACK else self.misc_control['track']
            stab = value if command_type == SUBIDX_STAB else self.misc_control['stab']
            firing_rate = value if command_type == SUBIDX_FIRING_RATE else self.misc_control['firingRate']
            rounds = value if command_type == SUBIDX_ROUNDS else self.misc_control['noOfRounds']
            brake = value if command_type == SUBIDX_BRAKE else self.misc_control['motorBrake']
            login = value if command_type == SUBIDX_LOGIN else self.misc_control['login']
            canlineopen = value if command_type == SUBIDX_CANLINE else self.misc_control['canlineopen']
            
            misc_data = struct.pack('<BBBIBBBBB',
                trigger,        # Trigger
                track,          # Track
                stab,           # Stab
                firing_rate,    # Firing rate
                rounds,         # Number of rounds
                brake,          # Motor brake
                login,          # Login
                canlineopen,    # CAN line open/closed
                command_type    # SubIdx for the operation
            )
            
            # Log the command being sent
            logger.info(f"Sending misc command: type={command_type}, value={value}")
            logger.info(f"Command data: trigger={trigger}, track={track}, stab={stab}, " +
                       f"firingRate={firing_rate}, rounds={rounds}, brake={brake}, login={login}, " +
                       f"canlineopen={canlineopen}")
            
            # Send command with ACK handling
            result = self._send_with_ack(MSG_TYPE_MISC_CONTROL, misc_data)
            
            # Special handling for brake command
            if command_type == SUBIDX_BRAKE and result:
                if value == 0:  # Unbrake
                    self.brake_time = time.time()
                
            # Special handling for trigger command
            if command_type == SUBIDX_TRIGGER and result:
                self.flag = not value  # Toggle flag for trigger state
                
            return result
        except Exception as e:
            self._handle_error(f"Error sending misc command: {str(e)}")
            return False
    
    # Convenience methods that use the misc_control_command function
    
    def brake(self):
        """Apply brake to motors"""
        logger.info("Applying brake")
        return self.misc_control_command(SUBIDX_BRAKE, 1)
    
    def unbrake(self):
        """Release brake from motors"""
        logger.info("Releasing brake")
        return self.misc_control_command(SUBIDX_BRAKE, 0)
    
    def trig(self, num_rounds):
        """Activate trigger without waiting for ACK"""
        if self.flag is None or self.flag:
            logger.info("Activating trigger (no ACK)")
            if num_rounds != 0:
                self.num_rounds = num_rounds
            return self.misc_control_command_no_ack(SUBIDX_TRIGGER, 1)
        return False

    def trigoff(self):
        """Deactivate trigger without waiting for ACK"""
        if self.flag is None or not self.flag:
            self.num_rounds = None
            logger.info("Deactivating trigger (no ACK)")
            return self.misc_control_command_no_ack(SUBIDX_TRIGGER, 0)
        return False

    
    def start_stab(self):
        """Start stabilization"""
        logger.info("Starting stabilization")
        return self.misc_control_command(SUBIDX_STAB, 1)
    
    def stop_stab(self):
        """Stop stabilization"""
        logger.info("Stopping stabilization")
        return self.misc_control_command(SUBIDX_STAB, 0)
    
    def set_firing_rate(self, rate):
        """
        Set the firing rate
        
        Args:
            rate: Firing rate value (uint32_t)
            
        Returns:
            bool: True if command was sent successfully
        """
        logger.info(f"Setting firing rate: {rate}")
        return self.misc_control_command(SUBIDX_FIRING_RATE, rate)    

    def set_rounds(self, num_rounds):
        """Set number of rounds to fire"""
        logger.info(f"Setting number of rounds: {num_rounds}")
        return self.misc_control_command(SUBIDX_ROUNDS, num_rounds)
    
    def start_track(self, pid_mode):
        """Start tracking"""
        logger.info("Starting tracking")
        return self.misc_control_command(SUBIDX_TRACK, pid_mode)
    
    def stop_track(self):
        """Stop tracking"""
        logger.info("Stopping tracking")
        return self.misc_control_command(SUBIDX_TRACK, 0)
    
    def start_touch_to_aim(self):
        "stop touch to aim"
        logger.info("Stopping touch to aim")
        return self.misc_control_command(SUBIDX_TRACK, 1)
    
    def login(self):
        """Send login command"""
        logger.info("Sending login command")
        return self.misc_control_command(SUBIDX_LOGIN, 1)
    
    def open_canline(self):
        """Open CAN line"""
        logger.info("Opening CAN line")
        return self.misc_control_command(SUBIDX_CANLINE, 1)
        
    def close_canline(self):
        """Close CAN line"""
        logger.info("Closing CAN line")
        return self.misc_control_command(SUBIDX_CANLINE, 0)
    
    def login_and_configure(self):
        """
        Send login command and configure motors with optimal parameters
        
        This function sends the login command and then configures both pan and tilt
        motors with the recommended parameters. It also reads back configurations
        and diagnostic information.
        
        Returns:
            bool: True if all commands were sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot login: Not connected")
            return False
            
        try:
            logger.info("Sending login command and configuring motors")
            
            # First send login command
            login_result = self.login()
            if not login_result:
                logger.error("Login command failed")
                return False
                
            # Wait a short time to ensure login is processed
            time.sleep(0.2)
            
            # Configure pan motor with optimal parameters
            pan_motion_params = {
                'profileSpeed': 72817,
                'profileAcceleration': 360000,
                'profileDeceleration': 360000,
                'maxSpeed': 216000,
                'maxPositionError': 0,
                'maxSpeedError': 0
            }
            
            # Write pan motor configuration
            logger.info("Writing pan motor configuration")
            pan_result = self.write_pan_motion_params(pan_motion_params)
            if not pan_result:
                logger.error("Failed to configure pan motor")
                return False
                
            # Wait a short time between commands
            # time.sleep(0.2)
            
            # Configure tilt motor with optimal parameters
            tilt_motion_params = {
                'profileSpeed': 72817,
                'profileAcceleration': 360000,
                'profileDeceleration': 360000,
                'maxSpeed': 216000,
                'maxPositionError': 0,
                'maxSpeedError': 0
            }
            
            # Write tilt motor configuration
            logger.info("Writing tilt motor configuration")
            tilt_result = self.write_tilt_motion_params(tilt_motion_params)
            if not tilt_result:
                logger.error("Failed to configure tilt motor")
                return False
            
            # Wait a short time between commands
            # time.sleep(0.2)
            
            # Read pan configuration
            logger.info("Reading pan motor configuration")
            read_pan_result = self.read_pan_config()
            if not read_pan_result:
                logger.warning("Failed to read pan configuration")
                # Continue anyway
            
            # Wait a short time between commands
            # time.sleep(0.2)
            
            # Read tilt configuration
            logger.info("Reading tilt motor configuration")
            read_tilt_result = self.read_tilt_config()
            if not read_tilt_result:
                logger.warning("Failed to read tilt configuration")
                # Continue anyway
            
            # # Wait a short time between commands
            # time.sleep(0.2)
            
            # # Read diagnostics for both motors
            # logger.info("Reading motor diagnostics")
            # diag_result = self.request_diagnostics()
            # if not diag_result:
            #     logger.warning("Failed to read motor diagnostics")
            #     # Continue anyway
                
            logger.info("Login and motor configuration completed successfully")
            return True
            
        except Exception as e:
            self._handle_error(f"Error during login and configuration: {str(e)}")
            return False
    
    def logout_cmd(self):
        """Send logout command"""
        logger.info("Sending logout command")
        return self.misc_control_command(SUBIDX_LOGIN, 0)
    
    def read_pan_config(self):
        """
        Read pan motor configuration
        
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot read pan config: Not connected")
            return False
            
        try:
            logger.info("Reading pan motor configuration")
            
            # Create a complete MotorConfig_t structure with just the subindex set
            # Format: profileSpeed, profileAccel, profileDecel, maxSpeed, maxPosError, maxSpeedError, 
            #         maxPosLimit, minPosLimit, arc, subIdx
            config_data = struct.pack('<IIIIIIiiBH',
                0,  # profileSpeed
                0,  # profileAcceleration
                0,  # profileDeceleration
                0,  # maxSpeed
                0,  # maxPositionError
                0,  # maxSpeedError
                0,  # maxPositionLimit
                0,  # minPositionLimit
                0,  # arc
                SUBIDX_READ_PAN_CONFIG  # SubIdx for reading pan config (should be 1)
            )
            
            logger.info(f"Sending config request with subIdx={SUBIDX_READ_PAN_CONFIG}, length={len(config_data)}")
            logger.info(f"Hex data: {config_data.hex()}")
            logger.info(f"Last two bytes (subindex): {config_data[-2:].hex()}")
            
            # Send config request with ACK handling
            return self._send_with_ack(MSG_TYPE_MOTOR_CONFIG, config_data)
        except Exception as e:
            self._handle_error(f"Error requesting pan configuration: {str(e)}")
            return False
    
    def read_tilt_config(self):
        """
        Read tilt motor configuration
        
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot read tilt config: Not connected")
            return False
            
        try:
            logger.info("Reading tilt motor configuration")
            
            # Create a complete MotorConfig_t structure with just the subindex set
            # Format: profileSpeed, profileAccel, profileDecel, maxSpeed, maxPosError, maxSpeedError, 
            #         maxPosLimit, minPosLimit, arc, subIdx
            config_data = struct.pack('<IIIIIIiiBH',
                0,  # profileSpeed
                0,  # profileAcceleration
                0,  # profileDeceleration
                0,  # maxSpeed
                0,  # maxPositionError
                0,  # maxSpeedError
                0,  # maxPositionLimit
                0,  # minPositionLimit
                0,  # arc
                SUBIDX_READ_TILT_CONFIG  # SubIdx for reading tilt config (should be 2)
            )
            
            logger.info(f"Sending config request with subIdx={SUBIDX_READ_TILT_CONFIG}, length={len(config_data)}")
            logger.info(f"Hex data: {config_data.hex()}")
            logger.info(f"Last two bytes (subindex): {config_data[-2:].hex()}")
            
            # Send config request with ACK handling
            return self._send_with_ack(MSG_TYPE_MOTOR_CONFIG, config_data)
        except Exception as e:
            self._handle_error(f"Error requesting tilt configuration: {str(e)}")
            return False
    
    def write_pan_motion_params(self, params):
        """
        Write pan motor motion parameters
        
        Args:
            params: Dictionary with motion parameters
            
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot write pan motion params: Not connected")
            return False
            
        try:
            logger.info("Writing pan motor motion parameters")
            
            # Create config structure with motion parameters
            # Use the full MotorConfig_t structure but set subindex to 4 (write pan motion)
            config_data = struct.pack('<IIIIIIiiBH',  # Changed ? to B for arc
                params.get('profileSpeed', 0),
                params.get('profileAcceleration', 0),
                params.get('profileDeceleration', 0),
                params.get('maxSpeed', 0),
                params.get('maxPositionError', 0),
                params.get('maxSpeedError', 0),
                0,  # maxPositionLimit (not used for motion params)
                0,  # minPositionLimit (not used for motion params)
                0,  # arc (not used for motion params)
                SUBIDX_WRITE_PAN_MOTION  # SubIdx for writing pan motion parameters
            )

            logger.info(f"Raw data bytes: {len(config_data)} bytes")
            logger.info(f"Hex data: {config_data.hex()}")
            logger.info(f"Last two bytes (subindex): {config_data[-2:].hex()}")
            logger.info(f"Expected subindex: {SUBIDX_WRITE_PAN_MOTION}")
            
            # Send config command with ACK handling
            return self._send_with_ack(MSG_TYPE_MOTOR_CONFIG, config_data)
        except Exception as e:
            self._handle_error(f"Error sending pan motion parameters: {str(e)}")
            return False
    
    def write_tilt_motion_params(self, params):
        """
        Write tilt motor motion parameters
        
        Args:
            params: Dictionary with motion parameters
            
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot write tilt motion params: Not connected")
            return False
            
        try:
            logger.info("Writing tilt motor motion parameters")
            
            # Create config structure with motion parameters
            # Use the full MotorConfig_t structure but set subindex to 8 (write tilt motion)
            config_data = struct.pack('<IIIIIIiiBH',  # Changed ? to B for arc
                params.get('profileSpeed', 0),
                params.get('profileAcceleration', 0),
                params.get('profileDeceleration', 0),
                params.get('maxSpeed', 0),
                params.get('maxPositionError', 0),
                params.get('maxSpeedError', 0),
                0,  # maxPositionLimit (not used for motion params)
                0,  # minPositionLimit (not used for motion params)
                0,  # arc (not used for motion params)
                SUBIDX_WRITE_TILT_MOTION  # SubIdx for writing tilt motion parameters
            )
            
            logger.info(f"Raw data bytes: {len(config_data)} bytes")
            logger.info(f"Hex data: {config_data.hex()}")
            logger.info(f"Last two bytes (subindex): {config_data[-2:].hex()}")
            logger.info(f"Expected subindex: {SUBIDX_WRITE_TILT_MOTION}")
            
            # Send config command with ACK handling
            return self._send_with_ack(MSG_TYPE_MOTOR_CONFIG, config_data)
        except Exception as e:
            self._handle_error(f"Error sending tilt motion parameters: {str(e)}")
            return False
    def read_pan_encoder(self):
        """Read the current pan encoder position from the motor"""
        if not self.connected:
            self._handle_error("Cannot read pan encoder: Not connected")
            return None
            
        try:
            # Return the current pan encoder position from motor_status
            # This is already being updated via _handle_motor_status()
            return self.motor_status['pan']
        except Exception as e:
            self._handle_error(f"Error reading pan encoder: {str(e)}")
            return None

    def read_tilt_encoder(self):
        """Read the current tilt encoder position from the motor"""
        if not self.connected:
            self._handle_error("Cannot read tilt encoder: Not connected")
            return None
            
        try:
            # Return the current tilt encoder position from motor_status
            # This is already being updated via _handle_motor_status()
            return self.motor_status['tilt']
        except Exception as e:
            self._handle_error(f"Error reading tilt encoder: {str(e)}")
            return None
    
    def write_pan_limit_params(self, params):
        """
        Write pan motor limit parameters
        Args:
            params: Dictionary with limit parameters
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot write pan limit params: Not connected")
            return False
        try:
            logger.info("Writing pan motor limit parameters")
            # Create config structure with limit parameters
            # Use the full MotorConfig_t structure but set subindex to 16 (write pan limits)
            config_data = struct.pack('<IIIIIIiiBH',  # Changed ? to B for arc
                0,  # profileSpeed (not used for limit params)
                0,  # profileAcceleration (not used for limit params)
                0,  # profileDeceleration (not used for limit params)
                0,  # maxSpeed (not used for limit params)
                0,  # maxPositionError (not used for limit params)
                0,  # maxSpeedError (not used for limit params)
                params.get('maxPositionLimit', 0),
                params.get('minPositionLimit', 0),
                1 if params.get('arc', False) else 0,  # Convert boolean to uint8_t
                SUBIDX_WRITE_PAN_LIMITS  # SubIdx for writing pan limit parameters
            )
            # Send config command with ACK handling
            return self._send_with_ack(MSG_TYPE_MOTOR_CONFIG, config_data)
        except Exception as e:
            self._handle_error(f"Error sending pan limit parameters: {str(e)}")
            return False

    def write_tilt_limit_params(self, params):
        """
        Write tilt motor limit parameters
        Args:
            params: Dictionary with limit parameters
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot write tilt limit params: Not connected")
            return False
        try:
            logger.info("Writing tilt motor limit parameters")
            # Create config structure with limit parameters
            # Use the full MotorConfig_t structure but set subindex to 32 (write tilt limits)
            config_data = struct.pack('<IIIIIIiiBH',  # Changed ? to B for arc
                0,  # profileSpeed (not used for limit params)
                0,  # profileAcceleration (not used for limit params)
                0,  # profileDeceleration (not used for limit params)
                0,  # maxSpeed (not used for limit params)
                0,  # maxPositionError (not used for limit params)
                0,  # maxSpeedError (not used for limit params)
                params.get('maxPositionLimit', 0),
                params.get('minPositionLimit', 0),
                1 if params.get('arc', False) else 0,  # Convert boolean to uint8_t
                SUBIDX_WRITE_TILT_LIMITS  # SubIdx for writing tilt limit parameters
            )
            # Send config command with ACK handling
            return self._send_with_ack(MSG_TYPE_MOTOR_CONFIG, config_data)
        except Exception as e:
            self._handle_error(f"Error sending tilt limit parameters: {str(e)}")
            return False
    
    def request_pan_diagnostics(self):
        """
        Request pan motor diagnostics
        
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot request diagnostics: Not connected")
            return False
            
        try:
            logger.info("Requesting pan motor diagnostics")
            
            # Set the current diagnostic request type to PAN (1)
            self.diagnostic_request_type = 1
            
            # Create diagnostics request with value 1 for pan
            # ESP32 is expecting a single uint8_t value
            diag_data = struct.pack('<B', 1)  # 1 = PAN
            
            logger.info(f"Sending pan diagnostics request with value=1, bytes={diag_data.hex()}")
            
            # Send diagnostics request with ACK handling
            return self._send_with_ack(MSG_TYPE_MOTOR_DIAGNOSTICS, diag_data)
        except Exception as e:
            self._handle_error(f"Error requesting pan diagnostics: {str(e)}")
            return False
    
    def request_tilt_diagnostics(self):
        """
        Request tilt motor diagnostics
        
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot request diagnostics: Not connected")
            return False
            
        try:
            logger.info("Requesting tilt motor diagnostics")
            
            # Set the current diagnostic request type to TILT (2)
            self.diagnostic_request_type = 2
            
            # Create diagnostics request with value 2 for tilt
            # ESP32 is expecting a single uint8_t value
            diag_data = struct.pack('<B', 2)  # 2 = TILT
            
            logger.info(f"Sending tilt diagnostics request with value=2, bytes={diag_data.hex()}")
            
            # Send diagnostics request with ACK handling
            return self._send_with_ack(MSG_TYPE_MOTOR_DIAGNOSTICS, diag_data)
        except Exception as e:
            self._handle_error(f"Error requesting tilt diagnostics: {str(e)}")
            return False
    
    # Enhance the request_diagnostics method in TinyFrameController.py

    def request_diagnostics(self):
        """
        Request motor diagnostics for both pan and tilt with improved timing
        
        Returns:
            bool: True if command was sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot request diagnostics: Not connected")
            return False
            
        try:
            logger.info("Requesting both pan and tilt motor diagnostics")
            
            # First request configuration data if not already available
            if not self.motor_config['pan'].get('profileSpeed'):
                logger.info("Motor configuration not available, requesting it first")
                self.read_pan_config()
                time.sleep(0.3)  # Short delay
                self.read_tilt_config()
                time.sleep(0.3)  # Short delay
            
            # First request pan diagnostics
            pan_result = self.request_pan_diagnostics()
            
            # Wait a short time to allow ESP32 to process first request
            # Reduced from 0.5 to 0.3 seconds for faster response
            time.sleep(0.3)
            
            # Then request tilt diagnostics
            tilt_result = self.request_tilt_diagnostics()
            
            # Return true if both succeeded
            return pan_result and tilt_result
        except Exception as e:
            self._handle_error(f"Error requesting diagnostics: {str(e)}")
            return False
    
    def is_system_alive(self):
        """
        Check if the system is alive based on heartbeat
        
        Returns:
            bool: True if system is alive
        """
        # Check if we've received a heartbeat in the last 5 seconds
        if self.heartbeat['active'] and (time.time() - self.heartbeat['timestamp']) < 5:
            return True
        return False
    
    # def send_exit_commands(self):
    #     """
    #     Send all exit commands at once in a single packet
        
    #     This sends brake on, trigger off, stabilization off, tracking off, and logout
    #     all in a single Misc_t structure packet.
        
    #     Returns:
    #         bool: True if command was sent successfully
    #     """
    #     if not self.connected:
    #         self._handle_error("Cannot send exit commands: Not connected")
    #         return False
            
    #     try:
    #         logger.info("Sending all exit commands in a single packet")
            
    #         # Create misc command structure with all exit values set
    #         # Format: uint8_t trigger, uint8_t track, uint8_t stab, uint32_t firingRate, 
    #         # uint8_t noOfRounds, uint8_t motorBrake, uint8_t login, uint8_t canlineopen, uint8_t subIdx
    #         misc_data = struct.pack('<BBBIBBBBB',
    #             0,  # Trigger off
    #             0,  # Track off
    #             0,  # Stab off
    #             0,  # Firing rate (unchanged)
    #             0,  # Number of rounds (unchanged)
    #             1,  # Motor brake on
    #             0,  # Logout
    #             0,
    #             SUBIDX_LOGIN
    #         )
            
    #         # Send all exit commands with ACK handling
    #         result = self._send_with_ack(MSG_TYPE_MISC_CONTROL, misc_data)
            
    #         # Update internal state
    #         if result:
    #             self.misc_control['trigger'] = 0
    #             self.misc_control['track'] = 0
    #             self.misc_control['stab'] = 0
    #             self.misc_control['motorBrake'] = 1
    #             self.misc_control['login'] = 0
    #             self.misc_control['canlineopen'] = 0
    #             self.flag = True  # Update trigger flag
    #             self.brake_time = time.time()
            
    #         return result
    #     except Exception as e:
    #         self._handle_error(f"Error sending exit commands: {str(e)}")
    #         return False

    def send_exit_commands(self):
        """
        Send all exit commands individually instead of in a single packet
        
        This sends brake on, trigger off, stabilization off, tracking off, and logout
        as separate commands with individual ACK handling.
        
        Returns:
            bool: True if all commands were sent successfully
        """
        if not self.connected:
            self._handle_error("Cannot send exit commands: Not connected")
            return False
            
        try:
            logger.info("Sending exit commands individually")
            
            # Call each command individually
            trig_result = self.trigoff()
            logger.info(f"Trigger off command result: {trig_result}")
            
            # Small delay between commands
            time.sleep(0.1)
            
            track_result = self.stop_track()
            logger.info(f"Stop track command result: {track_result}")
            
            # Small delay between commands
            time.sleep(0.1)
            
            stab_result = self.stop_stab()
            logger.info(f"Stop stabilization command result: {stab_result}")
            
            # Small delay between commands
            time.sleep(0.1)
            
            brake_result = self.brake()
            logger.info(f"Brake command result: {brake_result}")
            
            # Small delay between commands
            time.sleep(0.1)
            
            logout_result = self.logout_cmd()
            logger.info(f"Logout command result: {logout_result}")
            
            # Check if all commands were successful
            overall_result = trig_result and track_result and stab_result and brake_result and logout_result
            
            # Update internal state
            self.misc_control['trigger'] = 0
            self.misc_control['track'] = 0
            self.misc_control['stab'] = 0
            self.misc_control['motorBrake'] = 1
            self.misc_control['login'] = 0
            self.misc_control['canlineopen'] = 0
            self.flag = True  # Update trigger flag
            self.brake_time = time.time()
            
            if overall_result:
                logger.info("All exit commands executed successfully")
            else:
                logger.warning("Some exit commands failed to execute")
            
            return overall_result
        except Exception as e:
            self._handle_error(f"Error sending exit commands: {str(e)}")
            return False
    
    def exit(self):
        """
        Clean up resources before exiting
        """
        logger.info("Exiting TinyFrameGunController")
        try:
            # Make sure motors are disabled with a single command
            if self.connected:
                self.send_exit_commands()
            
            # Close TinyFrame
            if hasattr(self, 'tf'):
                self.tf.cleanup()
                
            self.connected = False
            logger.info("Resources cleaned up")
        except Exception as e:
            self._handle_error(f"Error during exit: {str(e)}")


if __name__ == "__main__":
    # Example usage of TinyFrameGunController
    def update_position_callback(pan, tilt):
        print(f"Position update: Pan = {pan}°, Tilt = {tilt}°")

    def error_callback(error_msg):
        print(f"ERROR: {error_msg}")
    
    try:
        # Initialize the controller
        print("Initializing TinyFrameGunController...")
        controller = TinyFrameGunController(
            function=update_position_callback,
            function_error=error_callback
        )
        
        # Test if the system is alive
        if controller.is_system_alive():
            print("System is alive!")
        else:
            print("System is not responding! Continuing anyway for testing...")
        
        # Write motion parameters for PAN motor (subindex 4)
        print("\n--- Setting PAN Motor Motion Parameters (SubIndex 4) ---")
        pan_motion_params = {
            'profileSpeed': 100000,  # Higher profile speed as requested
            'profileAcceleration': 100000,
            'profileDeceleration': 100000,
            'maxSpeed': 100000,
            'maxPositionError': 500,
            'maxSpeedError': 500
        }
        
        if controller.write_pan_motion_params(pan_motion_params):
            print("PAN motion parameters set successfully!")
        else:
            print("Failed to set PAN motion parameters.")
        
        # Write motion parameters for TILT motor (subindex 8)
        print("\n--- Setting TILT Motor Motion Parameters (SubIndex 8) ---")
        tilt_motion_params = {
            'profileSpeed': 100000,  # Higher profile speed
            'profileAcceleration': 100000,
            'profileDeceleration': 100000,
            'maxSpeed': 100000,
            'maxPositionError': 500,
            'maxSpeedError': 500
        }
        
        if controller.write_tilt_motion_params(tilt_motion_params):
            print("TILT motion parameters set successfully!")
        else:
            print("Failed to set TILT motion parameters.")
        

        print("\n--- Reading Motor Configurations ---")
        print("Reading PAN motor configuration...")
        controller.read_pan_config()
        time.sleep(1)  # Wait for response
        
        print("PAN motor configuration:")
        for key, value in controller.motor_config['pan'].items():
            print(f"  {key}: {value}")
    
        print("\nReading TILT motor configuration...")
        controller.read_tilt_config()
        time.sleep(1)  # Wait for response
        
        print("TILT motor configuration:")
        for key, value in controller.motor_config['tilt'].items():
            print(f"  {key}: {value}")

        
        print("\n--- Requesting Motor Diagnostics ---")
        controller.request_diagnostics()
        time.sleep(2)  # Wait for responses
        
        print("PAN motor diagnostics:")
        for key, value in controller.motor_diagnostics['pan'].items():
            print(f"  {key}: {value}")
        
        print("\nTILT motor diagnostics:")
        for key, value in controller.motor_diagnostics['tilt'].items():
            print(f"  {key}: {value}")
        
        # Test position control with profile speed setting
        print("\n--- Testing Position Control with Profile Speed ---")
        if controller.move(0, 0, 50000, 50000):
            print("Move command with profile speed sent successfully")
        else:
            print("Failed to send move command with profile speed")
        
        time.sleep(3)  # Wait for movement to complete
        
        # Test profile velocity control
        print("\n--- Testing Profile Velocity Control ---")
        if controller.vmove(20, -10):
            print("Profile velocity command sent successfully")
        else:
            print("Failed to send profile velocity command")
        
        time.sleep(2)
        
        # Test CSV velocity control
        print("\n--- Testing CSV Velocity Control ---")
        if controller.csvmove(15, -5):
            print("CSV velocity command sent successfully")
        else:
            print("Failed to send CSV velocity command")
        
        time.sleep(2)
        controller.vmove(0, 0)  # Stop the movement
        
        # Test login/logout
        print("\n--- Testing Login/Logout Commands ---")
        if controller.login():
            print("Login command sent successfully")
        else:
            print("Failed to send login command")
            
        time.sleep(1)
        
        if controller.logout_cmd():
            print("Logout command sent successfully")
        else:
            print("Failed to send logout command")
        
        # Test CAN line operations
        print("\n--- Testing CAN Line Commands ---")
        if controller.open_canline():
            print("Open CAN line command sent successfully")
        else:
            print("Failed to send open CAN line command")
            
        time.sleep(1)
        
        if controller.close_canline():
            print("Close CAN line command sent successfully")
        else:
            print("Failed to send close CAN line command")
            
        # Test sending all exit commands at once
        print("\n--- Testing Send All Exit Commands ---")
        if controller.send_exit_commands():
            print("All exit commands sent successfully in a single packet")
        else:
            print("Failed to send exit commands")
    
    except KeyboardInterrupt:
        print("\nTesting interrupted by user")
    except Exception as e:
        print(f"\nAn error occurred: {str(e)}")
    finally:
        print("\nCleaning up...")
        # if 'controller' in locals():
            # controller.exit()
        print("Test completed")