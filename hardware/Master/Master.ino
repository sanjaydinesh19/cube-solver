#include <Wire.h>
#include <AccelStepper.h>

// MASTER MOTORS - Standard CNC Shield Pinout
#define X_STEP_PIN 2   // LEFT
#define X_DIR_PIN 5

#define Y_STEP_PIN 3   // FRONT
#define Y_DIR_PIN 6

#define Z_STEP_PIN 4   // DOWN
#define Z_DIR_PIN 7

#define ENABLE_PIN 8

#define SLAVE_ADDR 8

AccelStepper stepperX(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepperY(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);
AccelStepper stepperZ(AccelStepper::DRIVER, Z_STEP_PIN, Z_DIR_PIN);

long posX = 0, posY = 0, posZ = 0;

int stepUnit = 50; 
int MAX_SPEED = 400;
int ACCEL = 200;

void setup() {
  Wire.begin(); 

  pinMode(ENABLE_PIN, OUTPUT);
  digitalWrite(ENABLE_PIN, LOW);

  stepperX.setMaxSpeed(MAX_SPEED);
  stepperX.setAcceleration(ACCEL);
  stepperY.setMaxSpeed(MAX_SPEED);
  stepperY.setAcceleration(ACCEL);
  stepperZ.setMaxSpeed(MAX_SPEED);
  stepperZ.setAcceleration(ACCEL);

  Serial.begin(9600);
  Serial.println("Master Ready");
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input == "") return;

    Serial.print("[MASTER RECEIVED] ");
    Serial.println(input);

    executeMove(input);

    Serial.println("DONE");  
  }
}

// Execute Move
void executeMove(String input) {

  // HANDLE "2" MOVES
  if (input.endsWith("2")) {
    String base = input.substring(0, 1);
    executeMove(base);
    executeMove(base);
    return;
  }

  // MASTER MOVES
  if (input == "L")       moveMotor(stepperX, posX, stepUnit);
  else if (input == "L'") moveMotor(stepperX, posX, -stepUnit);

  else if (input == "F")  moveMotor(stepperY, posY, stepUnit);
  else if (input == "F'") moveMotor(stepperY, posY, -stepUnit);

  else if (input == "D")  moveMotor(stepperZ, posZ, stepUnit);
  else if (input == "D'") moveMotor(stepperZ, posZ, -stepUnit);

  // SLAVE MOVES
  else if (input == "R" || input == "R'" ||
           input == "B" || input == "B'" ||
           input == "U" || input == "U'") {

    sendCommand(input);
    waitForSlave(); 
  }
  else {
    Serial.println("Invalid Command");
  }
}


void moveMotor(AccelStepper &motor, long &position, int step) {
  position += step;
  motor.moveTo(position);

  while (motor.distanceToGo() != 0) {
    motor.run();
  }
}

void sendCommand(String cmd) {
  Wire.beginTransmission(SLAVE_ADDR);
  Wire.print(cmd);
  Wire.endTransmission();

  Serial.println("[MASTER → SLAVE] " + cmd);
}


void waitForSlave() {
  while (true) {
    delay(5);

    Wire.requestFrom(SLAVE_ADDR, 4);

    String response = "";

    while (Wire.available()) {
      char c = Wire.read();
      response += c;
    }

    response.trim();

    if (response == "DONE") {
      Serial.println("[SLAVE DONE]");
      break;
    }
  }
}