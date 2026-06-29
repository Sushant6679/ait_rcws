import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import math
import os
import sys

def get_resource_path(relative_path):
    """Get the absolute path to a resource, works for PyInstaller and development"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except AttributeError:
        # If not running as PyInstaller executable, use current directory
        base_path = os.path.abspath(os.path.dirname(__file__))
    
    return os.path.join(base_path, relative_path)

class PolynomialPredictorNSVT:
    def __init__(self, csv_file):
        # Use get_resource_path to find the CSV file
        csv_path = get_resource_path(csv_file)
        
        self.df = pd.read_csv(csv_path)
        self.model = None
        self.fit_polynomial()

    def fit_polynomial(self):
        x = self.df['Range']
        y = self.df['Elevation']
        coefficients = np.polyfit(x, y, 4)  # You can change degree here
        self.model = np.poly1d(coefficients)

    def predict(self, range_value, wind_value = 0, wind_direction = '0'):
        corrections = {}
        if self.model:
            corrections['ELEVATION'] =  round(self.model(range_value), 2)
            if wind_direction == '0':
                wind = 0
            elif wind_direction == '1':
                wind = wind_value * math.sin(math.radians(30)) * -1
            elif wind_direction == '2':
                wind = wind_value * math.sin(math.radians(60)) * -1
            elif wind_direction == '3':
                wind = wind_value * math.sin(math.radians(90)) * -1
            elif wind_direction == '4':
                wind = wind_value * math.cos(math.radians(30)) * -1
            elif wind_direction == '5':
                wind = wind_value * math.cos(math.radians(60)) * -1
            elif wind_direction == '6':
                wind = 0
            elif wind_direction == '7':
                wind = wind_value * math.sin(math.radians(30))
            elif wind_direction == '8':
                wind = wind_value * math.sin(math.radians(60))
            elif wind_direction == '9':
                wind = wind_value
            elif wind_direction == '10':
                wind = wind_value * math.cos(math.radians(30))
            elif wind_direction == '11':
                wind = wind_value * math.sin(math.radians(60))
            elif wind_direction == '12':
                wind = 0

            drift_value = self.df.loc[self.df['Range'] == range_value, 'Drift_5mps'].values[0]
            drift = (wind * drift_value) / 5
            az_corr = round(math.degrees(math.atan(drift/range_value)), 2)
            corrections['AZIMUTH'] = az_corr
        return corrections

    def print_polynomial_equation(self):
        coeffs = self.model.coefficients
        terms = [f"{coeff:.6f}x^{i}" if i > 0 else f"{coeff:.6f}" for i, coeff in enumerate(coeffs[::-1])]
        equation = " + ".join(terms[::-1])
        print(f"Elevation = {equation}")

    def plot_fit(self):
        x = self.df['Range']
        y = self.df['Elevation']
        x_fit = np.linspace(min(x), max(x), 500)
        y_fit = self.model(x_fit)

        plt.scatter(x, y, label='Data')
        plt.plot(x_fit, y_fit, color='red', label='Polynomial Fit')
        plt.xlabel('Range (m)')
        plt.ylabel('Elevation (°)')
        plt.title('Polynomial Fit: Range vs Elevation')
        plt.legend()
        plt.grid(True)
        plt.show()

# Example usage
if __name__ == "__main__":
    predictor = PolynomialPredictorNSVT('rangetableNSVT.csv')
    predictor.print_polynomial_equation()
    predictor.plot_fit()
    test_range = 1000
    predicted_elevation = predictor.predict(test_range, wind_value=10, wind_direction='3')
    print(predicted_elevation)
    # print(f"Predicted Elevation at {test_range} m: {predicted_elevation['ELEVATION']:.6f}°")
