#include "wifi_udp_server.h"
#include "servo_brake.h"
#include "motor.h"
#include "events.h"
#include "encoder.h"

WiFiUDP Udp;
uint16_t localPort;
IPAddress lastRemoteIp;
uint16_t lastRemotePort;
char packetBuffer[255]; // 接收缓冲
ESP8266WebServer httpServer(80);

// 读取一次UDP消息，若有则返回true并更新最近的客户端信息
static bool readIncomingUDP(String &msg) {
    int packetSize = Udp.parsePacket();
    if (!packetSize) return false;

    lastRemoteIp = Udp.remoteIP();
    lastRemotePort = Udp.remotePort();

    int len = Udp.read(packetBuffer, sizeof(packetBuffer) - 1);
    if (len > 0) packetBuffer[len] = '\0';
    msg = String(packetBuffer);
    msg.trim();
    return true;
}

void initWiFiHotspotUDP(const char* ssid, const char* password, uint16_t listenPort) {
    WiFi.softAP(ssid, password);
    localPort = listenPort;
    Udp.begin(localPort);

    Serial.printf("[WiFi UDP] Hotspot started. SSID=%s, Port=%u\n", ssid, localPort);
    Serial.print("[WiFi UDP] Board IP: ");
    Serial.println(WiFi.softAPIP());
}

void initHttpEchoServer() {
    httpServer.on("/echo", HTTP_ANY, []() {
        String body = httpServer.arg("plain");
        Serial.printf("[HTTP] /echo received (%d bytes): %s\n", body.length(), body.c_str());
        httpServer.send(200, "text/plain", body);
    });
    httpServer.onNotFound([]() {
        httpServer.send(404, "text/plain", "Not Found");
    });
    httpServer.begin();
    Serial.println("[HTTP] Echo server started on port 80");
}

void handleHttpServer() {
    httpServer.handleClient();
}

void handleUDPMessages() {
    String msg;
    if (!readIncomingUDP(msg)) return;

    Serial.printf("[WiFi UDP] Received from %s:%u : %s\n",
                  lastRemoteIp.toString().c_str(),
                  lastRemotePort,
                  msg.c_str());

    // 原样回显，便于上位机网络监测
    sendUDPMessageToLast(msg);

    if (msg == "Start") {
        startEventSequence();
        sendUDPMessageToLast("ACK: Start");
    } else if (msg == "Stop") {
        servoBrakeLock();
        sendUDPMessageToLast("ACK: Stop");
    } else if (msg == "Winding") {
        motorWindBack();
        sendUDPMessageToLast("ACK: Winding");
    } else {
        // 其它指令由事件等待逻辑消费
        sendUDPMessageToLast("ACK: " + msg);
    }
}

void sendUDPMessage(const IPAddress& ip, uint16_t port, const String& msg) {
    Serial.printf("[WiFi UDP] Send to %s:%u : %s\n", ip.toString().c_str(), port, msg.c_str());
    Udp.beginPacket(ip, port);
    Udp.write(msg.c_str());
    Udp.endPacket();
}

void sendUDPMessageToLast(const String& msg) {
    if (lastRemoteIp) {
        sendUDPMessage(lastRemoteIp, lastRemotePort, msg);
    }
}

void sendSignal(const String& sig) {
    sendUDPMessageToLast(sig);
    Serial.printf("[WiFi UDP] Signal sent: %s\n", sig.c_str());
}

void waitForCmd(const String& target) {
    while (true) {
        String msg;
        if (readIncomingUDP(msg)) {
            Serial.printf("[WiFi UDP] WaitForCmd got: %s\n", msg.c_str());
            if (msg == target) return;
        }
        delay(10);
    }
}

String waitForCmdAny(std::initializer_list<String> targets) {
    while (true) {
        String msg;
        if (readIncomingUDP(msg)) {
            Serial.printf("[WiFi UDP] WaitForCmdAny got: %s\n", msg.c_str());
            for (auto &t : targets) {
                if (msg == t) return msg;
            }
        }
        delay(10);
    }
}

void waitShortPull() {
    float startDist = readDistance();
    while (readDistance() < startDist + 0.5) {
        delay(10);
    }
}
