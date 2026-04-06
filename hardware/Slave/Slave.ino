#include <Wire.h>
#include <AccelStepper.h>
long posU = 0;
long posR = 0;
long posB = 0;
#define SLAVE_ADDR 8

#define U_STEP 4   // Z slot
#define U_DIR 7

#define R_STEP 2   // X slot
#define R_DIR 5

#define B_STEP 3   // Y slot
#define B_DIR 6

AccelStepper stepperU(AccelStepper::DRIVER, U_STEP, U_DIR);
AccelStepper stepperR(AccelStepper::DRIVER, R_STEP, R_DIR);
AccelStepper stepperB(AccelStepper::DRIVER, B_STEP, B_DIR);

String receivedCmd = "";
bool newCommand = false;
bool doneFlag = false;

void setup() {
  Wire.begin(SLAVE_ADDR);
  Wire.onReceive(receiveEvent);
  Wire.onRequest(requestEvent);

  Serial.begin(9600);

  stepperU.setMaxSpeed(400);
  stepperU.setAcceleration(200);

  stepperR.setMaxSpeed(400);
  stepperR.setAcceleration(200);

  stepperB.setMaxSpeed(400);
  stepperB.setAcceleration(200);

  Serial.println("Slave Ready");
}

void loop() {
  if (newCommand) {
    Serial.print("[SLAVE EXEC] ");
    Serial.println(receivedCmd);

    executeMove(receivedCmd);

    doneFlag = true;
    newCommand = false;
  }
}

void receiveEvent(int howMany) {
  Serial.println("I2C RECEIVED");  

  receivedCmd = "";
  while (Wire.available()) {
    char c = Wire.read();
    receivedCmd += c;
  }

  receivedCmd.trim();
  newCommand = true;
}

void requestEvent() {
  if (doneFlag) {
    Wire.write("DONE");
    doneFlag = false;
  }
}

void executeMove(String input) {

  if (input.endsWith("2")) {
    String base = input.substring(0, 1);
    executeMove(base);
    executeMove(base);
    return;
  }

  if (input == "U") move(stepperU, posU, 50);
  else if (input == "U'") move(stepperU, posU, -50);

  else if (input == "R") move(stepperR, posR, 50);
  else if (input == "R'") move(stepperR, posR, -50);

  else if (input == "B") move(stepperB, posB, 50);
  else if (input == "B'") move(stepperB, posB, -50);
}

long currentU = 0;
long currentR = 0;
long currentB = 0;

void move(AccelStepper &motor, long &pos, int step) {
  pos += step;
  motor.moveTo(pos);

  while (motor.distanceToGo() != 0) {
    motor.run();
  }
}