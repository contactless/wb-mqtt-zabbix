import json
import os.path
import logging
from collections import namedtuple
from zbxsend import Metric, send_to_zabbix
import paho.mqtt.client as mqtt

log = logging.getLogger(__name__)

REG_DELAY = 1

CONF = [("mqtt_host", "localhost"),
        ("mqtt_port", 1883),
        ("mqtt_topics", "#"),
        ("zabbix_server", "localhost"),
        ("zabbix_port", 10051),
        ("zabbix_host_name", "Zabbix server"),
        ("debug", False)]
CONF_NAMES = [x[0] for x in CONF]


class ZabbixBridgeError(Exception):
    pass


def load_config(conf_file):
    conf = dict(CONF)
    if not conf_file or not os.path.exists(conf_file):
        logging.debug("config file is not specified or doesn't exist")
        return conf
    log.debug("loading conf file: %s", conf_file)
    with open(conf_file) as f:
        loaded = json.load(f)
        if not isinstance(loaded, dict):
            raise ZabbixBridgeError("bad configuration file")
        conf.update(loaded)
        return conf


class HandlerConf(namedtuple("HandlerConf", CONF_NAMES)):
    def __new__(cls, conf_file, **kwargs):
        conf = load_config(conf_file)
        for k, v in kwargs.items():
            if k in conf and isinstance(v, list) or isinstance(v, tuple):
                conf[k].extend(v)
            else:
                conf[k] = v
        return super(HandlerConf, cls).__new__(
            cls, **{k: v for k, v in conf.items() if k in CONF_NAMES})


class MQTTHandler(object):
    def __init__(self, client, debug, **kwargs):
        self.client = client
        if debug:
            kwargs["debug"] = True
        self.conf = HandlerConf(**kwargs)
        if self.conf.debug:
            logging.basicConfig(level=logging.DEBUG)
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.reg_map = set()

    def send(self, key, value):
        return send_to_zabbix([Metric(self.conf.zabbix_host_name, key, value)],
                              self.conf.zabbix_server, self.conf.zabbix_port)

    def on_connect(self, client, userdata, flags, rc):
        log.debug("Connected with result code %s" % rc)
        for topic in self.conf.mqtt_topics:
            t = unicode(topic).encode("utf-8")
            log.debug("Subscribing to %s" % t)
            self.client.subscribe(t)

    def register_control(self, topic):
        log.debug("REG: %s", topic)
        self.send("mqtt.lld", json.dumps(dict(data=[{"{#MQTTNAME}": topic}])))

    def send_value(self, topic, payload):
        log.debug("SEND: %s = %s" % (topic, payload))
        # XXX problem: may fail
        self.send("mqtt.lld.value[%s]" % topic, payload)

    def on_message(self, client, userdata, msg):
        if not mqtt.topic_matches_sub("/devices/+/controls/+", msg.topic):
            return
        if msg.topic not in self.reg_map:
            self.register_control(msg.topic)
            self.reg_map.add(msg.topic)
        self.send_value(msg.topic, msg.payload)

    def connect(self):
        self.client.connect(self.conf.mqtt_host, self.conf.mqtt_port)
