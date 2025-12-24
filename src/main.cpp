#include <Arduino.h>
#include "wifi_udp_server.h"
#include "encoder.h"
#include "servo_brake.h"
#include "motor.h"
#include "events.h"
#include "configs.h"
#include "signal_tester.h"

void setup() {
    Serial.begin(115200);
    Serial.println("[BOOT] SurgeryBox starting...");
    initWiFiHotspotUDP("surgeryBox", "12345678", 4210); // 改成UDP模式

    //initWiFiHotspot();      // 启动WiFi热点
    encoderInit();          // 初始化编码器
    servoBrakeInit();       // 初始化舵机
    motorInit();            // 初始化电机
    eventsInit();           // 加载10组随机距离数组
    signalTesterInit();
}

void loop() {
    //handleWiFiCommands();   // 检查上位机发来的指令
    handleUDPMessages();
    processEncoderEvents(); // 检查编码器距离并触发事件
    signalTesterLoop();
}
