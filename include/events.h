#ifndef EVENTS_H
#define EVENTS_H

void eventsInit();
void startEventSequence();
void processEncoderEvents();
// 测试用：在不依赖实际拉线的情况下模拟完整流程
void runTestFlow();

#endif
