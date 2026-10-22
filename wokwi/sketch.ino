#include <WiFi.h>
#include <SPI.h>
#include <MFRC522.h>
#include <PubSubClient.h>

#define SS_PIN 5
#define RST_PIN 21
#define TRIG_PIN 26
#define ECHO_PIN 27

const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASS = "";
const char* MQTT_SERVER = "broker.hivemq.com";
const int MQTT_PORT = 1883;
// Altere este topico NOS DOIS LUGARES (aqui e no fluxo Node-RED) se desejar.
const char* MQTT_TOPIC = "fiap/cp03/iot/hostim2026/acessos";
const String UID_AUTORIZADO = "01020304";  // cartao azul no Wokwi

MFRC522 leitor(SS_PIN, RST_PIN);
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);
unsigned long ultimaTentativa = 0;

float lerDistancia() {
  digitalWrite(TRIG_PIN, LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long tempo = pulseIn(ECHO_PIN, HIGH, 30000UL);
  if (tempo == 0) return -1;
  return tempo * 0.0343f / 2.0f;
}

void conectarMQTT() {
  if (mqtt.connected() || WiFi.status() != WL_CONNECTED) return;
  String clientId = "fiap-cp03-" + String((uint32_t)ESP.getEfuseMac(), HEX);
  if (mqtt.connect(clientId.c_str())) {
    Serial.println("MQTT conectado!");
  } else {
    Serial.print("MQTT indisponivel, rc=");
    Serial.println(mqtt.state());
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  SPI.begin();
  leitor.PCD_Init();
  WiFi.begin(WIFI_SSID, WIFI_PASS, 6);
  Serial.print("Conectando WiFi");
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < 20000) {
    delay(400);
    Serial.print(".");
  }
  Serial.println(WiFi.status() == WL_CONNECTED ? " WiFi conectado!" : " WiFi indisponivel");
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  conectarMQTT();
  Serial.println("Pronto. Aproxime um cartao RFID.");
}

void loop() {
  static unsigned long ultimaConexao = 0;
  if (!mqtt.connected() && millis() - ultimaConexao > 5000) {
    ultimaConexao = millis();
    conectarMQTT();
  }
  mqtt.loop();
  if (!leitor.PICC_IsNewCardPresent()) return;
  if (!leitor.PICC_ReadCardSerial()) return;
  if (millis() - ultimaTentativa < 1000) {
    leitor.PICC_HaltA();
    leitor.PCD_StopCrypto1();
    return;
  }
  ultimaTentativa = millis();

  String uid = "";
  for (byte i = 0; i < leitor.uid.size; i++) {
    if (leitor.uid.uidByte[i] < 16) uid += "0";
    uid += String(leitor.uid.uidByte[i], HEX);
  }
  uid.toUpperCase();
  float distancia = lerDistancia();
  bool liberado = uid == UID_AUTORIZADO && distancia >= 0 && distancia < 30.0f;
  String resultado = liberado ? "PERMITIDO" : "NEGADO";

  // A data e hora sao registradas pela API Flask ao receber o POST.
  String distanciaJson = distancia < 0 ? "null" : String(distancia, 2);
  String payload = "{\"cartao_id\":\"" + uid + "\",\"distancia_cm\":" + distanciaJson +
                   ",\"resultado\":\"" + resultado + "\"}";
  Serial.println(payload);
  if (mqtt.connected()) {
    bool enviado = mqtt.publish(MQTT_TOPIC, payload.c_str());
    Serial.println(enviado ? "Publicado no MQTT" : "Erro ao publicar MQTT");
  } else {
    Serial.println("Nao conectado ao MQTT: tentativa nao transmitida");
  }
  leitor.PICC_HaltA();
  leitor.PCD_StopCrypto1();
  delay(300);
}
