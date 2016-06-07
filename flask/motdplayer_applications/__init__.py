from importlib import import_module
import os


def parse_packages(dir_):
    packages = []
    for name in os.listdir(dir_):
        if name.startswith('__') and name.endswith('__'):
            continue

        if os.path.isdir(os.path.join(dir_, name)):
            packages.append(name)

    return packages


current_dir = os.path.dirname(__file__)
apps = parse_packages(current_dir)


def init(flask_app, db):
    for app_name in apps:
        app = import_module('motdplayer_applications.{}'.format(app_name))
        app.init(flask_app, db)
