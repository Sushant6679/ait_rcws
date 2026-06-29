import numpy as np
import math
from numba import njit, prange
from PyQt5.QtCore import QObject, pyqtSignal
import time

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

class ProjectileSolver(QObject):
    finished = pyqtSignal()
    corr_el = pyqtSignal(object, object)

    def __init__(self, initial_velocity=840, target_x=None, target_y=None, height=None):
        super().__init__()
        self.initial_velocity = initial_velocity
        self.target_x = target_x
        self.target_y = target_y
        self.h0 = height
        self.results = []

    def calculate_angle(self, x, y):
        slope = (y) / x
        return math.degrees(math.atan(slope))

    def choose_min_angle(self, x_target):
        range_table = {
            500: 0.28, 550:0.32, 600:0.37, 650:0.42, 700:0.478, 750:0.53,
            800:0.596, 850:0.66, 900:0.736, 950:0.815, 1000:0.9, 1050:0.99,
            1100:1.08, 1150:1.18, 1200:1.28, 1250:1.389, 1300:1.5, 1350:1.61, 1400:1.73
        }

        x_target -= x_target % 10
        k = (x_target // 100) * 100
        if x_target - k > 50:
            k += 50

        if k < 500:
            return 0
        if k > 1400:
            return None
        return range_table.get(k)

    def simulate_all_angles(self, initial_velocity, height, target_x, target_y, angles):
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

    def get_closest_positive_key_by_value(self, dictionary, target_value):
        valid_items = {k: v for k, v in dictionary.items() if v >= target_value}
        if not valid_items:
            return None
        return min(valid_items, key=lambda k: valid_items[k] - target_value)

    def find_launch_angle(self):
        range_table = {
            500: 0.28, 550:0.32, 600:0.37, 650:0.42, 700:0.478, 750:0.53,
            800:0.596, 850:0.66, 900:0.736, 950:0.815, 1000:0.9, 1050:0.99,
            1100:1.08, 1150:1.18, 1200:1.28, 1250:1.389, 1300:1.5, 1350:1.61, 1400:1.73
        }
        results = []
        target_x, target_y, height = self.target_x, self.target_y, self.h0
        angle_min = round(self.calculate_angle(target_x, target_y), 2)
        print(f"[INFO] Min angle: {angle_min}")
        if angle_min is None:
            return None

        if target_y < 5:
            increment = 1
        elif target_y < 10:
            increment =  1
        elif target_y < 15:
            increment = 1.5
        elif target_y < 20:
            increment = 2
        elif target_y < 30:
            increment = 2
        else:
            increment = 2.5

        angle_max = angle_min + increment
        print(f"[INFO] Max angle: {angle_max}")
        tolerance = 0.01
        input_range = np.arange(angle_min, angle_max, tolerance)

        results = self.simulate_all_angles(self.initial_velocity, height, target_x, target_y, input_range)
        for angle, y_result in zip(input_range, results):
            if y_result != -1.0:
                self.results.append((angle, y_result))
            else:
                self.results.append(None)
                
        results = [r for r in self.results if r is not None]
        if not results:
             closest_key = min(range_table.keys(), key=lambda k: abs(k - self.target_x))
             self.corr_el.emit(self.target_x, range_table[closest_key])
             self.finished.emit()
             return
        results_dict = dict(results)
        print(self.get_closest_positive_key_by_value(results_dict, target_y) - angle_min)
        self.corr_el.emit(self.target_x, self.get_closest_positive_key_by_value(results_dict, target_y))
        self.finished.emit()


if __name__ == "__main__":
    # bal = ProjectileSolver(initial_velocity=840, target_x=500, target_y=0, height=0)
    # bal.find_launch_angle()
    range_table = {
            500: 0.28, 550:0.32, 600:0.37, 650:0.42, 700:0.478, 750:0.53,
            800:0.596, 850:0.66, 900:0.736, 950:0.815, 1000:0.9, 1050:0.99,
            1100:1.08, 1150:1.18, 1200:1.28, 1250:1.389, 1300:1.5, 1350:1.61, 1400:1.73
        }
    for rng in range_table:
        if rng < 750:
            bal = ProjectileSolver(initial_velocity=840, target_x=rng, target_y=150, height=0)
            bal.find_launch_angle()
            del bal
            print(f"Without calculations: {range_table[rng]}")