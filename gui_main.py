# Importing necessary libraries
import csv
import math

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton,
    QVBoxLayout, QHBoxLayout, QTextEdit
)
from PyQt5.QtGui import QFont , QPixmap
from PyQt5.QtCore import Qt
import matplotlib.pyplot as plt


# Main window class
class MainWindow(QWidget):
    def __init__(self):
        super().__init__()

        # Set window settings
        self.setWindowTitle("Phone Usage Stats")
        self.setGeometry(100, 100, 1000, 750)
        self.setMinimumSize(1000, 750)
        self.setStyleSheet("background-color: #f0f0f0;")


        # Set background image
        photo = QtWidgets.QLabel(self)
        image_path = 'x.jpeg'
        p = QPixmap(image_path).scaled(self.width(), self.height())
        photo.setPixmap(p)
        photo.setGeometry(0, 0, self.width(), self.height())
        photo.lower()

        # Initialize variables
        self.target_column = "App Usage Time (min/day)"
        self.data = []
        self.headers = []

        # Load CSV data
        self.load_csv_direct()

        # load Data Visualization function
        self.generate_visuals()


        # Set up UI elements
        self.init_ui()

    # Create all UI components
    def init_ui(self):
        title = QLabel("Phone Usage Statistics")
        title.setFont(QFont("Arial", 18))
        title.setAlignment(Qt.AlignCenter)

        # Buttons for different actions
        self.analyze_button = QPushButton("Start Analysis")
        self.analyze_button.clicked.connect(self.start_analysis)

        self.ci_button = QPushButton("Confidence Interval")
        self.ci_button.clicked.connect(self.show_confidence_interval)

        self.hypothesis_button = QPushButton("Hypothesis Test")
        self.hypothesis_button.clicked.connect(self.perform_hypothesis_test)

        self.sample_size_button = QPushButton("Sample Size Estimation")
        self.sample_size_button.clicked.connect(self.estimate_sample_size)

        self.outlier_button = QPushButton("Detect Outliers")
        self.outlier_button.clicked.connect(self.detect_outliers)

        self.visuals_button = QPushButton("Show Visuals")
        self.visuals_button.clicked.connect(self.show_visual_image)

        self.image_label = QLabel()
        self.image_label.setScaledContents(True)
        self.image_label.setFixedHeight(350)

        self.result_box = QTextEdit()
        self.result_box.setReadOnly(True)

        # Layout for buttons
        top_layout = QHBoxLayout()
        top_layout.addWidget(self.analyze_button)
        top_layout.addWidget(self.ci_button)
        top_layout.addWidget(self.hypothesis_button)
        top_layout.addWidget(self.sample_size_button)
        top_layout.addWidget(self.visuals_button)
        top_layout.addWidget(self.outlier_button)

        # Main layout
        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(top_layout)
        layout.addWidget(self.result_box)
        layout.addWidget(self.image_label)

        self.setLayout(layout)

    # Load CSV data from file
    def load_csv_direct(self):
        try:
            with open("user_behavior_dataset.csv", newline='', encoding='utf-8') as file:
                reader = csv.reader(file)
                self.headers = next(reader)
                self.data = list(reader)
        except Exception as e:
            print("Error loading file:", str(e))

    # Perform basic statistics
    def start_analysis(self):
        selected_col = self.target_column
        if selected_col not in self.headers:
            self.result_box.setText(f"Column '{selected_col}' not found in the dataset.")
            return

        try:
            index = self.headers.index(selected_col)
            values = []
            for row in self.data:
                try:
                    value = float(row[index])
                    values.append(value)
                except ValueError:
                    continue

            if not values:
                self.result_box.setText("No numeric data found in the selected column.")
                return

            # Calculate statistics
            count = len(values)
            mean = sum(values) / count
            sorted_vals = sorted(values)
            median = sorted_vals[count // 2] if count % 2 == 1 else \
                (sorted_vals[count // 2 - 1] + sorted_vals[count // 2]) / 2
            variance = sum((x - mean) ** 2 for x in values) / (count - 1)
            std_dev = math.sqrt(variance)
            std_err = std_dev / math.sqrt(count)

            # Show results
            self.result_box.setText(f"Column: {selected_col}\n")
            self.result_box.append(f"Count: {count}")
            self.result_box.append(f"Mean: {mean:.2f}")
            self.result_box.append(f"Median: {median:.2f}")
            self.result_box.append(f"Variance: {variance:.2f}")
            self.result_box.append(f"Standard Deviation: {std_dev:.2f}")
            self.result_box.append(f"Standard Error: {std_err:.2f}")

        except Exception as e:
            self.result_box.setText(f"Error during analysis: {str(e)}")

    # Calculate confidence interval
    def show_confidence_interval(self):
        selected_col = self.target_column
        if selected_col not in self.headers:
            self.result_box.setText(f"Column '{selected_col}' not found in the dataset.")
            return

        try:
            index = self.headers.index(selected_col)
            values = []
            for row in self.data:
                try:
                    value = float(row[index])
                    values.append(value)
                except ValueError:
                    continue

            if not values:
                self.result_box.setText("No numeric data found in the selected column.")
                return

            # Compute interval
            n = len(values)
            mean = sum(values) / n
            std_dev = math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1))
            std_err = std_dev / math.sqrt(n)

            z = 1.96
            margin = z * std_err
            lower = mean - margin
            upper = mean + margin

            # Display result
            self.result_box.setText(f"95% Confidence Interval for '{selected_col}':")
            self.result_box.append(f"[{lower:.2f} , {upper:.2f}]")
            self.result_box.append(f"Margin of Error: {margin:.2f}")

        except Exception as e:
            self.result_box.setText(f"Error calculating confidence interval: {str(e)}")

    # Perform hypothesis testing
    def perform_hypothesis_test(self):
        selected_col = self.target_column
        if selected_col not in self.headers:
            self.result_box.setText(f"Column '{selected_col}' not found in the dataset.")
            return

        try:
            index = self.headers.index(selected_col)
            values = []
            for row in self.data:
                try:
                    value = float(row[index])
                    values.append(value)
                except ValueError:
                    continue

            if not values:
                self.result_box.setText("No numeric data found in the selected column.")
                return

            # Hypothesis test
            n = len(values)
            mean = sum(values) / n
            hypothesized_mean = 100.0
            std_dev = math.sqrt(sum((x - mean) ** 2 for x in values) / (n - 1))
            std_err = std_dev / math.sqrt(n)
            z = (mean - hypothesized_mean) / std_err

            # Output results
            self.result_box.setText(f"Hypothesis Test for '{selected_col}':")
            self.result_box.append(f"Null Hypothesis: μ = {hypothesized_mean}")
            self.result_box.append(f"Sample Mean: {mean:.2f}")
            self.result_box.append(f"Z-Score: {z:.2f}")
            self.result_box.append("Significance level: 0.05")
            self.result_box.append("Two-tailed test (|z| > 1.96)")

            if abs(z) > 1.96:
                self.result_box.append("Result: Reject the null hypothesis.")
            else:
                self.result_box.append("Result: Fail to reject the null hypothesis.")

        except Exception as e:
            self.result_box.setText(f"Error performing hypothesis test: {str(e)}")

    # Estimate required sample size
    def estimate_sample_size(self):
        try:
            std_dev = 50  # estimated value
            margin_of_error = 5
            z = 1.96  # for 95% confidence

            n = ((z * std_dev) / margin_of_error) ** 2
            n = math.ceil(n)

            self.result_box.setText("Sample Size Estimation:")
            self.result_box.append(f"Estimated sample size needed: {n}")
            self.result_box.append(f"(Using std dev = {std_dev}, margin of error = {margin_of_error}, confidence = 95%)")

        except Exception as e:
            self.result_box.setText(f"Error calculating sample size: {str(e)}")

    # Show saved visual image
    def show_visual_image(self):
        try:
            pixmap = QPixmap("Visualization.png")
            self.image_label.setPixmap(pixmap)
            self.image_label.setScaledContents(True)
            self.result_box.setText("Visual plots displayed below.")
        except Exception as e:
            self.result_box.setText(f"Error displaying image: {str(e)}")

    # Detect outliers using IQR method
    def detect_outliers(self):
        selected_col = self.target_column
        if selected_col not in self.headers:
            self.result_box.setText(f"Column '{selected_col}' not found in the dataset.")
            return

        try:
            index = self.headers.index(selected_col)
            values = []
            for row in self.data:
                try:
                    value = float(row[index])
                    values.append(value)
                except ValueError:
                    continue

            if not values:
                self.result_box.setText("No numeric data found.")
                return

            values.sort()
            n = len(values)

            # Calculate percentiles
            def get_percentile(p):
                k = (n - 1) * p
                f = int(k)
                c = min(f + 1, n - 1)
                return values[f] + (values[c] - values[f]) * (k - f)

            # Compute IQR and find outliers
            q1 = get_percentile(0.25)
            q3 = get_percentile(0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            outliers = [x for x in values if x < lower or x > upper]

            # Display results
            self.result_box.setText(f"Outlier Detection for '{selected_col}':")
            self.result_box.append(f"Q1: {q1:.2f}")
            self.result_box.append(f"Q3: {q3:.2f}")
            self.result_box.append(f"IQR: {iqr:.2f}")
            self.result_box.append(f"Lower Bound: {lower:.2f}")
            self.result_box.append(f"Upper Bound: {upper:.2f}")
            self.result_box.append(f"Number of Outliers: {len(outliers)}")

            if outliers:
                self.result_box.append("Example Outliers: " + ", ".join(f"{x:.1f}" for x in outliers[:5]))

        except Exception as e:
            self.result_box.setText(f"Error detecting outliers: {str(e)}")

    def generate_visuals(self):
            selected_col = self.target_column
            if selected_col not in self.headers:
                return

            try:
                index = self.headers.index(selected_col)
                values = []
                for row in self.data:
                    try:
                        value = float(row[index])
                        values.append(value)
                    except ValueError:
                        continue

                if not values:
                    return

                plt.figure(figsize=(10, 4))

                # Histogram
                plt.subplot(1, 2, 1)
                plt.hist(values, bins=20, color='skyblue', edgecolor='black')
                plt.title('Histogram of App Usage Time')
                plt.xlabel('Minutes per Day')
                plt.ylabel('Frequency')

                # Boxplot
                plt.subplot(1, 2, 2)
                plt.boxplot(values, vert=False)
                plt.title('Boxplot of App Usage Time')
                plt.xlabel('Minutes per Day')

                # Save the figure
                plt.tight_layout()
                plt.savefig("Visualization.png")
                plt.close()

            except Exception as e:
                print("Error generating visuals:", str(e))


