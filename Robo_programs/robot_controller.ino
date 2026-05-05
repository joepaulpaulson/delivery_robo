/*
  robot_controller.ino

  Serial protocol expected by Robo_programs/main.py at 9600 baud:
    F = drive forward
    B = drive backward
    L = turn left in place
    R = turn right in place
    S = stop motors immediately
    O = log drawer-open request
    C = log drawer-close request

  Drawer control is intentionally print-only for now so the robot can focus on
  reliable movement, room visits, waits, and return-to-base behavior.
*/

namespace Pins {
const uint8_t kLeftEnable = 5;   // PWM
const uint8_t kLeftIn1 = 7;
const uint8_t kLeftIn2 = 8;

const uint8_t kRightEnable = 6;  // PWM
const uint8_t kRightIn1 = 10;
const uint8_t kRightIn2 = 11;

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

void logDrawerAction(const __FlashStringHelper* action) {
  Serial.print(F("DRAWER:"));
  Serial.println(action);
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
      logDrawerAction(F("OPEN_REQUEST"));
      Serial.println(F("ACK:O"));
      break;
    case 'C':
      logDrawerAction(F("CLOSE_REQUEST"));
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
