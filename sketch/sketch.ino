#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include <vector>
#include <zephyr/kernel.h>

Arduino_LED_Matrix matrix;
K_MUTEX_DEFINE(matrix_mtx);

constexpr size_t MATRIX_FRAME_WORDS = 4;

void draw(std::vector<uint32_t> frame) {
  Monitor.print("MCU draw received words: ");
  Monitor.println(frame.size());

  if (frame.size() != MATRIX_FRAME_WORDS) {
    Monitor.println("MCU draw ignored: expected 4 words");
    return;
  }

  uint32_t matrix_frame[MATRIX_FRAME_WORDS];
  for (size_t i = 0; i < MATRIX_FRAME_WORDS; i++) {
    matrix_frame[i] = frame[i];
    Monitor.print("MCU frame[");
    Monitor.print(i);
    Monitor.print("] = 0x");
    Monitor.println(matrix_frame[i], HEX);
  }

  k_mutex_lock(&matrix_mtx, K_FOREVER);
  matrix.loadFrame(matrix_frame);
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
  matrix.clear();

  Bridge.begin();

  Monitor.begin();

  Bridge.provide("draw", draw);
  Bridge.provide("clear", clear_matrix);

  Monitor.println("MCU LED matrix sketch starting");

}

void loop() {
}
