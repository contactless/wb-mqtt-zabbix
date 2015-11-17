# wb-mqtt-zabbix
WB MQTT &lt;--> Zabbix bridge

## Установка zabbix

Для целей разработки проще всего посавить zabbix в контейнере без
выноса данных в volume - в этом случае его можно легко удалить и
создать с нуля для перепроверки конфигурации, кроме того, не будет
замусориваться система на машине, используемой для
разработки/тестирования.

1. [Ставим docker]([http://docs.docker.com/engine/installation/ubuntulinux/).

    ```
    sudo apt-key adv --keyserver hkp://p80.pool.sks-keyservers.net:80 --recv-keys 58118E89F3A912897C070ADBF76221572C52609D
    # тут надо поставить нужную версию Ubuntu - wily, vivid, trusty
    echo 'deb https://apt.dockerproject.org/repo ubuntu-wily main' | sudo tee /etc/apt/sources.list.d/docker.list
    apt-get update
    # удалить старый docker, если он был
    apt-get purge lxc-docker*
    # установить, собственно, свежий docker
    sudo apt-get install docker-engine
    ```

2. Запускаем имейдж b`erngp/docker-zabbix`:

    ```
    docker run -d -p 10051:10051 -p 8880:80 --name zabbix --cap-add SYS_PTRACE --security-opt apparmor:unconfined berngp/docker-zabbix
    ```

    (--cap-add SYS_PTRACE --security-opt apparmor:unconfined здесь нужны т.к. этот имейдж использует
    внутри monit)
3. Открываем в браузере http://localhost:8880/zabbix/ Логин `admin`, пароль `zabbix`.
   Открыться может не сразу, контейнер стартует некоторое время (создаётся база).
4. Идём в `Configuration -> Templates`, кликаем `Import` (справа
   сверху). Кликаем выбор файла рядом с `Import file`, находим
   `zbx_export_templates.xml`.  Кликаем Import.
5. Идём в `Configuration -> Hosts`, кликаем `Import` (справа
   сверху). Кликаем выбор файла рядом с `Import file`, находим
   `zbx_export_hosts.xml`.  Кликаем Import.

Контейнер удаляем так:
```
docker rm -f zabbix
```
После этого можно снова запустить имейдж через `docker run ...` (см. выше).

*TBD:* сделать импорт конфигурации через API.

## Проверка LLD

1. Создаём items:

    ```
    docker exec zabbix zabbix_sender -c /etc/zabbix/zabbix_agentd.conf -vv -k mqtt.lld -o '{"data":[{ "{#MQTTNAME}":"/devices/test/123" }, { "{#MQTTNAME}":"/devices/test/321" }]}'
    ```

2. Постим значения:

    ```
    docker exec zabbix zabbix_sender -c /etc/zabbix/zabbix_agentd.conf zabbix_sender -c /etc/zabbix/zabbix_agentd.conf -vv -k "mqtt.lld.value[/devices/test/123]" -o 42.42
    ```

3. Идём в `Monitoring -> Latest data`, кликаем посередине малозаметную
   надпись `Show filter`, в `Hosts` выбираем/пишем `Zabbix server`, нажимаем `Filter`.
   Раскрываем внизу `Other`, видим items.

## Установка wb-mqtt-zabbix (для разработки)

1. Устанавливаем зависимости:

    ```
    mkvirtualenv wb
    pip install -r requirements.txt
    ```

2. Запускаем `simulate.py` из mqtt-tools и homeui локально
3. Запускаем bridge:

    ```
    ./zabbix_bridge.py
    ```

4. В Zabbix Web UI идём в `Monitoring -> Latest data`, кликаем посередине малозаметную
   надпись `Show filter`, в `Hosts` выбираем/пишем `Zabbix server`, нажимаем `Filter`.
   Раскрываем внизу `Other`, видим топики из MQTT. *Важно:* из-за имеющейся пока недоработки
   при первом запуске бриджа значения могут потеряться. Чтобы они появились в Zabbix,
   надо перезапустить бридж. Это связано с тем, что LLD работает асинхронно и человеческого
   способа определить, что он завершился, скорее всего, нет. Будет исправлено, видимо,
   путём последовательных retry для каждого значения топика.
