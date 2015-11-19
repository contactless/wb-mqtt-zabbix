import time
import random

mqtt_dev_id = str(time.time()) + str(random.randint(0, 100000))


def retain_hack_topic():
    return "/tmp/%s/retain_hack" % mqtt_dev_id
