# """
# Configuration File for Medical Robot Dashboard
# Centralized settings for hardware, database, and server configuration
# """

# import os

# # ==================== SERVER CONFIG ====================
# class Config:
#     SECRET_KEY = os.environ.get('SECRET_KEY') or 'medical-robot-2025-secure-key'
#     HOST = '0.0.0.0'  # Allow external access on local network
#     PORT = 5000
#     DEBUG = True  # Set to False in production
    
#     # Database
#     DATABASE_PATH = 'database/medical_robot.db'
    
#     # Camera Settings
#     CAMERA_RESOLUTION = (640, 480)  # Lower res for Pi performance
#     CAMERA_FRAMERATE = 20  # FPS
#     CAMERA_ROTATION = 0  # 0, 90, 180, or 270
    
#     # HC-05 Bluetooth Settings
#     BLUETOOTH_PORT = '/dev/rfcomm0'  # Default Linux Bluetooth serial
#     BLUETOOTH_BAUDRATE = 9600
#     BLUETOOTH_TIMEOUT = 1.0  # seconds
    
#     # Robot Physical Limits
#     BATTERY_LOW_THRESHOLD = 20  # Percentage
#     WATER_LOW_THRESHOLD = 2  # Remaining doses
#     PILLS_LOW_THRESHOLD = 3  # Remaining pills
    
#     # Alert Settings
#     HEART_RATE_MIN = 50  # BPM
#     HEART_RATE_MAX = 120  # BPM
#     SPO2_MIN = 92  # Percentage
    
#     # Schedule Settings
#     MEDICINE_TIMES = ['08:00', '14:00', '20:00']  # Daily medicine schedule
#     WATER_REMINDER_INTERVAL = 2  # Hours

# # ==================== HARDWARE PINS (for reference) ====================
# class HardwareConfig:
#     # Arduino Nano Motor Control (via Serial/I2C)
#     ARDUINO_PORT = '/dev/ttyUSB0'
#     ARDUINO_BAUDRATE = 115200
    
#     # Emergency buzzer GPIO (if connected directly to Pi)
#     BUZZER_PIN = 18
    
#     # LED Status Indicators
#     STATUS_LED_PIN = 23
#     ALERT_LED_PIN = 24



"""
Configuration File for Medical Robot Dashboard
Centralized settings for hardware, database, and server configuration
"""

import os

# ==================== SERVER CONFIG ====================
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'medical-robot-2025-secure-key'
    HOST = '127.0.0.1'  # Changed to localhost for safer Windows testing
    PORT = 5000
    DEBUG = True  # Set to False in production
    
    # Database
    # Ensure the 'database' folder exists, otherwise this might error
    DATABASE_PATH = 'database/medical_robot.db'
    
    # Camera Settings
    CAMERA_RESOLUTION = (640, 480)  # Standard webcam resolution
    CAMERA_FRAMERATE = 30  # Increased to 30 for smoother laptop webcam
    CAMERA_ROTATION = 0  # 0, 90, 180, or 270
    
    # HC-05 Bluetooth Settings
    # Changed /dev/rfcomm0 (Linux) to COM1 (Windows Placeholder)
    BLUETOOTH_PORT = 'COM1' 
    BLUETOOTH_BAUDRATE = 9600
    BLUETOOTH_TIMEOUT = 1.0  # seconds
    
    # Robot Physical Limits
    BATTERY_LOW_THRESHOLD = 20  # Percentage
    WATER_LOW_THRESHOLD = 2  # Remaining doses
    PILLS_LOW_THRESHOLD = 3  # Remaining pills
    
    # Alert Settings
    HEART_RATE_MIN = 50  # BPM
    HEART_RATE_MAX = 120  # BPM
    SPO2_MIN = 92  # Percentage
    
    # Schedule Settings
    MEDICINE_TIMES = ['08:00', '14:00', '20:00']  # Daily medicine schedule
    WATER_REMINDER_INTERVAL = 2  # Hours
    GRID_STEP_SECONDS = int(os.environ.get('GRID_STEP_SECONDS', '4'))

# ==================== HARDWARE PINS (Reference Only) ====================
class HardwareConfig:
    # Arduino Nano Motor Control (via Serial/I2C)
    # Changed /dev/ttyUSB0 (Linux) to COM2 (Windows Placeholder)
    ARDUINO_PORT = 'COM2'
    ARDUINO_BAUDRATE = 115200
    
    # Emergency buzzer GPIO (if connected directly to Pi)
    BUZZER_PIN = 18
    
    # LED Status Indicators
    STATUS_LED_PIN = 23
    ALERT_LED_PIN = 24
