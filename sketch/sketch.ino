#include <Arduino_LED_Matrix.h>
#include <Arduino_RouterBridge.h>
#include <vector>

Arduino_LED_Matrix matrix;

void draw(std::vector<uint8_t> frame) {
  if (frame.empty()) {
    return;
  }

  matrix.draw(frame.data());
}

void clear_matrix() {
  matrix.clear();
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
}
