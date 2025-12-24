#include <Arduino.h>
#include "events.h"
#include "config.h"
#include "encoder.h"
#include "servo_brake.h"
#include "wifi_udp_server.h"

float distanceArrays[10][4];
float currentArray[4];
bool sequenceRunning = false;

void eventsInit() {
    // 初始化10组随机距离（这里只是示例）
    for(int i=0;i<10;i++){
        distanceArrays[i][0] = random(5,15); // Pain距离
        distanceArrays[i][1] = random(15,25); // Pain2距离
        distanceArrays[i][2] = random(25,35); // HighDamp距离
        distanceArrays[i][3] = random(35,45); // LowDamp距离
    }
}

void startEventSequence() {
    int idx = random(0,10);
    for(int i=0;i<4;i++){
        currentArray[i] = distanceArrays[idx][i];
    }
    sequenceRunning = true;
    Serial.printf("[EVENT] Sequence started: Array #%d", idx);
}

void processEncoderEvents() {
    if(!sequenceRunning) return;
    float dist = readDistance();

    if(dist >= currentArray[0]) sendUDPMessageToLast("Pain");
    if(dist >= currentArray[1]) sendUDPMessageToLast("Pain2");
    if(dist >= currentArray[2]) {
        sendUDPMessageToLast("HighDamp");
        servoBrakeLock();
        waitForCmd("OK");
        servoBrakeRelease();
    }
    if(dist >= currentArray[3]) {
        sendUDPMessageToLast("LowDamp");
        servoBrakeWeak();
        String cmd = waitForCmdAny({"OK1","Continue"});
        if(cmd == "OK1") {
            servoBrakeRelease();
        } else if(cmd == "Continue") {
            waitShortPull();
            sendUDPMessageToLast("Keep");
            waitForCmd("OK2");
            servoBrakeRelease();
        }
    }
}
