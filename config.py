import yaml

global_vars = {
    "server_data": {},
    "cached_message_objects": {}
}
config = {}
default_config = {
    "admin_roles": [],
    "active_messages": {},
    "servers": {}
}


def write_config():
    with open("config.yaml", "w") as f:
        yaml.dump(config, f)


def read_config():
    global config

    try:
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    except FileNotFoundError:
        write_config()

        return default_config


read_config()
