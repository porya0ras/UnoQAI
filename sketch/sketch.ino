#include <Arduino_LED_Matrix.h>
#include <Arduino_Monitor.h>
#include <Arduino_RouterBridge.h>
#include <zephyr/kernel.h>
#include <vector>

Arduino_LED_Matrix matrix;
K_MUTEX_DEFINE(matrix_mtx);

void draw(std::vector<uint8_t> frame) {
  Monitor.print("MCU draw received bytes: ");
  Monitor.println(frame.size());

  if (frame.size() != 96) {
    Monitor.println("MCU draw ignored: expected 96 bytes");
    return;
  }

  k_mutex_lock(&matrix_mtx, K_FOREVER);
  matrix.draw(frame.data());
  k_mutex_unlock(&matrix_mtx);

  Monitor.println("MCU draw completed");
}

void clear_matrix() {
  Monitor.println("MCU clear received");

  k_mutex_lock(&matrix_mtx, K_FOREVER);
  matrix.clear();
  k_mutex_unlock(&matrix_mtx);

  Monitor.println("MCU clear completed");
}

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);
  matrix.clear();

  Monitor.begin();
  Monitor.println("MCU LED matrix sketch starting");

  Bridge.begin();
  Bridge.provide("draw", draw);
  Bridge.provide("clear", clear_matrix);

  Monitor.println("MCU Bridge providers ready: draw, clear");
}

void loop() {
  delay(1);
}
