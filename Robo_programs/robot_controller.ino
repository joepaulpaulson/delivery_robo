/*
  robot_controller.ino

  Serial protocol expected by Robo_programs/main.py at 9600 baud:
    F = drive forward
    B = drive backward
    L = turn left in place
    R = turn right in place
    S = stop motors immediately
    O = open drawer
    C = close drawer

  Assumed hardware:
    - Arduino Uno/Nano
    - Dual DC motor driver (L298N/L293D-style wiring)
    - One servo for the medicine drawer

  Adjust the pin mapping, motor speeds, and drawer angles below to match
  your chassis and driver wiring.
*/

#include <Servo.h>

namespace Pins {
const uint8_t kLeftEnable = 5;   // PWM
const uint8_t kLeftIn1 = 7;
const uint8_t kLeftIn2 = 8;

const uint8_t kRightEnable = 6;  // PWM
const uint8_t kRightIn1 = 10;
const uint8_t kRightIn2 = 11;

const uint8_t kDrawerServo = 9;
const uint8_t kStatusLed = LED_BUILTIN;
}  // namespace Pins

namespace Motion {
const uint8_t kForwardSpeed = 180;
const uint8_t kBackwardSpeed = 180;
const uint8_t kTurnSpeed = 170;

// Python sends a stop after each timed command. This is a failsafe in case the
// stop byte is missed or the Pi process crashes mid-move.
const unsigned long kCommandTimeoutMs = 15000UL;
}  // namespace Motion

namespace Drawer {
const int kClosedAngle = 12;
const int kOpenAngle = 95;
const uint8_t kStepDelayMs = 12;
}  // namespace Drawer

Servo drawerServo;

char activeCommand = 'S';
unsigned long lastMotionCommandAt = 0;

void setMotor(int enablePin, int in1Pin, int in2Pin, int speedValue, bool forward) {
  speedValue = constrain(speedValue, 0, 255);
  digitalWrite(in1Pin, forward ? HIGH : LOW);
  digitalWrite(in2Pin, forward ? LOW : HIGH);
  analogWrite(enablePin, speedValue);
}

void stopMotor(int enablePin, int in1Pin, int in2Pin) {
  analogWrite(enablePin, 0);
  digitalWrite(in1Pin, LOW);
  digitalWrite(in2Pin, LOW);
}

void stopDrive() {
  stopMotor(Pins::kLeftEnable, Pins::kLeftIn1, Pins::kLeftIn2);
  stopMotor(Pins::kRightEnable, Pins::kRightIn1, Pins::kRightIn2);
  activeCommand = 'S';
  digitalWrite(Pins::kStatusLed, LOW);
}

void driveForward() {
  setMotor(Pins::kLeftEnable, Pins::kLeftIn1, Pins::kLeftIn2, Motion::kForwardSpeed, true);
  setMotor(Pins::kRightEnable, Pins::kRightIn1, Pins::kRightIn2, Motion::kForwardSpeed, true);
  activeCommand = 'F';
  lastMotionCommandAt = millis();
  digitalWrite(Pins::kStatusLed, HIGH);
}

void driveBackward() {
  setMotor(Pins::kLeftEnable, Pins::kLeftIn1, Pins::kLeftIn2, Motion::kBackwardSpeed, false);
  setMotor(Pins::kRightEnable, Pins::kRightIn1, Pins::kRightIn2, Motion::kBackwardSpeed, false);
  activeCommand = 'B';
  lastMotionCommandAt = millis();
  digitalWrite(Pins::kStatusLed, HIGH);
}

void turnLeft() {
  setMotor(Pins::kLeftEnable, Pins::kLeftIn1, Pins::kLeftIn2, Motion::kTurnSpeed, false);
  setMotor(Pins::kRightEnable, Pins::kRightIn1, Pins::kRightIn2, Motion::kTurnSpeed, true);
  activeCommand = 'L';
  lastMotionCommandAt = millis();
  digitalWrite(Pins::kStatusLed, HIGH);
}

void turnRight() {
  setMotor(Pins::kLeftEnable, Pins::kLeftIn1, Pins::kLeftIn2, Motion::kTurnSpeed, true);
  setMotor(Pins::kRightEnable, Pins::kRightIn1, Pins::kRightIn2, Motion::kTurnSpeed, false);
  activeCommand = 'R';
  lastMotionCommandAt = millis();
  digitalWrite(Pins::kStatusLed, HIGH);
}

void moveDrawerTo(int targetAngle) {
  int currentAngle = drawerServo.read();
  if (currentAngle < 0 || currentAngle > 180) {
    currentAngle = Drawer::kClosedAngle;
  }

  if (currentAngle == targetAngle) {
    drawerServo.write(targetAngle);
    return;
  }

  int step = currentAngle < targetAngle ? 1 : -1;
  for (int angle = currentAngle; angle != targetAngle; angle += step) {
    drawerServo.write(angle);
    delay(Drawer::kStepDelayMs);
  }
  drawerServo.write(targetAngle);
}

void openDrawer() {
  moveDrawerTo(Drawer::kOpenAngle);
}

void closeDrawer() {
  moveDrawerTo(Drawer::kClosedAngle);
}

void handleCommand(char command) {
  switch (command) {
    case 'F':
      driveForward();
      Serial.println(F("ACK:F"));
      break;
    case 'B':
      driveBackward();
      Serial.println(F("ACK:B"));
      break;
    case 'L':
      turnLeft();
      Serial.println(F("ACK:L"));
      break;
    case 'R':
      turnRight();
      Serial.println(F("ACK:R"));
      break;
    case 'S':
      stopDrive();
      Serial.println(F("ACK:S"));
      break;
    case 'O':
      openDrawer();
      Serial.println(F("ACK:O"));
      break;
    case 'C':
      closeDrawer();
      Serial.println(F("ACK:C"));
      break;
    default:
      Serial.print(F("ERR:UNKNOWN_COMMAND:"));
      Serial.println(command);
      break;
  }
}

void setup() {
  pinMode(Pins::kLeftEnable, OUTPUT);
  pinMode(Pins::kLeftIn1, OUTPUT);
  pinMode(Pins::kLeftIn2, OUTPUT);
  pinMode(Pins::kRightEnable, OUTPUT);
  pinMode(Pins::kRightIn1, OUTPUT);
  pinMode(Pins::kRightIn2, OUTPUT);
  pinMode(Pins::kStatusLed, OUTPUT);

  stopDrive();

  drawerServo.attach(Pins::kDrawerServo);
  closeDrawer();

  Serial.begin(9600);
  Serial.println(F("ROBOT_READY"));
}

void loop() {
  while (Serial.available() > 0) {
    char incoming = static_cast<char>(Serial.read());
    if (incoming == '\n' || incoming == '\r' || incoming == ' ') {
      continue;
    }

    if (incoming >= 'a' && incoming <= 'z') {
      incoming = incoming - 'a' + 'A';
    }

    handleCommand(incoming);
  }

  if (activeCommand != 'S' && millis() - lastMotionCommandAt > Motion::kCommandTimeoutMs) {
    stopDrive();
    Serial.println(F("SAFE_STOP:COMMAND_TIMEOUT"));
  }
}
