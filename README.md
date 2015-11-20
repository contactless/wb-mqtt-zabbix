# wb-mqtt-zabbix
WB MQTT &lt;--> Zabbix bridge

## Установка Zabbix

Для целей разработки проще всего поставить Zabbix в контейнере без
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

2. Запускаем имейдж `berngp/docker-zabbix`:

    ```
    docker run -d -p 10051:10051 -p 8880:80 --name zabbix --cap-add SYS_PTRACE --security-opt apparmor:unconfined berngp/docker-zabbix
    ```

    (--cap-add SYS_PTRACE --security-opt apparmor:unconfined здесь нужны т.к. этот имейдж использует
    внутри monit)
3. Открываем в браузере http://localhost:8880/zabbix/ Логин `admin`, пароль `zabbix`.
   Открыться может не сразу, контейнер стартует некоторое время (создаётся база).
   После того, как страница загрузится, убеждаемся в работоспособности zabbix.
   Далее можно установить templates и hosts (см. ниже)

Контейнер удаляем так:
```
docker rm -f zabbix
```
После этого можно снова запустить имейдж через `docker run ...` (см. выше).

## Конфигурация

Перед началом работы необходимо отредактировать конфигурационный файл
`/etc/wb-mqtt-zabbix.conf`. Пример:
```
{
  "mqtt_host": "localhost",
  "mqtt_port": 1883,
  "mqtt_topics": ["#"],
  "zabbix_server": "localhost",
  "zabbix_port": 10051,
  "zabbix_host_name": "Zabbix server",
  "debug": false,
  "min_interval": 10,
  "retry_interval": 5
}
```

`mqtt_host` и `mqtt_port` задают хост и порт MQTT-брокера.

`mqtt_topics` - список топиков для отправки.

`zabbix_server`, `zabbix_port` - хост и порт Zabbix-сервера,
указываемые в конфигурации Zabbix agent.

`zabbix_host_name` задаёт имя хоста, определённого в конфигурации
хостов Zabbix.

`debug` включает отладочную печать.

`min_interval` задаёт минимальную задержку между отправкой
новых значений одного и того же топика.

`retry_interval` задаёт время повторной попытки отправки
значения параметра после его регистрации в Zabbix. Повторения
нужны, так как LLD (Low Level Discovery) в Zabbix срабатывает
не сразу.

## Ручной запуск сервиса в отладочном режиме

```
service wb-mqtt-zabbix stop
/usr/share/python/wb-mqtt-zabbix/bin/zabbix_bridge run -d -c /etc/wb-mqtt-zabbix.conf
```

## Подготовка zabbix-сервера при работе с Wiren Board

Пакет поддерживает автоматическую установку templates и hosts
на Zabbix-сервер.

```
/usr/share/python/wb-mqtt-zabbix/bin/zabbix_bridge deploy <url> -l <login> -p <password>
service wb-mqtt-zabbix restart
```

Например:
```
/usr/share/python/wb-mqtt-zabbix/bin/zabbix_bridge deploy http://myzabbix:8880/zabbix/ -l admin -p zabbix
service wb-mqtt-zabbix restart
```

Чтобы установить только templates, необходимо передать опцию --no-hosts.

Для проверки работы сервиса в zabbix идём в `Monitoring -> Latest data`,
кликаем посередине малозаметную надпись `Show filter`, в `Hosts`
выбираем/пишем `Zabbix server`, нажимаем `Filter`.  Раскрываем внизу `Other`, видим items.

## Установка wb-mqtt-zabbix (для разработки)

1. Устанавливаем зависимости:

    ```
    mkvirtualenv wb
    pip install -r requirements.txt
    ```

2. Запускаем `simulate.py` из mqtt-tools и homeui локально
3. Устанавливаем шаблоны и хосты в zabbix:

    ```
    PYTHONPATH=$PWD bin/zabbix_bridge deploy http://localhost:8880/zabbix/ -l admin -p zabbix
    ```

4. Запускаем bridge (`-d` - отладка):

    ```
    PYTHONPATH=$PWD bin/zabbix_bridge run -d
    ```

5. В Zabbix Web UI идём в `Monitoring -> Latest data`, кликаем посередине малозаметную
   надпись `Show filter`, в `Hosts` выбираем/пишем `Zabbix server`, нажимаем `Filter`.
   Раскрываем внизу `Other`, видим топики из MQTT. *Важно:* из-за имеющейся пока недоработки
   при первом запуске бриджа значения могут потеряться. Чтобы они появились в Zabbix,
   надо перезапустить бридж. Это связано с тем, что LLD работает асинхронно и человеческого
   способа определить, что он завершился, скорее всего, нет. Будет исправлено, видимо,
   путём последовательных retry для каждого значения топика.

## Сборка пакета

Для сборки пакета необходима chroot-среда Wiren Board и dh_virtualenv.
Для установки dh_virtualenv в chroot'е от рута необходимо запустить
скрипт install_dh_virtualenv.sh. Далее собираем пакет `wb-mqtt-zabbix`
командой

```
dpkg-buildpackage -us -uc
```

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
