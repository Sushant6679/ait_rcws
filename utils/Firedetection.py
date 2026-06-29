#!/usr/bin/env python3
"""
Single Port CASTLE Fire Detection Listener - Integrated with RCWS Auto-targeting
Handles all CASTLE message types and provides auto-targeting capabilities with comprehensive logging
"""
import socket
import json
import struct
import threading
import time
import traceback
import logging
import os
from datetime import datetime
from typing import Dict, Any, Optional, Callable

class CASTLEListener:
    def __init__(self, video_player_instance=None, debug=False):
        """Initialize CASTLE listener with RCWS integration and logging"""
        self.multicast_ip = "239.255.43.21"
        self.port = 40100
        
        self.socket = None
        self.thread = None
        self.running = False
        
        # Reference to VideoPlayer for auto-targeting
        self.video_player = video_player_instance
        
        # Latest data storage
        self.latest_fire_event = None
        self.latest_localization = None
        self.latest_node_info = None
        
        # Auto-targeting control
        self.auto_targeting_enabled = False
        self.last_targeting_timestamp = None
        
        # Stats
        self.stats = {
            'node_info': {'messages': 0, 'events': 0},
            'event_detection': {'messages': 0, 'events': 0},
            'event_localization': {'messages': 0, 'events': 0},
            'auto_targeting_attempts': 0,
            'successful_targeting': 0,
            'unknown': {'messages': 0, 'events': 0}
        }
        self.total_messages = 0
        self.start_time = None
        
        # Thread safety
        self.lock = threading.Lock()
        
        # Debug mode
        self.debug = debug
        
        # Initialize logging
        self.logger = None
        self.log_file_path = None
        self.setup_logging()
        
    def setup_logging(self):
        """Setup dedicated logging for Fire Detection system"""
        try:
            # Create logs directory if it doesn't exist
            log_dir = "fire_detection_logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # Create unique log filename with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_file_path = os.path.join(log_dir, f"castle_fire_detection_{timestamp}.log")
            
            # Create logger
            self.logger = logging.getLogger(f'castle_fire_detection_{timestamp}')
            self.logger.setLevel(logging.DEBUG)
            
            # Remove any existing handlers to avoid duplicates
            if self.logger.handlers:
                self.logger.handlers.clear()
            
            # Create file handler
            file_handler = logging.FileHandler(self.log_file_path, mode='w', encoding='utf-8')
            file_handler.setLevel(logging.DEBUG)
            
            # Create console handler for important messages
            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.INFO)
            
            # Create detailed formatter for file
            file_formatter = logging.Formatter(
                '%(asctime)s.%(msecs)03d | %(levelname)-8s | %(funcName)-20s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            
            # Create simple formatter for console
            console_formatter = logging.Formatter(
                '%(asctime)s | CASTLE | %(levelname)s | %(message)s',
                datefmt='%H:%M:%S'
            )
            
            file_handler.setFormatter(file_formatter)
            console_handler.setFormatter(console_formatter)
            
            self.logger.addHandler(file_handler)
            self.logger.addHandler(console_handler)
            
            # Prevent propagation to root logger
            self.logger.propagate = False
            
            if self.debug:
                print(f"🔥 Fire Detection logging initialized: {self.log_file_path}")
                
        except Exception as e:
            print(f"Error setting up Fire Detection logging: {str(e)}")
            self.logger = None
    
    def log_message(self, level, message, extra_data=None):
        """Centralized logging method"""
        if not self.logger:
            return
            
        try:
            if extra_data:
                full_message = f"{message} | Data: {json.dumps(extra_data, indent=2, default=str)}"
            else:
                full_message = message
                
            if level == 'debug':
                self.logger.debug(full_message)
            elif level == 'info':
                self.logger.info(full_message)
            elif level == 'warning':
                self.logger.warning(full_message)
            elif level == 'error':
                self.logger.error(full_message)
            elif level == 'critical':
                self.logger.critical(full_message)
        except Exception as e:
            if self.debug:
                print(f"Error in log_message: {str(e)}")
    
    def log_raw_message(self, message_type, raw_message):
        """Log the complete raw message for debugging and analysis"""
        if not self.logger:
            return
            
        try:
            self.logger.debug(f"RAW_{message_type.upper()}_MESSAGE: {json.dumps(raw_message, indent=2, default=str)}")
        except Exception as e:
            if self.debug:
                print(f"Error logging raw message: {str(e)}")
        
    def convert_relative_angle_to_rcws(self, relative_angle):
        """
        Convert ACLOGUS-4 sensor relative angle to RCWS coordinates
        Sensor front (90°) -> RCWS 0°, so subtract 90°
        """
        rcws_angle = relative_angle
        
        self.log_message('debug', f"Angle conversion: Sensor {relative_angle}° -> RCWS {rcws_angle}°")
        
        if self.debug:
            print(f"Converted sensor relative angle {relative_angle}° to RCWS angle {rcws_angle}°")
        return rcws_angle
    
    def attempt_auto_targeting(self, relative_angle, event_type="UNKNOWN", additional_info=""):
        """
        Attempt to auto-target the RCWS if conditions are met
        NOW WITH CLASSIFICATION FILTERING
        """
        try:
            # 🎯 NEW: CLASSIFICATION FILTERING - ADD THIS SECTION AT THE BEGINNING
            
            # Define movement rules by classification
            event_localization_prefix = "PRECISE"  # All event_localization start with "PRECISE"
            allowed_event_detection = [
                "SHOCKWAVE",      # Allow shockwave 
                "MUZZLE BLAST",   # Allow muzzle_blast
                "MORTAR"          # Allow mortar
            ]
            blocked_event_detection = [
                "SHOCKWAVE WARNING"  # Block sw_warning
            ]
            
            # Check if this is event_localization (always allow)
            if event_type.startswith(event_localization_prefix):
                self.log_message('info', f"Event localization detected - movement ALLOWED", {
                    'event_type': event_type,
                    'rule': 'Always allow event_localization'
                })
            # Check if this is blocked event_detection  
            elif event_type in blocked_event_detection:
                self.log_message('warning', f"Movement BLOCKED for classification: {event_type}", {
                    'event_type': event_type,
                    'rule': 'Blocked classification',
                    'allowed_classifications': allowed_event_detection,
                    'blocked_classifications': blocked_event_detection
                })
                return False
            # Check if this is allowed event_detection
            elif event_type in allowed_event_detection:
                self.log_message('info', f"Event detection allowed - movement PERMITTED", {
                    'event_type': event_type,
                    'rule': 'Allowed event_detection classification'
                })
            # Handle unknown/unexpected classifications
            else:
                self.log_message('warning', f"Unknown classification - movement BLOCKED", {
                    'event_type': event_type,
                    'rule': 'Unknown classification blocked by default',
                    'allowed_classifications': allowed_event_detection,
                    'blocked_classifications': blocked_event_detection
                })
                return False
            
            # 🎯 END OF NEW CLASSIFICATION FILTERING SECTION
            
            # Continue with existing condition checks...
            self.log_message('info', f"Auto-targeting attempt initiated", {
                'event_type': event_type,
                'relative_angle': relative_angle,
                'additional_info': additional_info
            })
            
            # Check if auto-targeting is enabled
            if not self.auto_targeting_enabled:
                self.log_message('warning', f"Auto-targeting disabled - {event_type} detected but not targeting")
                if self.debug:
                    print(f"Auto-targeting disabled - {event_type} detected but not targeting")
                return False
            
            # Check if VideoPlayer instance is available
            if not self.video_player:
                self.log_message('error', f"No VideoPlayer instance - cannot auto-target {event_type}")
                if self.debug:
                    print(f"No VideoPlayer instance - cannot auto-target {event_type}")
                return False
            
            # Check if fire detection is active in the main application
            if not hasattr(self.video_player, 'fire_detection_active') or not self.video_player.fire_detection_active:
                self.log_message('warning', f"Fire detection not active in main app - {event_type} detected but not targeting")
                if self.debug:
                    print(f"Fire detection not active in main app - {event_type} detected but not targeting")
                return False
            
            # Convert relative angle to RCWS coordinates
            rcws_azimuth = self.convert_relative_angle_to_rcws(relative_angle)
            
            # Check movement restrictions (armed + fire on move off)
            fire_on_move = 'Off'
            if (hasattr(self.video_player, 'config') and 
                'DEFAULT' in self.video_player.config and 
                'Fire on Move' in self.video_player.config['DEFAULT']):
                fire_on_move = self.video_player.config['DEFAULT']['Fire on Move']
                
            if (hasattr(self.video_player, 'armed') and 
                self.video_player.armed and 
                fire_on_move == 'Off'):
                self.log_message('warning', f"Auto-targeting blocked: System is ARMED and Fire on Move is Off")
                if self.debug:
                    print(f"Auto-targeting blocked: System is ARMED and Fire on Move is Off")
                return False
            
            # Get current elevation for targeting
            current_elevation = getattr(self.video_player, '_gun_elevation', 0)
            
            self.log_message('info', f"Attempting gun movement", {
                'target_azimuth': rcws_azimuth,
                'target_elevation': current_elevation,
                'event_type': event_type
            })
            
            # Attempt to move gun
            success = self.video_player.position_gun(rcws_azimuth, current_elevation)
            
            # Update stats
            with self.lock:
                self.stats['auto_targeting_attempts'] += 1
                if success:
                    self.stats['successful_targeting'] += 1
                    self.last_targeting_timestamp = datetime.now()
            
            if success:
                self.log_message('critical', f"AUTO-TARGETING SUCCESSFUL", {
                    'event_type': event_type,
                    'target_azimuth': rcws_azimuth,
                    'target_elevation': current_elevation,
                    'additional_info': additional_info
                })
                print(f"✅ AUTO-TARGETING SUCCESSFUL: {event_type}")
                print(f"   Target: {rcws_azimuth:.2f}° azimuth, {current_elevation:.2f}° elevation")
                print(f"   {additional_info}")
            else:
                self.log_message('error', f"AUTO-TARGETING FAILED", {
                    'event_type': event_type,
                    'target_azimuth': rcws_azimuth,
                    'target_elevation': current_elevation,
                    'reason': "Target outside limits or movement restricted"
                })
                print(f"❌ AUTO-TARGETING FAILED: {event_type}")
                print(f"   Target was outside limits or movement restricted")
                
            return success
            
        except Exception as e:
            self.log_message('error', f"Error in auto-targeting: {str(e)}")
            print(f"Error in auto-targeting: {str(e)}")
            if self.debug:
                traceback.print_exc()
            return False
    
    def fire_detection_callback(self, fire_data):
        """Enhanced fire detection callback with auto-targeting and logging"""
        try:
            classification = fire_data.get('classification', 'unknown')
            relative_angle = fire_data.get('relative_angle')
            azimuth = fire_data.get('azimuth')  # Keep for logging
            node_id = fire_data.get('node_id', 'Unknown')
            level = fire_data.get('level')
            event_id = fire_data.get('event_id')
            
            # Classification mapping
            classification_map = {
                'sw_warning': "SHOCKWAVE WARNING",
                'shockwave': "SHOCKWAVE", 
                'muzzle_blast': "MUZZLE BLAST",
                'mortar': "MORTAR"
            }
            classification_name = classification_map.get(classification, f"{classification.upper()}")
            
            # Log the fire detection event
            self.log_message('critical', f"FIRE DETECTION EVENT: {classification_name}", {
                'node_id': node_id,
                'event_id': event_id,
                'sound_level_db': level,
                'absolute_azimuth': azimuth,
                'relative_angle': relative_angle,
                'timestamp': fire_data.get('timestamp'),
                'full_data': fire_data
            })
            
            print(f"🔥 CASTLE FIRE DETECTION: {classification_name}")
            print(f"   Node: {node_id} | Event ID: {event_id}")
            if level is not None:
                print(f"   Sound Level: {level:.1f} dB")
            if azimuth is not None:
                print(f"   Absolute Azimuth: {azimuth:.1f}°")
            if relative_angle is not None:
                print(f"   Relative Angle: {relative_angle:.1f}°")
            
            # Store latest detection
            with self.lock:
                self.latest_fire_event = fire_data
                
            # Attempt auto-targeting using relative angle if available
            if relative_angle is not None:
                additional_info = f"Node: {node_id}, Level: {level:.1f}dB" if level else f"Node: {node_id}"
                self.attempt_auto_targeting(
                    relative_angle, 
                    event_type=classification_name,
                    additional_info=additional_info
                )
            elif azimuth is not None:
                # Fallback to absolute azimuth if relative angle not available
                # Convert absolute azimuth to relative angle (azimuth)
                relative_angle_fallback = azimuth
                    
                self.log_message('warning', f"Using fallback angle conversion: {azimuth}° -> {relative_angle_fallback}° relative")
                print(f"   Using fallback conversion: {azimuth}° -> {relative_angle_fallback}° relative")
                additional_info = f"Node: {node_id}, Level: {level:.1f}dB (fallback)" if level else f"Node: {node_id} (fallback)"
                self.attempt_auto_targeting(
                    relative_angle_fallback,
                    event_type=classification_name,
                    additional_info=additional_info
                )
                
        except Exception as e:
            self.log_message('error', f"Error in fire detection callback: {str(e)}")
            print(f"Error in fire detection callback: {str(e)}")
            if self.debug:
                traceback.print_exc()
    
    def localization_callback(self, loc_data):
        """Enhanced localization callback with precise auto-targeting and logging"""
        try:
            classification = loc_data.get('classification', 'Unknown')
            relative_angle = loc_data.get('relative_angle')  # This is from relative_info.angle
            azimuth = loc_data.get('azimuth')  # Keep for logging
            range_m = loc_data.get('range')
            shots = loc_data.get('shots')
            node_id = loc_data.get('node_id', 'Unknown')
            event_id = loc_data.get('event_id')
            
            # Log the localization event
            self.log_message('critical', f"LOCALIZATION EVENT: {classification.upper()}", {
                'node_id': node_id,
                'event_id': event_id,
                'absolute_azimuth': azimuth,
                'relative_angle': relative_angle,
                'range_meters': range_m,
                'shots_detected': shots,
                'timestamp': loc_data.get('timestamp'),
                'full_data': loc_data
            })
            
            print(f"🎯 CASTLE LOCALIZATION: {classification.upper()}")
            print(f"   Node: {node_id} | Event ID: {event_id}")
            if azimuth is not None:
                print(f"   Absolute Azimuth: {azimuth:.1f}°")
            if relative_angle is not None:
                print(f"   Relative Angle: {relative_angle:.1f}°")
            if range_m is not None:
                print(f"   Range: {range_m}m")
            if shots is not None:
                print(f"   Shots Detected: {shots}")
                
            # Store latest localization
            with self.lock:
                self.latest_localization = loc_data
                
            # Attempt auto-targeting using relative angle (localization has higher priority)
            if relative_angle is not None:
                additional_info = f"Range: {range_m}m, Shots: {shots}" if range_m and shots else f"Node: {node_id}"
                success = self.attempt_auto_targeting(
                    relative_angle,
                    event_type=f"PRECISE {classification.upper()}",
                    additional_info=additional_info
                )
                
                # Log precise targeting
                if success:
                    self.log_message('info', f"Precise targeting completed with ±5° accuracy")
                    print(f"   ✅ Precise targeting completed with ±5° accuracy")
            elif azimuth is not None:
                # Fallback to absolute azimuth if relative angle not available
                # Convert absolute azimuth to relative angle (azimuth)
                relative_angle_fallback = azimuth
                    
                self.log_message('warning', f"Using fallback conversion for localization: {azimuth}° -> {relative_angle_fallback}° relative")
                print(f"   Using fallback conversion: {azimuth}° -> {relative_angle_fallback}° relative")
                additional_info = f"Range: {range_m}m, Shots: {shots} (fallback)" if range_m and shots else f"Node: {node_id} (fallback)"
                success = self.attempt_auto_targeting(
                    relative_angle_fallback,
                    event_type=f"PRECISE {classification.upper()}",
                    additional_info=additional_info
                )
                    
        except Exception as e:
            self.log_message('error', f"Error in localization callback: {str(e)}")
            print(f"Error in localization callback: {str(e)}")
            if self.debug:
                traceback.print_exc()
    
    def node_status_callback(self, node_data):
        """Node status callback with logging"""
        try:
            node_id = node_data.get('node_id', 'Unknown')
            state = node_data.get('state', 'Unknown')
            temp = node_data.get('temperature')
            
            # Log node status
            self.log_message('info', f"Node status update", {
                'node_id': node_id,
                'state': state,
                'temperature': temp,
                'latitude': node_data.get('latitude'),
                'longitude': node_data.get('longitude'),
                'altitude': node_data.get('altitude'),
                'yaw': node_data.get('yaw'),
                'pitch': node_data.get('pitch'),
                'roll': node_data.get('roll'),
                'pressure': node_data.get('pressure'),
                'wind_speed': node_data.get('wind_speed'),
                'wind_direction': node_data.get('wind_direction')
            })
            
            if self.debug:
                print(f"📡 CASTLE Node {node_id} status: {state}")
                if temp is not None:
                    print(f"   Temperature: {temp:.1f}°C")
                    
            # Store latest node info
            with self.lock:
                self.latest_node_info = node_data
                
        except Exception as e:
            self.log_message('error', f"Error in node status callback: {str(e)}")
            print(f"Error in node status callback: {str(e)}")
            if self.debug:
                traceback.print_exc()
    
    def setup_socket(self):
        """Setup optimized UDP multicast socket"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            sock.bind(('', self.port))
            
            mreq = struct.pack("4sl", socket.inet_aton(self.multicast_ip), socket.INADDR_ANY)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            sock.settimeout(0.1)
            
            self.log_message('info', f"Socket created for port {self.port}")
            if self.debug:
                print(f"Socket created for port {self.port}")
            
            return sock
            
        except Exception as e:
            self.log_message('error', f"Error setting up socket: {e}")
            if self.debug:
                print(f"Error setting up socket: {e}")
            return None
    
    def extract_numeric_value(self, value):
        """Extract numeric value safely"""
        if value is None or value == 'null' or value == 'nan':
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
    
    def detect_message_type(self, message):
        """Detect message type based on JSON structure"""
        if 'node_info' in message:
            return 'node_info'
        elif 'event_detection' in message:
            return 'event_detection'
        elif 'event_localization' in message:
            return 'event_localization'
        else:
            return 'unknown'
    
    def process_node_info(self, message):
        """Process node_info messages"""
        with self.lock:
            self.stats['node_info']['messages'] += 1
        
        self.log_message('debug', f"Processing node_info message")
        self.log_raw_message('node_info', message)
        
        try:
            node_info = message.get('node_info', {})
            node = node_info.get('node', {})
            weather = node_info.get('weather', {})
            position = node.get('position', {})
            location = position.get('location', {})
            orientation = position.get('orientation', {})
            
            coordinates = location.get('coordinates', [])
            lat, lon, alt = None, None, None
            if len(coordinates) >= 2:
                lon = self.extract_numeric_value(coordinates[0])
                lat = self.extract_numeric_value(coordinates[1])
                if len(coordinates) >= 3:
                    alt = self.extract_numeric_value(coordinates[2])
            
            parsed = {
                'timestamp': datetime.now(),
                'message_type': 'node_info',
                'node_id': node.get('id'),
                'time': node.get('time'),
                'state': node.get('state'),
                'fix': position.get('fix'),
                'latitude': lat,
                'longitude': lon,
                'altitude': alt,
                'yaw': self.extract_numeric_value(orientation.get('yaw')),
                'pitch': self.extract_numeric_value(orientation.get('pitch')),
                'roll': self.extract_numeric_value(orientation.get('roll')),
                'temperature': self.extract_numeric_value(weather.get('temperature')),
                'pressure': self.extract_numeric_value(weather.get('pressure')),
                'wind_speed': self.extract_numeric_value(weather.get('wind_speed')),
                'wind_direction': self.extract_numeric_value(weather.get('wind_direction')),
                'raw': message
            }
            
            with self.lock:
                self.stats['node_info']['events'] += 1
            
            self.node_status_callback(parsed)
                        
        except Exception as e:
            self.log_message('error', f"Error processing node_info: {e}")
            if self.debug:
                print(f"Error processing node_info: {e}")
    
    def process_event_detection(self, message):
        """Process event_detection messages"""
        with self.lock:
            self.stats['event_detection']['messages'] += 1
        
        self.log_message('debug', f"Processing event_detection message")
        self.log_raw_message('event_detection', message)
        
        try:
            event = message.get('event_detection', {})
            node = event.get('node', {})
            location = event.get('location', {})
            direction = event.get('direction', {})
            orientation = event.get('orientation', {})
            
            coordinates = location.get('coordinates', [])
            lat, lon, alt = None, None, None
            if len(coordinates) >= 2:
                lon = self.extract_numeric_value(coordinates[0])
                lat = self.extract_numeric_value(coordinates[1])
                if len(coordinates) >= 3:
                    alt = self.extract_numeric_value(coordinates[2])
            
            fire_data = {
                'timestamp': datetime.now(),
                'message_type': 'event_detection',
                'time': event.get('time'),
                'event_id': event.get('id'),
                'classification': event.get('classification'),
                'level': self.extract_numeric_value(event.get('level')),
                'azimuth': self.extract_numeric_value(direction.get('azimuth')),
                'elevation': self.extract_numeric_value(direction.get('elevation')),
                'relative_angle': self.extract_numeric_value(direction.get('relative_angle')),
                'sector_angle': self.extract_numeric_value(direction.get('sector_angle')),
                'node_id': node.get('id'),
                'latitude': lat,
                'longitude': lon,
                'altitude': alt,
                'yaw': self.extract_numeric_value(orientation.get('yaw')),
                'pitch': self.extract_numeric_value(orientation.get('pitch')),
                'roll': self.extract_numeric_value(orientation.get('roll')),
                'raw': message
            }
            
            with self.lock:
                self.stats['event_detection']['events'] += 1
            
            self.fire_detection_callback(fire_data)
                        
        except Exception as e:
            self.log_message('error', f"Error processing event_detection: {e}")
            if self.debug:
                print(f"Error processing event_detection: {e}")
    
    def process_event_localization(self, message):
        """Process event_localization messages"""
        with self.lock:
            self.stats['event_localization']['messages'] += 1
        
        self.log_message('debug', f"Processing event_localization message")
        self.log_raw_message('event_localization', message)
        
        try:
            event = message.get('event_localization', {})
            node = event.get('node', {})
            location = event.get('location', {})
            direction = event.get('direction', {})
            relative_info = event.get('relative_info', {})
            
            coordinates = location.get('coordinates', [])
            lat, lon, alt = None, None, None
            if len(coordinates) >= 2:
                lon = self.extract_numeric_value(coordinates[0])
                lat = self.extract_numeric_value(coordinates[1])
                if len(coordinates) >= 3:
                    alt = self.extract_numeric_value(coordinates[2])
            
            shots_value = event.get('shots')
            shots = None
            if shots_value is not None:
                try:
                    shots = int(shots_value) if shots_value != 'null' else None
                except (ValueError, TypeError):
                    shots = None
            
            loc_data = {
                'timestamp': datetime.now(),
                'message_type': 'event_localization',
                'time': event.get('time'),
                'event_id': event.get('id'),
                'state': event.get('state'),
                'classification': event.get('classification'),
                'azimuth': self.extract_numeric_value(direction.get('azimuth')),
                'elevation': self.extract_numeric_value(direction.get('elevation')),
                'relative_angle': self.extract_numeric_value(relative_info.get('angle')),
                'range': self.extract_numeric_value(relative_info.get('range')),
                'relative_time': relative_info.get('time'),
                'shots': shots,
                'caliber': event.get('caliber'),
                'weapon': event.get('weapon'),
                'node_id': node.get('id'),
                'latitude': lat,
                'longitude': lon,
                'altitude': alt,
                'raw': message
            }
            
            with self.lock:
                self.stats['event_localization']['events'] += 1
            
            self.localization_callback(loc_data)
                        
        except Exception as e:
            self.log_message('error', f"Error processing event_localization: {e}")
            if self.debug:
                print(f"Error processing event_localization: {e}")
    
    def process_message(self, message):
        """Process message based on its type"""
        with self.lock:
            self.total_messages += 1
        
        try:
            message_type = self.detect_message_type(message)
            
            self.log_message('debug', f"Received message", {
                'message_type': message_type,
                'total_messages': self.total_messages
            })
            
            if message_type == 'node_info':
                self.process_node_info(message)
            elif message_type == 'event_detection':
                self.process_event_detection(message)
            elif message_type == 'event_localization':
                self.process_event_localization(message)
            else:
                with self.lock:
                    self.stats['unknown']['messages'] += 1
                
                self.log_message('warning', f"Unknown message type received", {
                    'message_type': message_type,
                    'raw_message': message
                })
                self.log_raw_message('unknown', message)
                    
        except Exception as e:
            self.log_message('error', f"Error processing message: {e}")
            if self.debug:
                print(f"Error processing message: {e}")
    
    def listen(self):
        """Listen on the socket"""
        socket_obj = self.setup_socket()
        
        if not socket_obj:
            self.log_message('error', "Failed to setup socket - listener cannot start")
            return
        
        self.socket = socket_obj
        
        self.log_message('critical', f"CASTLE Fire Detection System Started", {
            'multicast_ip': self.multicast_ip,
            'port': self.port,
            'auto_targeting': self.auto_targeting_enabled,
            'debug_mode': self.debug,
            'log_file': self.log_file_path
        })
        
        if self.debug:
            print(f"🎯 CASTLE Fire Detection System Started")
            print(f"   Listening on port {self.port}")
            print(f"   Auto-targeting: {'ENABLED' if self.auto_targeting_enabled else 'DISABLED'}")
            print(f"   Coordinate system: Sensor relative angle = RCWS angle")
            print(f"   Log file: {self.log_file_path}")
        
        message_count = 0
        while self.running:
            try:
                if not self.running:
                    break
                
                data, addr = socket_obj.recvfrom(8192)
                message = json.loads(data.decode('utf-8'))
                
                if message:
                    message_count += 1
                    self.process_message(message)
                
            except socket.timeout:
                continue
            except socket.error as e:
                if self.running:
                    self.log_message('error', f"Socket error: {e}")
                    if self.debug:
                        print(f"Socket error: {e}")
                break
            except Exception as e:
                if self.running:
                    self.log_message('error', f"Unexpected error: {e}")
                    if self.debug:
                        print(f"Unexpected error: {e}")
                continue
        
        try:
            socket_obj.close()
        except:
            pass
        
        self.log_message('critical', f"CASTLE listener stopped", {
            'total_messages_processed': message_count,
            'final_stats': self.stats
        })
        
        if self.debug:
            print(f"CASTLE listener stopped - processed {message_count} messages")
    
    def start_listening(self):
        """Start listening"""
        self.running = True
        self.start_time = time.time()
        
        self.log_message('info', "Starting CASTLE listener thread")
        
        thread = threading.Thread(target=self.listen)
        thread.daemon = True
        thread.start()
        self.thread = thread
    
    def stop(self):
        """Stop listener"""
        self.log_message('info', "Stopping CASTLE listener")
        self.running = False
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
    
    # GETTER FUNCTIONS FOR MAIN.PY
    def enable_auto_targeting(self):
        """Enable auto-targeting"""
        self.auto_targeting_enabled = True
        self.log_message('critical', "Auto-targeting ENABLED")
        if self.debug:
            print("🎯 CASTLE Auto-targeting ENABLED")
    
    def disable_auto_targeting(self):
        """Disable auto-targeting"""
        self.auto_targeting_enabled = False
        self.log_message('critical', "Auto-targeting DISABLED")
        if self.debug:
            print("🎯 CASTLE Auto-targeting DISABLED")
    
    def is_auto_targeting_enabled(self):
        """Check if auto-targeting is enabled"""
        return self.auto_targeting_enabled
    
    def get_latest_fire_event(self):
        """Get latest fire detection event"""
        with self.lock:
            return self.latest_fire_event
    
    def get_latest_localization(self):
        """Get latest localization event"""
        with self.lock:
            return self.latest_localization
    
    def get_latest_node_info(self):
        """Get latest node info"""
        with self.lock:
            return self.latest_node_info
    
    def get_last_targeting_timestamp(self):
        """Get timestamp of last successful targeting"""
        with self.lock:
            return self.last_targeting_timestamp
    
    def get_stats(self):
        """Get comprehensive statistics"""
        with self.lock:
            stats = {
                'total_messages': self.total_messages,
                'by_type': self.stats.copy(),
                'running': self.running,
                'auto_targeting_enabled': self.auto_targeting_enabled,
                'last_targeting': self.last_targeting_timestamp,
                'port': self.port,
                'multicast_ip': self.multicast_ip,
                'log_file': self.log_file_path
            }
            if self.start_time:
                stats['runtime_seconds'] = time.time() - self.start_time
            return stats
    
    def get_log_file_path(self):
        """Get the current log file path"""
        return self.log_file_path

# For standalone testing
if __name__ == "__main__":
    print("CASTLE Fire Detection System - Standalone Test Mode")
    
    listener = CASTLEListener(debug=True)
    listener.enable_auto_targeting()  # Enable for testing
    listener.start_listening()
    
    try:
        while True:
            time.sleep(10)
            stats = listener.get_stats()
            print(f"\n📊 STATS: {stats['total_messages']} messages, Auto-targeting: {stats['auto_targeting_enabled']}")
            print(f"📄 Log file: {stats['log_file']}")
            
    except KeyboardInterrupt:
        print("\nStopping CASTLE listener...")
        listener.stop()