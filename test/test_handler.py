from collections import namedtuple
from nose.tools import with_setup, eq_
from mock import patch
from wb_mqtt_zabbix import MQTTHandler

FakeMsg = namedtuple("FakeMsg", ["topic", "payload"])


class FakeMQTT(object):
    def __init__(self):
        self._rec = []

    def rec(self, s):
        self._rec.append(s)

    def check(self, *items):
        eq_(list(items), self._rec)
        self._rec = []

    def connect(self, host, port):
        self.rec("connect: %s:%d" % (host, port))
        self.on_connect(self, None, 0, 0)

    def subscribe(self, topic):
        self.rec("subscribe: %s" % topic)

    def recv(self, topic, payload):
        self.on_message(self, None, FakeMsg(topic, payload))

mqtt = None


def setup_func():
    global mqtt
    mqtt = FakeMQTT()


def send_to_zabbix(metrics, zabbix_host, zabbix_port):
    mqtt.rec("send_to_zabbix: %s @ %s:%d" % (", ".join(map(repr, metrics)),
                                             zabbix_host, zabbix_port))


@with_setup(setup_func)
@patch("zbxsend.send_to_zabbix", send_to_zabbix)
def test_handler():
    handler = MQTTHandler(mqtt)
    handler.connect()
    mqtt.check("connect: localhost:1883", "subscribe: #")
    mqtt.recv("/devices/abc/controls/def", "123")
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', 'mqtt.lld', " +
        "'{\"data\": [{\"{#MQTTNAME}\": \"/devices/abc/controls/def\"}]}') @ localhost:10051",
        "send_to_zabbix: Metric('Zabbix server', " +
        "'mqtt.lld.value[/devices/abc/controls/def]', '123') @ localhost:10051")
    mqtt.recv("/devices/abc/controls/def", "45.6")
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', " +
        "'mqtt.lld.value[/devices/abc/controls/def]', '45.6') @ localhost:10051")
