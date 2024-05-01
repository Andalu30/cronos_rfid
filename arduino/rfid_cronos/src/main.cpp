#include <Arduino.h>
#include <SPI.h>
#include <MFRC522.h>


#define RST_PIN 9
#define SS_PIN 10
#define IRQ_PIN 2 //Not user for now
MFRC522 mfrc522(SS_PIN, RST_PIN);


void setup() {
  // put your setup code here, to run once:
  Serial.begin(115200);
  SPI.begin();
  mfrc522.PCD_Init();
  Serial.println("RFID initialized");
}

/**
 * Helper routine to dump a byte array as hex values to Serial.
 */
void dump_byte_array(byte *buffer, byte bufferSize) {
  for (byte i = 0; i < bufferSize; i++) {
    Serial.print(buffer[i] < 0x10 ? " 0" : " ");
    Serial.print(buffer[i], HEX);
  }
}

void loop() {
  // put your main code here, to run repeatedly:

  // Reset the loop if no new card present on the sensor/reader. This saves the entire process when idle.
	if ( ! mfrc522.PICC_IsNewCardPresent()) {
		return;
	}

	// // Select one of the cards
	if ( ! mfrc522.PICC_ReadCardSerial()) {
		return;
	}

	// Dump debug info about the card;
	mfrc522.PICC_DumpDetailsToSerial(&(mfrc522.uid));
  mfrc522.PICC_HaltA();
}