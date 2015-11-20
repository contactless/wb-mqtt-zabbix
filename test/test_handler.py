from collections import namedtuple
from functools import wraps
from nose.tools import with_setup, eq_
from mock import patch
from wb_mqtt_zabbix import MQTTHandler

START_TIME = 1447974674
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
handler = None
current_time = 0


def setup_func():
    global mqtt, fail_keys, handler, current_time
    mqtt = FakeMQTT()
    fail_keys = []
    handler = None
    current_time = START_TIME


def elapse(seconds):
    global current_time
    current_time += seconds


def send_to_zabbix(metrics, zabbix_host, zabbix_port):
    r = True
    fail_str = ""
    if any(m.key in fail_keys for m in metrics):
        fail_str = "FAIL: "
        r = False
    mqtt.rec("send_to_zabbix: %s%s @ %s:%d" % (fail_str, ", ".join(map(repr, metrics)),
                                               zabbix_host, zabbix_port))
    return r


def with_handler(f=None, **kwargs):
    def do_wrap(f):
        @wraps(f)
        @with_setup(setup_func)
        @patch("wb_mqtt_zabbix.zbxsend.send_to_zabbix", send_to_zabbix)
        @patch("wb_mqtt_zabbix.util.retain_hack_topic", lambda: "/retain_hack")
        @patch("time.time", lambda: current_time)
        def wrap():
            global handler
            handler = MQTTHandler(mqtt, retry_interval=5, **kwargs)
            handler.connect()
            mqtt.check(
                "connect: localhost:1883",
                "subscribe: #",
                "subscribe: /retain_hack",
                "publish: /retain_hack: 1")
            f()
        return wrap
    if callable(f):
        return do_wrap(f)
    else:
        return do_wrap


def check_reg(name, value, send_fail=False):
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', 'mqtt.lld', " +
        "'{\"data\": [{\"{#MQTTNAME}\": \"abc / %s\", " % name +
        "\"{#MQTTTOPIC}\": \"/devices/abc/controls/%s\"}]}') @ localhost:10051" % name,
        "send_to_zabbix: %sMetric('Zabbix server', " % ("FAIL: " if send_fail else "") +
        "'mqtt.lld.value[/devices/abc/controls/%s]', '%s') @ localhost:10051" % (name, value))


def check_reg_str(name, value, send_fail=False):
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', 'mqtt.lld_str', " +
        "'{\"data\": [{\"{#MQTTNAME}\": \"abc / %s\", " % name +
        "\"{#MQTTTOPIC}\": \"/devices/abc/controls/%s\"}]}') @ localhost:10051" % name,
        "send_to_zabbix: %sMetric('Zabbix server', " % ("FAIL: " if send_fail else "") +
        "'mqtt.lld.str_value[/devices/abc/controls/%s]', '%s') @ localhost:10051" % (name, value))


def check_send(name, value):
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', " +
        "'mqtt.lld.value[/devices/abc/controls/%s]', '%s') @ localhost:10051" % (name, value))


def check_send_fail(name, value):
    mqtt.check(
        "send_to_zabbix: FAIL: Metric('Zabbix server', " +
        "'mqtt.lld.value[/devices/abc/controls/%s]', '%s') @ localhost:10051" % (name, value))


def check_send_str(name, value):
    mqtt.check(
        "send_to_zabbix: Metric('Zabbix server', " +
        "'mqtt.lld.str_value[/devices/abc/controls/%s]', '%s') @ localhost:10051" % (name, value))


@with_handler
def test_handler():
    mqtt.recv("/devices/abc/controls/def", "123")
    mqtt.recv("/devices/abc/controls/def/meta/type", "temperature")
    mqtt.check()
    mqtt.recv("/retain_hack", "1")
    check_reg("def", "123")
    mqtt.recv("/devices/abc/controls/def", "45.6")
    check_send("def", "45.6")
    mqtt.recv("/devices/abc/controls/foobar/meta/type", "temperature")
    mqtt.recv("/devices/abc/controls/foobar", "42")
    check_reg("foobar", "42")
    handler.process_periodic_retries()
    mqtt.check()


@with_handler
def test_non_numeric():
    mqtt.recv("/devices/abc/controls/def", "123;45;1")
    mqtt.recv("/devices/abc/controls/def/meta/type", "rgb")
    mqtt.recv("/devices/abc/controls/zzz", "1")  # skipped (pushbutton type)
    mqtt.recv("/devices/abc/controls/def/meta/type", "pushbutton")
    mqtt.check()
    mqtt.recv("/retain_hack", "1")
    check_reg_str("def", "123;45;1")
    mqtt.recv("/devices/abc/controls/def", "1;1;1")
    check_send_str("def", "1;1;1")
    handler.process_periodic_retries()
    mqtt.check()


@with_handler
def test_retry():
    mqtt.recv("/devices/abc/controls/def", "123")
    mqtt.recv("/devices/abc/controls/def/meta/type", "temperature")
    fail_keys.append("mqtt.lld.value[/devices/abc/controls/def]")
    mqtt.recv("/retain_hack", "1")
    check_reg("def", "123", send_fail=True)

    handler.process_periodic_retries()
    check_send_fail("def", "123")

    fail_keys.pop()
    handler.process_periodic_retries()
    mqtt.check()  # not enough time elapsed

    elapse(5)
    handler.process_periodic_retries()
    check_send("def", "123")

    elapse(5)
    handler.process_periodic_retries()
    mqtt.check()


@with_handler(min_interval=10)
def test_rate_limit():
    mqtt.recv("/devices/abc/controls/def", "123")
    mqtt.recv("/devices/abc/controls/def/meta/type", "temperature")
    mqtt.recv("/retain_hack", "1")
    check_reg("def", "123")

    mqtt.recv("/devices/abc/controls/def", "45.6")
    mqtt.check()  # oops, rate limit exceeded

    elapse(5)
    mqtt.recv("/devices/abc/controls/def", "46")
    mqtt.check()  # still not enough

    elapse(5)
    mqtt.recv("/devices/abc/controls/def", "146")
    check_send("def", "146")

    mqtt.recv("/devices/abc/controls/def", "42")
    mqtt.check()

    elapse(13)
    mqtt.recv("/devices/abc/controls/def", "42")
    check_send("def", "42")
