import json
import time
import logging
import paho.mqtt.client as mqtt
import wb_mqtt_zabbix.util as util
import wb_mqtt_zabbix.zbxsend as zbxsend
from .conf import HandlerConf

log = logging.getLogger(__name__)


STRING_TYPES = ["text", "rgb"]
SKIP_TYPES = ["pushbutton"]


def classify_topic(topic):
    if topic.endswith("/meta/type"):
        return True, topic[:-len("/meta/type")]
    else:
        return False, topic


class TimeInterval(object):
    def __init__(self, interval, zero_ok=True):
        self._interval = interval
        self._zero_ok = zero_ok
        self._ts = None

    def check(self):
        if not self._interval:
            return self._zero_ok

        ts = time.time()
        if self._ts is not None and ts - self._ts < self._interval:
            return False
        self._ts = time.time()
        return True


class Control(object):
    def __init__(self, topic, value, value_type, send, min_interval):
        self.topic = topic
        self.value = value
        self.value_type = value_type
        self._send = send
        self._send_interval = TimeInterval(min_interval)
        self._value_sent = False
        self._retry_pending = False
        self._retry_ts = None

    def is_complete(self):
        return self.value is not None and self.value_type is not None

    def update(self, value, value_type):
        if value is not None:
            self.value = value
        if value_type is not None:
            self.value_type = value_type
        return self.is_complete()

    def should_skip(self):
        return self.value_type in SKIP_TYPES

    def is_str(self):
        return self.value_type in STRING_TYPES

    def register(self):
        log.debug("REG: %s", self.topic)
        topic_parts = self.topic.split("/")
        if len(topic_parts) != 5:
            mqtt_name = topic_parts[-1] or self.topic
        else:
            mqtt_name = topic_parts[2] + " / " + topic_parts[4]
        d = dict(data=[{"{#MQTTNAME}": mqtt_name,
                        "{#MQTTTOPIC}": self.topic}])
        if not self._send("mqtt.lld_str" if self.is_str() else "mqtt.lld",
                          json.dumps(d, sort_keys=True)):
            log.error("failed to register %s" % self.topic)

    def send_value(self):
        key_fmt = "mqtt.lld.str_value[%s]" if self.is_str() else "mqtt.lld.value[%s]"
        if not self._send_interval.check():
            log.debug("SKIP: %s = %s" % (self.topic, self.value))
            return
        log.debug("SEND: %s = %s" % (self.topic, self.value))
        if not self._send(key_fmt % self.topic, self.value) and not self._value_sent:
            self._retry_pending = True
            log.warn("failed to send %s = %s, will retry" % (self.topic, self.value))
        else:
            self._value_sent = True
            self._retry_pending = False

    def maybe_retry(self):
        if self._retry_pending:
            self.send_value()


class MQTTHandler(object):
    def __init__(self, client, debug=False, **kwargs):
        self.client = client
        if debug:
            kwargs["debug"] = True
        self.conf = HandlerConf(**kwargs)
        if self.conf.debug:
            logging.getLogger("").setLevel(logging.DEBUG)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self._controls = {}
        self._ready = False
        self._postponed = []
        self._retry_pending = False
        self._retry_interval = TimeInterval(self.conf.retry_interval, False)

    def send(self, key, value):
        r = zbxsend.send_to_zabbix(
            [zbxsend.Metric(self.conf.zabbix_host_name, key, value)],
            self.conf.zabbix_server, self.conf.zabbix_port)
        if not r:
            self._retry_pending = True
        return r

    def on_connect(self, client, userdata, flags, rc):
        log.debug("Connected with result code %s" % rc)
        for topic in (self.conf.mqtt_topics or ["#"]):
            t = unicode(topic).encode("utf-8")
            log.debug("Subscribing to %s" % t)
            self.client.subscribe(t)
        self.client.subscribe(util.retain_hack_topic())
        self.client.publish(util.retain_hack_topic(), "1")

    def _handle_message(self, msg):
        if not mqtt.topic_matches_sub("/devices/+/controls/+", msg.topic) and \
           not mqtt.topic_matches_sub("/devices/+/controls/+/meta/type", msg.topic):
            return
        is_type_topic, value_topic = classify_topic(msg.topic)
        if is_type_topic:
            cur_value = None
            cur_type = msg.payload
        else:
            cur_value = msg.payload
            cur_type = None
        if value_topic not in self._controls:
            self._controls[value_topic] = Control(
                value_topic, cur_value, cur_type,
                send=self.send, min_interval=self.conf.min_interval)
            # control cannot be complete at this point
            return

        control = self._controls[value_topic]
        if control.should_skip():
            log.debug("skipping control: %s" % control.topic)
            return

        if not control.is_complete():
            if not control.update(cur_value, cur_type):
                return
            if control.should_skip():
                log.debug("skipping control: %s" % control.topic)
                return
            control.register()
            control.send_value()
            return
        elif is_type_topic:
            return

        control.update(cur_value, cur_type)
        control.send_value()

    def on_message(self, client, userdata, msg):
        if self._ready:
            self._handle_message(msg)
            return

        if msg.topic != util.retain_hack_topic():
            log.debug("postponing message for topic %r" % msg.topic)
            self._postponed.append(msg)
            return

        log.debug("retain hack message received -- ready")
        self._ready = True
        for msg in self._postponed:
            self._handle_message(msg)
        del self._postponed

    def connect(self):
        self.client.connect(self.conf.mqtt_host, self.conf.mqtt_port)

    def process_periodic_retries(self):
        if not self._retry_pending or not self._retry_interval.check():
            return
        self._retry_pending = False
        for control in sorted(self._controls.values(), key=lambda c: c.topic):
            log.debug("retrying sending %s = %s" % (control.topic, control.value))
            control.maybe_retry()
