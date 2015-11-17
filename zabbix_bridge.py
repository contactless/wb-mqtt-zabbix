#!/usr/bin/env python
import json
import click
import logging
import paho.mqtt.client as mqtt
from zbxsend import Metric, send_to_zabbix

PORT_VALUE = click.IntRange(1, 65535)
REG_DELAY = 1


logging.basicConfig(level=logging.DEBUG)


class MQTTHandler(object):
    def __init__(self, client, mqtt_topic, zabbix_server, zabbix_port, zabbix_host_name, **kwargs):
        self.client = client
        self.mqtt_topic = mqtt_topic
        self.zabbix_server = zabbix_server
        self.zabbix_port = zabbix_port
        self.zabbix_host_name = zabbix_host_name
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.reg_map = set()

    def send(self, key, value):
        return send_to_zabbix([Metric(self.zabbix_host_name, key, value)],
                              self.zabbix_server, self.zabbix_port)

    def on_connect(self, client, userdata, flags, rc):
        print("Connected with result code "+str(rc))
        self.client.subscribe(unicode(self.mqtt_topic).encode("utf-8"))

    def register_control(self, topic):
        print "REG: " + topic
        self.send("mqtt.lld", json.dumps(dict(data=[{"{#MQTTNAME}": topic}])))

    def send_value(self, topic, payload):
        print "SEND: %s = %s" % (topic, payload)
        # XXX problem: may fail
        self.send("mqtt.lld.value[%s]" % topic, payload)

    def on_message(self, client, userdata, msg):
        if not mqtt.topic_matches_sub("/devices/+/controls/+", msg.topic):
            return
        if msg.topic not in self.reg_map:
            self.register_control(msg.topic)
            self.reg_map.add(msg.topic)
        self.send_value(msg.topic, msg.payload)


@click.command()
@click.option("-h", "--mqtt-host", default="localhost", help="MQTT host")
@click.option("-p", "--mqtt-port", type=PORT_VALUE, default=1883, help="MQTT port")
@click.option("-t", "--mqtt-topic", default="#", help="MQTT subsctiption topic")
@click.option("-H", "--zabbix-server", default="localhost", help="Zabbix server")
@click.option("-P", "--zabbix-port", type=PORT_VALUE, default=10051, help="Zabbix port")
@click.option("-z", "--zabbix-host-name", default="Zabbix server",
              help="Host name as registered in Zabbix frontend")
def zbridge(mqtt_host, mqtt_port, **kwargs):
    """Zabbix bridge for Wiren Board."""
    client = mqtt.Client()
    MQTTHandler(client, **kwargs)
    client.connect(mqtt_host, mqtt_port)
    client.loop_forever()

if __name__ == "__main__":
    zbridge()
