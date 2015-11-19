import json
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


class Control(object):
    def __init__(self, topic, value, value_type):
        self.topic = topic
        self.value = value
        self.value_type = value_type
        self.value_sent = False

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
        self._pending_retries = set()

    def send(self, key, value):
        return zbxsend.send_to_zabbix(
            [zbxsend.Metric(self.conf.zabbix_host_name, key, value)],
            self.conf.zabbix_server, self.conf.zabbix_port)

    def on_connect(self, client, userdata, flags, rc):
        log.debug("Connected with result code %s" % rc)
        for topic in (self.conf.mqtt_topics or ["#"]):
            t = unicode(topic).encode("utf-8")
            log.debug("Subscribing to %s" % t)
            self.client.subscribe(t)
        self.client.subscribe(util.retain_hack_topic())
        self.client.publish(util.retain_hack_topic(), "1")

    def register_control(self, control):
        log.debug("REG: %s", control.topic)
        d = dict(data=[{"{#MQTTNAME}": control.topic.rsplit("/", 1)[-1] or control.topic,
                        "{#MQTTTOPIC}": control.topic}])
        self.send("mqtt.lld_str" if control.is_str() else "mqtt.lld",
                  json.dumps(d, sort_keys=True))

    def send_value(self, control):
        log.debug("SEND: %s = %s" % (control.topic, control.value))
        key_fmt = "mqtt.lld.str_value[%s]" if control.is_str() else "mqtt.lld.value[%s]"
        if not self.send(key_fmt % control.topic, control.value) and not control.value_sent:
            self._pending_retries.add(control)
        else:
            control.value_sent = True
            self._pending_retries.discard(control)

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
            self._controls[value_topic] = Control(value_topic, cur_value, cur_type)
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
            self.register_control(control)
            self.send_value(control)
            return
        elif is_type_topic:
            return

        control.update(cur_value, cur_type)
        self.send_value(control)

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
        for control in sorted(self._pending_retries, key=lambda c: c.topic):
            log.debug("retrying sending %s = %s" % (control.topic, control.value))
            self.send_value(control)
