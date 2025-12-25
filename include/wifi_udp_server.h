#ifndef WIFI_UDP_SERVER_H
#define WIFI_UDP_SERVER_H

#include <Arduino.h>
#include <ESP8266WiFi.h>
#include <ESP8266WebServer.h>
#include <WiFiUdp.h>
#include <initializer_list>

// 初始化热点和UDP监听
void initWiFiHotspotUDP(const char* ssid, const char* password, uint16_t listenPort);

// HTTP Echo 服务器（用于上位机测试）
void initHttpEchoServer();
void handleHttpServer();

// 循环调用，处理收到的UDP数据（Start/Stop/Winding）
void handleUDPMessages();

// 主动向某IP/端口发送消息
void sendUDPMessage(const IPAddress& ip, uint16_t port, const String& msg);

// 用于方便发送到最近一次连接的客户端
void sendUDPMessageToLast(const String& msg);

// 发送事件信号（Pain/HighDamp/LowDamp/Keep等）
void sendSignal(const String& sig);

// 阻塞等待指定指令
void waitForCmd(const String& target);
String waitForCmdAny(std::initializer_list<String> targets);

// 等待短距离拉出（用于 Continue 分支）
void waitShortPull();

#endif
