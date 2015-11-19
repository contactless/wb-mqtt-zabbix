#!/usr/bin/env python

from setuptools import setup

setup(name='wb-mqtt-zabbix',
      version='1.0',
      description='WB MQTT Zabbix Bridge',
      author='Ivan Shvedunov',
      author_email='ivan4th@gmail.com',
      url='https://github.com/evgeny-boger/wb-mqtt-zabbix',
      scripts=['bin/zabbix_bridge'],
      packages=['wb_mqtt_zabbix'])
