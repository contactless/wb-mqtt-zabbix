import json
import logging
from collections import namedtuple
from .exc import ZabbixBridgeError

log = logging.getLogger(__name__)

CONF = [("mqtt_host", "localhost"),
        ("mqtt_port", 1883),
        ("mqtt_topics", []),
        ("zabbix_server", "localhost"),
        ("zabbix_port", 10051),
        ("zabbix_host_name", "Zabbix server"),
        ("min_interval", 0),
        ("retry_interval", 5),
        ("debug", False),
        ("syslog", False)]
CONF_NAMES = [x[0] for x in CONF]


def load_config(conf_file):
    conf = dict(CONF)
    if not conf_file:
        log.debug("config file not specified")
        return conf
    log.debug("loading conf file: %s", conf_file)
    loaded = json.load(conf_file)
    if not isinstance(loaded, dict):
        raise ZabbixBridgeError("bad configuration file")
    conf.update(loaded)
    return conf


class HandlerConf(namedtuple("HandlerConf", CONF_NAMES)):
    def __new__(cls, conf_file=None, **kwargs):
        conf = load_config(conf_file)
        for k, v in kwargs.items():
            if k in conf and isinstance(v, list) or isinstance(v, tuple):
                conf[k].extend(v)
            else:
                conf[k] = v
        return super(HandlerConf, cls).__new__(
            cls, **{k: v for k, v in conf.items() if k in CONF_NAMES})
