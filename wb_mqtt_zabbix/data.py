import os.path

DATA_PATH = os.path.join(os.path.split(__file__)[0], "data")


def load_data_file(name):
    with open(os.path.join(DATA_PATH, name), "r") as f:
        return f.read()
