from collections import namedtuple
from functools import wraps
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

    def publish(self, topic, payload):
        self.rec("publish: %s: %s" % (topic, payload))

    def recv(self, topic, payload):
        self.on_message(self, None, FakeMsg(topic, payload))

mqtt = None
fail_keys = []


def setup_func():
    global mqtt, fail_keys
    mqtt = FakeMQTT()
    fail_keys = []


def send_to_zabbix(metrics, zabbix_host, zabbix_port):
    r = True
    fail_str = ""
    if any(m.key in fail_keys for m in metrics):
        fail_str = "FAIL: "
        r = False
    mqtt.rec("send_to_zabbix: %s%s @ %s:%d" % (fail_str, ", ".join(map(repr, metrics)),
                                               zabbix_host, zabbix_port))
    return r


def with_handler(f):
    @wraps(f)
    @with_setup(setup_func)
    @patch("wb_mqtt_zabbix.zbxsend.send_to_zabbix", send_to_zabbix)
    @patch("wb_mqtt_zabbix.util.retain_hack_topic", lambda: "/retain_hack")
    def wrap():
        handler = MQTTHandler(mqtt)
        handler.connect()
        mqtt.check(
            "connect: localhost:1883",
            "subscribe: #",
            "subscribe: /retain_hack",
            "publish: /retain_hack: 1")
        f(handler)
    return wrap


@with_handler
def test_handler(handler):
    mqtt.recv("/devices/abc/controls/def", "123")
    mqtt.recv("/devices/abc/controls/def/meta/type", "temperature")
    mqtt.check()
    mqtt.recv("/retain_hack", "1")
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', 'mqtt.lld', " +
        "'{\"data\": [{\"{#MQTTNAME}\": \"def\", " +
        "\"{#MQTTTOPIC}\": \"/devices/abc/controls/def\"}]}') @ localhost:10051",
        "send_to_zabbix: Metric('Zabbix server', " +
        "'mqtt.lld.value[/devices/abc/controls/def]', '123') @ localhost:10051")
    mqtt.recv("/devices/abc/controls/def", "45.6")
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', " +
        "'mqtt.lld.value[/devices/abc/controls/def]', '45.6') @ localhost:10051")

    mqtt.recv("/devices/abc/controls/foobar/meta/type", "temperature")
    mqtt.recv("/devices/abc/controls/foobar", "42")
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', 'mqtt.lld', " +
        "'{\"data\": [{\"{#MQTTNAME}\": \"foobar\", " +
        "\"{#MQTTTOPIC}\": \"/devices/abc/controls/foobar\"}]}') @ localhost:10051",
        "send_to_zabbix: Metric('Zabbix server', " +
        "'mqtt.lld.value[/devices/abc/controls/foobar]', '42') @ localhost:10051")
    handler.process_periodic_retries()
    mqtt.check()


@with_handler
def test_non_numeric(handler):
    mqtt.recv("/devices/abc/controls/def", "123;45;1")
    mqtt.recv("/devices/abc/controls/def/meta/type", "rgb")
    mqtt.recv("/devices/abc/controls/zzz", "1")  # skipped (pushbutton type)
    mqtt.recv("/devices/abc/controls/def/meta/type", "pushbutton")
    mqtt.check()
    mqtt.recv("/retain_hack", "1")
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', 'mqtt.lld_str', " +
        "'{\"data\": [{\"{#MQTTNAME}\": \"def\", " +
        "\"{#MQTTTOPIC}\": \"/devices/abc/controls/def\"}]}') @ localhost:10051",
        "send_to_zabbix: Metric('Zabbix server', " +
        "'mqtt.lld.str_value[/devices/abc/controls/def]', '123;45;1') @ localhost:10051")
    mqtt.recv("/devices/abc/controls/def", "1;1;1")
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', " +
        "'mqtt.lld.str_value[/devices/abc/controls/def]', '1;1;1') @ localhost:10051")
    handler.process_periodic_retries()
    mqtt.check()


@with_handler
def test_retry(handler):
    mqtt.recv("/devices/abc/controls/def", "123")
    mqtt.recv("/devices/abc/controls/def/meta/type", "temperature")
    fail_keys.append("mqtt.lld.value[/devices/abc/controls/def]")
    mqtt.recv("/retain_hack", "1")
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', 'mqtt.lld', " +
        "'{\"data\": [{\"{#MQTTNAME}\": \"def\", " +
        "\"{#MQTTTOPIC}\": \"/devices/abc/controls/def\"}]}') @ localhost:10051",
        "send_to_zabbix: FAIL: Metric('Zabbix server', " +
        "'mqtt.lld.value[/devices/abc/controls/def]', '123') @ localhost:10051")

    handler.process_periodic_retries()
    mqtt.check(
        "send_to_zabbix: FAIL: Metric('Zabbix server', " +
        "'mqtt.lld.value[/devices/abc/controls/def]', '123') @ localhost:10051")

    fail_keys.pop()
    handler.process_periodic_retries()
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', " +
        "'mqtt.lld.value[/devices/abc/controls/def]', '123') @ localhost:10051")

    handler.process_periodic_retries()
    mqtt.check()
