from machine import Pin, ADC, PWM, time_pulse_us
from umqtt.simple import MQTTClient
import network
import dht
import time


# WiFi connection to virtual network 

SSID = "Wokwi-GUEST"
PASSWORD = ""


# MQTT

MQTT_BROKER = "broker.emqx.io"
CLIENT_ID = "rana7-esp32-smartenv"

# Sensor topics
TOPIC_TEMP = b"rana7/iot/temperature"
TOPIC_HUM = b"rana7/iot/humidity"
TOPIC_LIGHT = b"rana7/iot/light"
TOPIC_MOTION = b"rana7/iot/motion"
TOPIC_DISTANCE = b"rana7/iot/distance"
TOPIC_MODE_STATUS = b"rana7/iot/mode_status"

# Control Acctuators
TOPIC_LED_CONTROL = b"rana7/iot/control/led"
TOPIC_BUZZER_CONTROL = b"rana7/iot/control/buzzer"
TOPIC_RELAY_CONTROL = b"rana7/iot/control/relay"
TOPIC_SERVO_CONTROL = b"rana7/iot/control/servo"
TOPIC_MODE_CONTROL = b"rana7/iot/control/mode"

# Threshold section
TOPIC_TEMP_THRESHOLD = b"rana7/iot/control/temp_threshold"
TOPIC_LIGHT_THRESHOLD = b"rana7/iot/control/light_threshold"
TOPIC_DISTANCE_THRESHOLD = b"rana7/iot/control/distance_threshold"


# Pins

DHT_PIN = 15
LDR_PIN = 34
PIR_PIN = 27
TRIG_PIN = 5
ECHO_PIN = 18

RED_LED_PIN = 13
GREEN_LED_PIN = 12
YELLOW_LED_PIN = 14
BUZZER_PIN = 19
RELAY_PIN = 23
SERVO_PIN = 21


# Thresholds manual fixed Average values

temp_threshold = 30
light_threshold = 1500
distance_threshold = 50

# 0 = MANUAL, 1 = AUTO
auto_mode = 0

# Manual states
manual_led_state = 0
manual_buzzer_state = 0
manual_relay_state = 0
manual_servo_angle = 0


# Sensor Setup

dht_sensor = dht.DHT22(Pin(DHT_PIN))  # for tem

ldr = ADC(Pin(LDR_PIN))   # for light level
ldr.atten(ADC.ATTN_11DB)
ldr.width(ADC.WIDTH_12BIT)  

pir = Pin(PIR_PIN, Pin.IN) # for motion 

trig = Pin(TRIG_PIN, Pin.OUT)  # for disance 
echo = Pin(ECHO_PIN, Pin.IN)
trig.value(0)


# Actuator Setup

red_led = Pin(RED_LED_PIN, Pin.OUT)
green_led = Pin(GREEN_LED_PIN, Pin.OUT)
yellow_led = Pin(YELLOW_LED_PIN, Pin.OUT)

red_led.off()
green_led.off()
yellow_led.off()

buzzer = PWM(Pin(BUZZER_PIN))
buzzer.freq(2000)
buzzer.duty(0)

relay = Pin(RELAY_PIN, Pin.OUT)
relay.off()

servo = PWM(Pin(SERVO_PIN), freq=50)


# Helper functiond to manage Acctuator work 
# validation function for servo
def servo_write(angle):
    try:
        angle = int(angle) 
    except:
        angle = 0

    if angle < 0:
        angle = 0
    if angle > 180:
        angle = 180

    min_duty = 26
    max_duty = 128
    duty = int(min_duty + (max_duty - min_duty) * angle / 180)
    servo.duty(duty)

# read distance throught Altrsonic sensor 
def read_distance():
    try:
        trig.value(0)
        time.sleep_us(2)
        trig.value(1)
        time.sleep_us(10)
        trig.value(0)

        duration = time_pulse_us(echo, 1, 30000) # calculate how much echo stills in the high mode so that we can calculate the duration 
        if duration < 0:
            return None

        return (duration * 0.0343) / 2
    except:
        return None

# connect wifi with ESP32 before connecting MQTT so we try to connect to wifi not stablish a new wifi network 
def connect_wifi():
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    wifi.connect(SSID, PASSWORD)

    print("Connecting to WiFi", end="")
    while not wifi.isconnected():
        print(".", end="")
        time.sleep(0.5)

    print("\nWiFi Connected!")
    print("IP address:", wifi.ifconfig()[0])
    return wifi


def apply_manual_outputs():
    if manual_led_state == 1:
        red_led.on()
    else:
        red_led.off()

    if manual_buzzer_state == 1:
        buzzer.duty(512)
    else:
        buzzer.duty(0)

    if manual_relay_state == 1:
        relay.on()
    else:
        relay.off()

    servo_write(manual_servo_angle)

    green_led.off() 
    yellow_led.off()

# this function takes the sensors values and compare it to thresholds and then take action according to this comparasion 
def apply_auto_outputs(temperature, light_level, motion, distance):
    # Red LED: high temperature
    if temperature > temp_threshold:
        red_led.on()
    else:
        red_led.off()

    # Yellow LED: low light
    if light_level < light_threshold:
        yellow_led.on()
    else:
        yellow_led.off()

    # Green LED: safe condition
    normal_temp = temperature <= temp_threshold
    normal_light = light_level >= light_threshold
    normal_motion = (motion == 0)
    normal_distance = (distance is None) or (distance > distance_threshold)

    if normal_temp and normal_light and normal_motion and normal_distance:
        green_led.on()
    else:
        green_led.off()

    # Buzzer: motion detected
    if motion == 1:
        buzzer.duty(512)
    else:
        buzzer.duty(0)

    # Relay: high temperature
    if temperature > temp_threshold:
        relay.on()
    else:
        relay.off()

    # Servo: object close
    if (distance is not None) and (distance < distance_threshold):
        servo_write(90)
    else:
        servo_write(0)

