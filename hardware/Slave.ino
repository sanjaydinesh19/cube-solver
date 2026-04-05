#include <Wire.h>
#include <AccelStepper.h>

// SLAVE MOTORS - Pins 2,3,4 (Step) and 5,6,7 (Dir)
#define X_STEP_PIN 2   // RIGHT
#define X_DIR_PIN 5
#define Y_STEP_PIN 3   // BACK
#define Y_DIR_PIN 6
#define Z_STEP_PIN 4   // UP
#define Z_DIR_PIN 7

#define ENABLE_PIN 8

AccelStepper stepperX(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepperY(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);
AccelStepper stepperZ(AccelStepper::DRIVER, Z_STEP_PIN, Z_DIR_PIN);

long posX = 0, posY = 0, posZ = 0;
int stepUnit = 50;

volatile bool newCommand = false;
String command = "";

void setup() {
  Wire.begin(8);
  Wire.onReceive(receiveEvent);

  pinMode(ENABLE_PIN, OUTPUT);
  digitalWrite(ENABLE_PIN, LOW);

  stepperX.setMaxSpeed(400);
  stepperX.setAcceleration(200);
  stepperY.setMaxSpeed(400);
  stepperY.setAcceleration(200);
  stepperZ.setMaxSpeed(400);
  stepperZ.setAcceleration(200);

  Serial.begin(9600);
  Serial.println("Slave Online");
}

void loop() {
  if (newCommand) {
    Serial.println("Executing: " + command);

    if (command == "R")       moveMotor(stepperX, posX, stepUnit);
    else if (command == "R'") moveMotor(stepperX, posX, -stepUnit);
    else if (command == "B")  moveMotor(stepperY, posY, stepUnit);
    else if (command == "B'") moveMotor(stepperY, posY, -stepUnit);
    else if (command == "U")  moveMotor(stepperZ, posZ, stepUnit);
    else if (command == "U'") moveMotor(stepperZ, posZ, -stepUnit);

    command = ""; // Clear string
    newCommand = false;
  }
}

void receiveEvent(int bytes) {
  command = "";
  while (Wire.available()) {
    char c = Wire.read();
    command += c;
  }
  command.trim();
  newCommand = true;
}

void moveMotor(AccelStepper &motor, long &position, int step) {
  position += step;
  motor.moveTo(position);
  while (motor.distanceToGo() != 0) {
    motor.run();
  }
}