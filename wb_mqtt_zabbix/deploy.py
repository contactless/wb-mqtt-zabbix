from zabbix_api import ZabbixAPI, ZabbixAPIException
from .exc import ZabbixBridgeError
from .data import load_data_file


HOSTS_DATA_FILE = "zbx_export_hosts.xml"
TEMPLATES_DATA_FILE = "zbx_export_templates.xml"


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

    def deploy_hosts(self):
        self._connect()
        try:
            self.zapi.configuration.import_(
                dict(format="xml",
                     source=load_data_file(HOSTS_DATA_FILE),
                     rules=dict(hosts=dict(createMissing=True, updateExisting=True),
                                templateLinkage=dict(createMissing=True))))
        except ZabbixAPIException, e:
            raise ZabbixBridgeError("Zabbix API error: %s" % e)

    def deploy_templates(self):
        self._connect()
        try:
            self.zapi.configuration.import_(
                dict(format="xml",
                     source=load_data_file(TEMPLATES_DATA_FILE),
                     rules=dict(templates=dict(createMissing=True, updateExisting=True),
                                groups=dict(createMissing=True, updateExisting=True),
                                discoveryRules=dict(createMissing=True, updateExisting=True))))
        except ZabbixAPIException, e:
            raise ZabbixBridgeError("Zabbix API error: %s" % e)