# this function works when ESP32 recives a MQTT messege 
def mqtt_callback(topic, msg):
    global auto_mode
    global manual_led_state, manual_buzzer_state, manual_relay_state, manual_servo_angle
    global temp_threshold, light_threshold, distance_threshold

    print("Received:", topic, msg)

    if topic == TOPIC_MODE_CONTROL:
        if msg == b"1":
            auto_mode = 1
            print("Mode = AUTO")
        elif msg == b"0":
            auto_mode = 0
            print("Mode = MANUAL")

    elif topic == TOPIC_LED_CONTROL and auto_mode == 0:
        if msg == b"1":
            manual_led_state = 1
            red_led.on()
            print("LED turned ON")
        elif msg == b"0":
            manual_led_state = 0
            red_led.off()
            print("LED turned OFF")

    elif topic == TOPIC_BUZZER_CONTROL and auto_mode == 0:
        if msg == b"1":
            manual_buzzer_state = 1
            buzzer.duty(512)
            print("Buzzer turned ON")
        elif msg == b"0":
            manual_buzzer_state = 0
            buzzer.duty(0)
            print("Buzzer turned OFF")

    elif topic == TOPIC_RELAY_CONTROL and auto_mode == 0:
        if msg == b"1":
            manual_relay_state = 1
            relay.on()
            print("Relay turned ON")
        elif msg == b"0":
            manual_relay_state = 0
            relay.off()
            print("Relay turned OFF")

    elif topic == TOPIC_SERVO_CONTROL and auto_mode == 0:
        try:
            angle = int(msg)
            manual_servo_angle = angle
            servo_write(angle)
            print("Servo moved to", angle)
        except:
            print("Invalid servo value")

    elif topic == TOPIC_TEMP_THRESHOLD:
        try:
            temp_threshold = int(msg)
            print("Temp threshold =", temp_threshold)
        except:
            print("Invalid temp threshold")

    elif topic == TOPIC_LIGHT_THRESHOLD:
        try:
            light_threshold = int(msg)
            print("Light threshold =", light_threshold)
        except:
            print("Invalid light threshold")

    elif topic == TOPIC_DISTANCE_THRESHOLD:
        try:
            distance_threshold = int(msg)
            print("Distance threshold =", distance_threshold)
        except:
            print("Invalid distance threshold")


def connect_mqtt():
    client = MQTTClient(CLIENT_ID, MQTT_BROKER)
    client.set_callback(mqtt_callback)
    client.connect()

    client.subscribe(TOPIC_LED_CONTROL)
    client.subscribe(TOPIC_BUZZER_CONTROL)
    client.subscribe(TOPIC_RELAY_CONTROL)
    client.subscribe(TOPIC_SERVO_CONTROL)
    client.subscribe(TOPIC_MODE_CONTROL)

    client.subscribe(TOPIC_TEMP_THRESHOLD)
    client.subscribe(TOPIC_LIGHT_THRESHOLD)
    client.subscribe(TOPIC_DISTANCE_THRESHOLD)

    print("Subscribed to:", TOPIC_LED_CONTROL)
    print("Subscribed to:", TOPIC_BUZZER_CONTROL)
    print("Subscribed to:", TOPIC_RELAY_CONTROL)
    print("Subscribed to:", TOPIC_SERVO_CONTROL)
    print("Subscribed to:", TOPIC_MODE_CONTROL)
    print("Subscribed to:", TOPIC_TEMP_THRESHOLD)
    print("Subscribed to:", TOPIC_LIGHT_THRESHOLD)
    print("Subscribed to:", TOPIC_DISTANCE_THRESHOLD)
    print("Connected to MQTT broker!")

    return client


# Main

wifi = connect_wifi()
servo_write(0)
client = connect_mqtt()

# this function alwys checks that everything work as planned 
while True:
    try:
        client.check_msg()

        dht_sensor.measure()
        temperature = dht_sensor.temperature()
        humidity = dht_sensor.humidity()
        light_level = ldr.read()
        motion = pir.value()
        distance = read_distance()

        if auto_mode == 1:
            apply_auto_outputs(temperature, light_level, motion, distance)
        else:
            apply_manual_outputs()

        # publish sensors
        client.publish(TOPIC_TEMP, str(temperature))
        client.publish(TOPIC_HUM, str(humidity))
        client.publish(TOPIC_LIGHT, str(light_level))
        client.publish(TOPIC_MOTION, str(motion))
        client.publish(TOPIC_MODE_STATUS, str(auto_mode))

        if distance is None:
            client.publish(TOPIC_DISTANCE, "0")
        else:
            client.publish(TOPIC_DISTANCE, str(distance))

        print("Mode:", "AUTO" if auto_mode == 1 else "MANUAL")
        print("Temperature:", temperature)
        print("Humidity:", humidity)
        print("Light:", light_level)
        print("Motion:", motion)
        print("Distance:", distance)
        print("Temp Threshold:", temp_threshold)
        print("Light Threshold:", light_threshold)
        print("Distance Threshold:", distance_threshold)
        print("----------------------")

    except Exception as e:
        print("Error:", e)

    time.sleep(1)