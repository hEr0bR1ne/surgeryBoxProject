#include "signal_tester.h"
#include "wifi_udp_server.h"
#include <Arduino.h>

String serialInputBuffer = "";

void signalTesterInit() {
    Serial.println("[SignalTester] Ready. Type a message in Serial Monitor to send via WiFi.");
    Serial.println("[SignalTester] Example: Pain / OK1 / Start");
}

void signalTesterLoop() {
    while (Serial.available()) {
        char c = Serial.read();

        // 如果输入的是回车或换行，则发送
        if (c == '\n' || c == '\r') {
            if (serialInputBuffer.length() > 0) {
                sendUDPMessageToLast(serialInputBuffer); // UDP发给最近的客户端
                Serial.printf("[SignalTester] Sent: %s", serialInputBuffer.c_str());
                serialInputBuffer = "";
            }
        } else {
            // 累加到缓冲区
            serialInputBuffer += c;
        }
    }
}
