import math
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
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

class PolynomialPredictor:
    def __init__(self, csv_file):
        # Use get_resource_path to find the CSV file
        csv_path = get_resource_path(csv_file)
        
        # Read the CSV file
        self.df = pd.read_csv(csv_path)
        self.models = {}
        self.fit_polynomials()

    def fit_polynomials(self):
        # Fit a 4th degree polynomial for each column
        range_column = self.df['RANGE']
        y_columns = self.df.columns.difference(['RANGE'])
        for y_col in y_columns:
            y_values = self.df[y_col]
            coefficients = np.polyfit(range_column, y_values, 3)
            polynomial = np.poly1d(coefficients)
            self.models[y_col] = polynomial

    def predict_internal(self, range_value):
        predictions = {}
        for y_col, model in self.models.items():
            predictions[y_col] = model(range_value)
        return predictions
    
    def predict(self, range_value, wind_value=0, wind_direction='0'):
        predictions = self.predict_internal(range_value)
        ans = {}
        ans['ELEVATION'] = math.degrees(predictions['ELEVATION'] * 0.001)
        
        if wind_direction == '0' or wind_value == 0:
            wind = 0  # No wind adjustment if direction is 0 or speed is 0
        elif wind_direction in ["3", "9"]:
            wind = predictions['3,9']
        elif wind_direction in ["2", "4", "8", "10"]:
            wind = predictions['2,4,8,10']
        elif wind_direction in ["1", "5", "7", "11"]:
            wind = predictions['1,5,7,11']
        else:
            wind = 0  # Default case if direction is not recognized
        
        wind = 3.6 * wind_value * wind / 15
        if wind_direction in ["3", "1", "2", "4", "5"]:
            wind = -wind
        
        ans['AZIMUTH'] = math.degrees(wind * 0.001)
        ans['TIME'] = predictions['TIME']
        ans['WIDTH'] = predictions['WIDTH']
        ans['LENGTH'] = predictions['LENGTH']
        return ans

    def print_polynomial_equations(self):
        for y_col, model in self.models.items():
            coeffs = model.coefficients
            equation_terms = [f"{coeff:.4f}x^{i}" if i > 0 else f"{coeff:.4f}" for i, coeff in enumerate(coeffs[::-1])]
            equation = " + ".join(equation_terms[::-1])
            print(f"{y_col} polynomial equation: y = {equation}")

    def plot_all_polynomial_fits(self):
        range_column = self.df['RANGE']
        y_columns = self.df.columns.difference(['RANGE'])

        # Generate a range of x values for plotting the polynomial curves
        x_plot = np.linspace(min(range_column), max(range_column), 500)

        # Create subplots
        fig, axes = plt.subplots(len(y_columns), 1, figsize=(10, len(y_columns) * 5))
        fig.suptitle('4th Degree Polynomial Fits for All Columns')

        # Plot each column
        for ax, y_col in zip(axes, y_columns):
            if y_col not in self.models:
                print(f"No model found for {y_col}")
                continue

            model = self.models[y_col]
            y_values = self.df[y_col]
            y_plot = model(x_plot)

            # Plot the original data
            ax.scatter(range_column, y_values, label='Data Points')

            # Plot the polynomial curve
            ax.plot(x_plot, y_plot, color='red', label=f'Polynomial Fit for {y_col}')

            ax.set_xlabel('RANGE')
            ax.set_ylabel(y_col)
            ax.legend()

        plt.tight_layout(rect=[0, 0, 1, 0.96])
        plt.show()

# Example usage
if __name__ == "__main__":
    predictor = PolynomialPredictor('rangetable.csv')
    predictor.fit_polynomials()
    predictor.print_polynomial_equations()
    predictor.plot_all_polynomial_fits()
    range_value = 1000
    wind = 15
    wind_directoin = '3'
    predictions = predictor.predict(range_value, wind, wind_directoin)
    for y_col, prediction in predictions.items():
        print(f"The predicted {y_col} for range {range_value} is: {prediction}")