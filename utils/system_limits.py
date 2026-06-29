"""
System-specific motion limits for different equipment types.
This file centralizes all taboo zone limits to maintain consistency across the application.
"""

# Dictionary of system types and their corresponding motion limits
SYSTEM_LIMITS = {
    'BMG': {
        'PAN_LEFT_LIMIT': -180,
        'PAN_RIGHT_LIMIT': 180,
        'TILT_BOTTOM_LIMIT': -15,
        'TILT_TOP_LIMIT': 60
    },
    'NSVT': {
        'PAN_LEFT_LIMIT': -180,
        'PAN_RIGHT_LIMIT': 180,
        'TILT_BOTTOM_LIMIT': -7,
        'TILT_TOP_LIMIT': 75
    },
    'RCWS': {
        'PAN_LEFT_LIMIT': -180,
        'PAN_RIGHT_LIMIT': 180,
        'TILT_BOTTOM_LIMIT': -10,
        'TILT_TOP_LIMIT': 45
    }
}

# Default limits to use when system type is unknown
DEFAULT_LIMITS = {
    'PAN_LEFT_LIMIT': -180,
    'PAN_RIGHT_LIMIT': 180,
    'TILT_BOTTOM_LIMIT': -5,
    'TILT_TOP_LIMIT': 15
}

def get_system_limits(system_type):
    """
    Get the motion limits for a specific system type.
    
    Args:
        system_type (str): The type of system (BMG, NSVT, or RCWS)
        
    Returns:
        dict: A dictionary containing all the limit values for the specified system
    """
    return SYSTEM_LIMITS.get(system_type, DEFAULT_LIMITS)

# Additional help text for ConfigScreen
HELP_TEXT = {
    'left': 'Adjust the PAN left angle',
    'right': 'Adjust the PAN right angle',
    'top': 'Adjust the TILT top angle',
    'bottom': 'Adjust the TILT bottom angle'
}