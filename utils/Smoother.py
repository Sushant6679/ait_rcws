from pydash import clamp
class JoystickSmoother:
    def __init__(self, dead_zone = 0.05, exponent = 3, alpha_slow=0.1, alpha_fast=0.5) -> None:
        self.dead_zone = dead_zone
        self.exponent = exponent
        self.alpha_slow = alpha_slow
        self.alpha_fast = alpha_fast
        self.prev_x = 0
        self.prev_y = 0
    
    def apply_dead_zone(self, x, y):
        if abs(x) < self.dead_zone:
            x = 0
        if abs(y) < self.dead_zone:
            y = 0
        return x, y

    def non_linear_scale(self, value):
        return value * self.exponent if value >= 0 else -(abs(value) * self.exponent)

    def dynamic_low_pass_filter(self, current_value, previous_value):
        delta = abs(current_value - previous_value)
        alpha = self.alpha_fast if delta > 0.5 else self.alpha_slow
        return alpha * current_value + (1 - alpha) * previous_value
    
    def get(self, joystick_x, joystick_y, pan_speed=1, tilt_speed=1):
        # Apply dead zone
        joystick_x, joystick_y = self.apply_dead_zone(joystick_x, joystick_y)
        # Apply non-linear scaling
        joystick_x = self.non_linear_scale(joystick_x)
        joystick_y = self.non_linear_scale(joystick_y)
        # Apply dynamic smoothing filter
        previous_x = self.prev_x
        previous_y = self.prev_y
        if joystick_x == 0:
            x_velocity = 0
        else:
            x_velocity = self.dynamic_low_pass_filter(joystick_x, previous_x)
            x_velocity = clamp(x_velocity, -1, 1)

        if joystick_y == 0:
            y_velocity = 0
        else:
            y_velocity = self.dynamic_low_pass_filter(joystick_y, previous_y)
            y_velocity = clamp(y_velocity, -1, 1)
        
        self.prev_x = x_velocity
        self.prev_y = y_velocity
        return x_velocity * pan_speed, y_velocity * tilt_speed