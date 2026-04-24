#include <Arduino_LED_Matrix.h>
#include <Arduino_RouterBridge.h>
#include <zephyr/kernel.h>
#include <vector>

Arduino_LED_Matrix matrix;
K_MUTEX_DEFINE(matrix_mtx);

void draw(std::vector<uint8_t> frame) {
  if (frame.size() != 96) {
    return;
  }

  k_mutex_lock(&matrix_mtx, K_FOREVER);
  matrix.draw(frame.data());
  k_mutex_unlock(&matrix_mtx);
}

void clear_matrix() {
  k_mutex_lock(&matrix_mtx, K_FOREVER);
  matrix.clear();
  k_mutex_unlock(&matrix_mtx);
}

void setup() {
  matrix.begin();
  matrix.setGrayscaleBits(3);
  matrix.clear();

  Bridge.begin();
  Bridge.provide("draw", draw);
  Bridge.provide("clear", clear_matrix);
}

void loop() {
  delay(1);
}
