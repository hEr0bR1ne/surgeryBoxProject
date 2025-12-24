#ifndef WIFI_SERVER_H
#define WIFI_SERVER_H
#include <Arduino.h>

void initWiFiHotspot();
String readCommandFromClient();
void handleWiFiCommands();
void sendSignal(String sig);
void waitForCmd(String target);
String waitForCmdAny(std::initializer_list<String> targets);
void waitShortPull();

#endif
