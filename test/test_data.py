from wb_mqtt_zabbix.data import load_data_file


def test_load_dat_file():
    assert "<templates>" in load_data_file("zbx_export_templates.xml")
    assert "<hosts>" in load_data_file("zbx_export_hosts.xml")
