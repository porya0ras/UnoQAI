#include <Arduino_LED_Matrix.h>
#include <Arduino_RouterBridge.h>

Arduino_LED_Matrix matrix;
void setup() {
     matrix.begin();
  matrix.clear();

  Bridge.begin();
}



void loop() {

    const uint32_t happy[] = {
    0x19819,
    0x80000001,
    0x81f8000
    };

    matrix.loadFrame(happy);
  delay(500);

    matrix.clear();
  delay(500);

}
