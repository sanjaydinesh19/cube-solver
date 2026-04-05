#include <Wire.h>
#include <AccelStepper.h>

// MASTER MOTORS - Standard CNC Shield Pinout
#define X_STEP_PIN 2   // LEFT
#define X_DIR_PIN 5

#define Y_STEP_PIN 3   // FRONT (Moved from 12 to 3 to avoid Pin 13 LED conflict)
#define Y_DIR_PIN 6    // FRONT (Moved from 13 to 6)

#define Z_STEP_PIN 4   // DOWN
#define Z_DIR_PIN 7

#define ENABLE_PIN 8

AccelStepper stepperX(AccelStepper::DRIVER, X_STEP_PIN, X_DIR_PIN);
AccelStepper stepperY(AccelStepper::DRIVER, Y_STEP_PIN, Y_DIR_PIN);
AccelStepper stepperZ(AccelStepper::DRIVER, Z_STEP_PIN, Z_DIR_PIN);

long posX = 0, posY = 0, posZ = 0;
int stepUnit = 50; 
int MAX_SPEED = 400;     // Increased for better response
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
  Serial.println("Master Online. Enter: L, R, F, B, U, D");
}

void loop() {
  if (Serial.available()) {
    String input = Serial.readStringUntil('\n');
    input.trim();

    if (input == "") return;

    Serial.print("Command: ");
    Serial.println(input);

    // MASTER CONTROLS
    if (input == "L")       moveMotor(stepperX, posX, stepUnit);
    else if (input == "L'") moveMotor(stepperX, posX, -stepUnit);
    else if (input == "F")  moveMotor(stepperY, posY, stepUnit);
    else if (input == "F'") moveMotor(stepperY, posY, -stepUnit);
    else if (input == "D")  moveMotor(stepperZ, posZ, stepUnit);
    else if (input == "D'") moveMotor(stepperZ, posZ, -stepUnit);
    
    // SLAVE CONTROLS (R, B, U)
    else if (input == "R" || input == "R'" || input == "B" || 
             input == "B'" || input == "U" || input == "U'") {
      sendCommand(input);
    }
    else {
      Serial.println("Invalid Command");
    }
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
  Wire.beginTransmission(8);
  Wire.print(cmd); 
  Wire.endTransmission();
  Serial.println("Sent to Slave: " + cmd);
}