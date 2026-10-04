# Importing necessary libraries
import csv
import io
import math

from PyQt5 import QtWidgets
from PyQt5.QtWidgets import (
    QWidget, QLabel, QPushButton, QComboBox, QLineEdit,
    QVBoxLayout, QHBoxLayout, QTextEdit
)
from PyQt5.QtGui import QFont , QPixmap
from PyQt5.QtCore import Qt
from matplotlib.figure import Figure

import stats_tools as st

CONFIDENCE = 0.95
ALPHA = 1 - CONFIDENCE


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
        self.data = []
        self.headers = []

        # Load CSV data and find the numeric columns
        self.load_csv_direct()
        self.numeric_columns = self.find_numeric_columns()
        self.target_column = ("App Usage Time (min/day)"
                              if "App Usage Time (min/day)" in self.numeric_columns
                              else (self.numeric_columns[0] if self.numeric_columns else ""))

        # Set up UI elements
        self.init_ui()

    # Create all UI components
    def init_ui(self):
        title = QLabel("Phone Usage Statistics")
        title.setFont(QFont("Arial", 18))
        title.setAlignment(Qt.AlignCenter)

        # Column selection
        self.column_combo = QComboBox()
        self.column_combo.addItems(self.numeric_columns)
        self.column_combo.setCurrentText(self.target_column)
        self.column_combo.currentTextChanged.connect(self.change_column)

        # Test / planning parameters
        self.mu0_input = QLineEdit("100")
        self.mu0_input.setToolTip("Hypothesised population mean used by the hypothesis test")
        self.sigma_input = QLineEdit()
        self.sigma_input.setPlaceholderText("unknown (use sample s)")
        self.sigma_input.setToolTip("Known population standard deviation. Leave empty if unknown:\n"
                                    "the confidence interval and test then use Student's t.")
        self.margin_input = QLineEdit("5")
        self.margin_input.setToolTip("Desired margin of error for the sample size estimate")

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

        # Layout for column selection and parameters
        options_layout = QHBoxLayout()
        options_layout.addWidget(QLabel("Column:"))
        options_layout.addWidget(self.column_combo, 2)
        options_layout.addWidget(QLabel("μ₀:"))
        options_layout.addWidget(self.mu0_input, 1)
        options_layout.addWidget(QLabel("σ:"))
        options_layout.addWidget(self.sigma_input, 1)
        options_layout.addWidget(QLabel("E:"))
        options_layout.addWidget(self.margin_input, 1)

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
        layout.addLayout(options_layout)
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

    # Columns whose values are all numbers (the row identifier is excluded)
    def find_numeric_columns(self):
        numeric = []
        for index, name in enumerate(self.headers):
            if name == "User ID":
                continue
            try:
                for row in self.data:
                    float(row[index])
                numeric.append(name)
            except (ValueError, IndexError):
                continue
        return numeric

    # Switch the column used by every analysis and chart
    def change_column(self, name):
        self.target_column = name
        self.image_label.clear()
        self.result_box.setText(f"Selected column: {name}")

    # Numeric values of the selected column (None + message if unavailable)
    def get_values(self):
        selected_col = self.target_column
        if selected_col not in self.headers:
            self.result_box.setText(f"Column '{selected_col}' not found in the dataset.")
            return None
        index = self.headers.index(selected_col)
        values = []
        for row in self.data:
            try:
                values.append(float(row[index]))
            except ValueError:
                continue
        if len(values) < 2:
            self.result_box.setText("Not enough numeric data in the selected column.")
            return None
        return values

    # Read a number from an input box; blank allowed only when optional
    def read_number(self, line_edit, name, optional=False, positive=False):
        text = line_edit.text().strip()
        if not text:
            if optional:
                return None
            raise ValueError(f"Please enter a value for {name}.")
        try:
            value = float(text)
        except ValueError:
            raise ValueError(f"{name} must be a number (got '{text}').")
        if positive and value <= 0:
            raise ValueError(f"{name} must be greater than 0.")
        return value

    # Perform basic statistics
    def start_analysis(self):
        values = self.get_values()
        if values is None:
            return

        try:
            # Calculate statistics
            count = len(values)
            mean = st.mean(values)
            median = st.median(values)
            variance = st.sample_variance(values)
            std_dev = math.sqrt(variance)
            std_err = std_dev / math.sqrt(count)

            # Show results
            self.result_box.setText(f"Column: {self.target_column}\n")
            self.result_box.append(f"Count: {count}")
            self.result_box.append(f"Mean: {mean:.2f}")
            self.result_box.append(f"Median: {median:.2f}")
            self.result_box.append(f"Variance: {variance:.2f}")
            self.result_box.append(f"Standard Deviation: {std_dev:.2f}")
            self.result_box.append(f"Standard Error: {std_err:.2f}")

        except Exception as e:
            self.result_box.setText(f"Error during analysis: {str(e)}")

    # Calculate confidence interval (z if σ is known, otherwise Student's t)
    def show_confidence_interval(self):
        values = self.get_values()
        if values is None:
            return

        try:
            sigma = self.read_number(self.sigma_input, "σ", optional=True, positive=True)

            # Compute interval
            n = len(values)
            mean = st.mean(values)
            if sigma is not None:
                method = "z (σ known)"
                critical = st.z_critical(CONFIDENCE)
                std_err = sigma / math.sqrt(n)
            else:
                method = f"Student's t (σ unknown, df = {n - 1})"
                critical = st.t_critical(n - 1, CONFIDENCE)
                std_err = st.sample_std(values) / math.sqrt(n)

            margin = critical * std_err
            lower = mean - margin
            upper = mean + margin

            # Display result
            self.result_box.setText(f"{CONFIDENCE:.0%} Confidence Interval for '{self.target_column}':")
            self.result_box.append(f"[{lower:.2f} , {upper:.2f}]")
            self.result_box.append(f"Margin of Error: {margin:.2f}")
            self.result_box.append(f"Method: {method}, critical value = {critical:.4f}")

        except Exception as e:
            self.result_box.setText(f"Error calculating confidence interval: {str(e)}")

    # Perform hypothesis testing (one-sample z-test if σ is known, otherwise t-test)
    def perform_hypothesis_test(self):
        values = self.get_values()
        if values is None:
            return

        try:
            hypothesized_mean = self.read_number(self.mu0_input, "μ₀")
            sigma = self.read_number(self.sigma_input, "σ", optional=True, positive=True)

            # Hypothesis test
            n = len(values)
            mean = st.mean(values)
            if sigma is not None:
                test_name = "One-sample z-test (σ known)"
                statistic_name = "Z-Score"
                statistic = (mean - hypothesized_mean) / (sigma / math.sqrt(n))
                critical = st.z_critical(CONFIDENCE)
                p_value = st.z_two_tailed_p(statistic)
            else:
                test_name = f"One-sample t-test (σ unknown, df = {n - 1})"
                statistic_name = "T-Statistic"
                statistic = (mean - hypothesized_mean) / (st.sample_std(values) / math.sqrt(n))
                critical = st.t_critical(n - 1, CONFIDENCE)
                p_value = st.t_two_tailed_p(statistic, n - 1)

            # Output results
            self.result_box.setText(f"Hypothesis Test for '{self.target_column}':")
            self.result_box.append(test_name)
            self.result_box.append(f"Null Hypothesis: μ = {hypothesized_mean:g}")
            self.result_box.append(f"Sample Mean: {mean:.2f}")
            self.result_box.append(f"{statistic_name}: {statistic:.2f}")
            self.result_box.append(f"p-value: {p_value:.4g}")
            self.result_box.append(f"Significance level: {ALPHA:.2f}")
            self.result_box.append(f"Two-tailed test (|statistic| > {critical:.4f})")

            if abs(statistic) > critical:
                self.result_box.append("Result: Reject the null hypothesis.")
            else:
                self.result_box.append("Result: Fail to reject the null hypothesis.")

        except Exception as e:
            self.result_box.setText(f"Error performing hypothesis test: {str(e)}")

    # Estimate required sample size
    def estimate_sample_size(self):
        values = self.get_values()
        if values is None:
            return

        try:
            margin_of_error = self.read_number(self.margin_input, "E", positive=True)
            sigma = self.read_number(self.sigma_input, "σ", optional=True, positive=True)
            if sigma is None:
                std_dev = st.sample_std(values)
                source = "sample standard deviation of the selected column"
            else:
                std_dev = sigma
                source = "entered σ"
            z = st.z_critical(CONFIDENCE)

            n = ((z * std_dev) / margin_of_error) ** 2
            n = math.ceil(n)

            self.result_box.setText(f"Sample Size Estimation for '{self.target_column}':")
            self.result_box.append(f"Estimated sample size needed: {n}")
            self.result_box.append(f"(Using std dev = {std_dev:.2f} from the {source}, "
                                   f"margin of error = {margin_of_error:g}, confidence = {CONFIDENCE:.0%})")

        except Exception as e:
            self.result_box.setText(f"Error calculating sample size: {str(e)}")

    # Draw and show the charts for the selected column
    def show_visual_image(self):
        values = self.get_values()
        if values is None:
            return
        try:
            pixmap = self.generate_visuals(values)
            self.image_label.setPixmap(pixmap)
            self.image_label.setScaledContents(True)
            self.result_box.setText(f"Visual plots for '{self.target_column}' displayed below.")
        except Exception as e:
            self.result_box.setText(f"Error displaying image: {str(e)}")

    # Detect outliers using IQR method
    def detect_outliers(self):
        values = self.get_values()
        if values is None:
            return

        try:
            values.sort()

            # Compute IQR and find outliers
            q1 = st.percentile(values, 0.25)
            q3 = st.percentile(values, 0.75)
            iqr = q3 - q1
            lower = q1 - 1.5 * iqr
            upper = q3 + 1.5 * iqr

            outliers = [x for x in values if x < lower or x > upper]

            # Display results
            self.result_box.setText(f"Outlier Detection for '{self.target_column}':")
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

    # Histogram + boxplot of the values, rendered in memory
    def generate_visuals(self, values):
        column = self.target_column
        figure = Figure(figsize=(10, 4))

        # Histogram
        hist = figure.add_subplot(1, 2, 1)
        hist.hist(values, bins=20, color='skyblue', edgecolor='black')
        hist.set_title(f'Histogram of {column}')
        hist.set_xlabel(column)
        hist.set_ylabel('Frequency')

        # Boxplot
        box = figure.add_subplot(1, 2, 2)
        box.boxplot(values, vert=False)
        box.set_title(f'Boxplot of {column}')
        box.set_xlabel(column)

        figure.tight_layout()
        buffer = io.BytesIO()
        figure.savefig(buffer, format="png")
        pixmap = QPixmap()
        pixmap.loadFromData(buffer.getvalue(), "PNG")
        return pixmap
