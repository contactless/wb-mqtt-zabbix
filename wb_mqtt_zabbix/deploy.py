import re
from zabbix_api import ZabbixAPI, ZabbixAPIException
from .exc import ZabbixBridgeError
from .data import load_data_file
import logging

log = logging.getLogger(__name__)

SUBST_VERSION = "2.4"
IMPORT_FILES = {
    "2.2": {
        "hosts": "zbx_export_hosts-2.2.xml",
        "templates": "zbx_export_templates-2.2.xml"
    },
    "2.4": {
        "hosts": "zbx_export_hosts-2.4.xml",
        "templates": "zbx_export_templates-2.4.xml"
    },
}


class Deploy(object):
    def __init__(self, server, login, password):
        self.server = server
        self.login = login
        self.password = password
        self._connected = False

    def _connect(self):
        if self._connected:
            return
        try:
            self.zapi = ZabbixAPI(server=self.server)
            self.zapi.login(self.login, self.password)
        except ZabbixAPIException, e:
            raise ZabbixBridgeError("Zabbix API error: %s" % e)
        self._connected = True
        self._request_api_version()

    def _request_api_version(self):
        version_str = self.zapi.do_request(
            self.zapi.json_obj('apiinfo.version', {})).get("result", "")
        self.api_version = re.sub(r"(\d+\.\d+).\d+", r"\1", version_str)
        log.debug("Zabbix API version: %r", self.api_version)

    def _data_file(self, name):
        v = self.api_version if self.api_version in IMPORT_FILES else SUBST_VERSION
        filename = IMPORT_FILES[v][name]
        log.debug("data file: %r" % filename)
        return load_data_file(filename)

    def deploy_hosts(self):
        self._connect()
        try:
            log.debug("importing hosts")
            self.zapi.configuration.import_(
                dict(format="xml",
                     source=self._data_file("hosts"),
                     rules=dict(hosts=dict(createMissing=True, updateExisting=True),
                                templateLinkage=dict(createMissing=True))))
        except ZabbixAPIException, e:
            raise ZabbixBridgeError("Zabbix API error: %s" % e)

    def deploy_templates(self):
        self._connect()
        try:
            log.debug("importing templates")
            self.zapi.configuration.import_(
                dict(format="xml",
                     source=self._data_file("templates"),
                     rules=dict(templates=dict(createMissing=True, updateExisting=True),
                                groups=dict(createMissing=True, updateExisting=True),
                                discoveryRules=dict(createMissing=True, updateExisting=True))))
        except ZabbixAPIException, e:
            raise ZabbixBridgeError("Zabbix API error: %s" % e)
