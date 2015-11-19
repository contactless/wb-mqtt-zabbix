from cStringIO import StringIO
from wb_mqtt_zabbix.conf import HandlerConf, CONF
from nose.tools import eq_

EMPTY_CONF = "{}"

SAMPLE_CONF = """
{
  "mqtt_host": "localhost",
  "mqtt_port": 1883,
  "mqtt_topics": [
    "/devices/Weather/controls/Illuminance",
    "/devices/Weather/controls/Pressure"
  ],
  "zabbix_server": "localhost",
  "zabbix_port": 10051,
  "zabbix_host_name": "Zabbix server",
  "debug": false
}
"""


def test_empty_conf():
    conf = HandlerConf(conf_file=StringIO(EMPTY_CONF))
    for k, v in CONF:
        eq_(v, getattr(conf, k))


def test_override():
    conf = HandlerConf(conf_file=StringIO(SAMPLE_CONF), mqtt_port=1884,
                       mqtt_topics=["/devices/Zzz/#"])
    eq_("localhost", conf.mqtt_host)
    eq_(1884, conf.mqtt_port)
    eq_(["/devices/Weather/controls/Illuminance",
         "/devices/Weather/controls/Pressure",
         "/devices/Zzz/#"], conf.mqtt_topics)
