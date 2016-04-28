from configparser import ConfigParser
from hashlib import sha512
from random import randrange
from warnings import warn

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from core import GAME_NAME
from cvars import ConVar
from listeners import OnClientActive, OnClientDisconnect, OnLevelInit
from listeners.tick import GameThread
from messages import VGUIMenu
from paths import CUSTOM_DATA_PATH
from players.entity import Player
from players.helpers import index_from_userid

from .server import SockServer
from .site_client import SiteClient
from .steamid import SteamID


AUTH_BY_SRCDS = 1
AUTH_BY_WEB = 2

MESSED_UP_GAMES = ('csgo', )
MOTDPLAYER_DATA_PATH = CUSTOM_DATA_PATH / "motdplayer"
SECRET_SALT_FILE = MOTDPLAYER_DATA_PATH / "secret_salt.dat"
CONFIG_FILE = MOTDPLAYER_DATA_PATH / "config.ini"
SERVER_ADDR = ConVar('ip').get_string()     # TODO: Better way?

if SECRET_SALT_FILE.isfile():
    with open(SECRET_SALT_FILE, 'rb') as f:
        SECRET_SALT = f.read()
else:
    SECRET_SALT = bytes([randrange(256) for x in range(32)])
    with open(SECRET_SALT_FILE, 'wb') as f:
        f.write(SECRET_SALT)

config = ConfigParser()
config.read(CONFIG_FILE)

engine = create_engine(config['database']['uri'].format(
    motdplayer_data_path=MOTDPLAYER_DATA_PATH,
))
Base = declarative_base()
Session = sessionmaker(bind=engine)

server = None


class User(Base):
    __tablename__ = 'motdplayers_srcds_users'

    id = Column(Integer, primary_key=True)
    steamid = Column(String(32))
    salt = Column(String(64))

    def __repr__(self):
        return "<User({})>".format(self.steamid)


Base.metadata.create_all(engine)


class SessionClosedException(Exception):
    pass


class MOTDPlayer:
    class Session:
        def __init__(self, motd_player, id_, callback, retargeting_callback):
            self._closed = False
            self._motd_player = motd_player
            self.id = id_
            self.callback = callback
            self.retargeting_callback = retargeting_callback

        def error(self, error):
            if self._closed:
                raise SessionClosedException("Please stop data transmission")

            self.callback(data=None, error=error)

        def receive(self, data):
            if self._closed:
                raise SessionClosedException("Please stop data transmission")

            return self.callback(data=data, error=None)

        def request_retargeting(self, new_page_id):
            if self._closed:
                raise SessionClosedException("Please stop data transmission")

            if self.retargeting_callback is None:
                return None

            return self.retargeting_callback(new_page_id)

        def close(self):
            self._closed = True
            self._motd_player.discard_session(self.id)

    def __init__(self, player):
        self.player = player
        self.salt = None
        self.communityid = str(SteamID(self.player.steamid).steamid64)

        self._next_session_id = 1
        self._sessions = {}

    def get_session_for_data_transmission(self, session_id):
        if session_id not in self._sessions:
            return None

        session = self._sessions[session_id]
        for session_ in self._sessions.values():
            if session_.id != session.id:
                try:
                    session_.error("TAKEN_OVER")
                except Exception as e:
                    warn(Warning(e))    # TODO: Print traceback instead

        self._sessions = {
            session_id: session
        }

        return session

    def close_all_sessions(self, error=None):
        if error is not None:
            for session in self._sessions.values():
                try:
                    session.error(error)
                except Exception as e:
                    warn(Warning(e))    # TODO: Print traceback instead

        self._sessions.clear()

    def discard_session(self, session_id):
        if session_id in self._sessions:
            del self._sessions[session_id]

    def get_auth_token(self, plugin_id, page_id, session_id):
        personal_salt = '' if self.salt is None else self.salt
        return sha512(
            (
                personal_salt +
                config['server']['id'] +
                plugin_id +
                self.communityid +
                page_id +
                str(session_id)
            ).encode('ascii') + SECRET_SALT
        ).hexdigest()

    def confirm_new_salt(self, new_salt):
        self.salt = new_salt

        # We save new salt to the database immediately to prevent
        # losing it when server crashes
        self.save_to_database()

        return True

    def load_from_database(self):
        db_session = Session()

        user = db_session.query(User).filter_by(
            steamid=self.communityid).first()

        if user is None:
            user = User()
            user.steamid = self.communityid
            db_session.add(user)
            db_session.commit()
        else:
            self.salt = user.salt

        db_session.close()

    def save_to_database(self):
        db_session = Session()

        user = db_session.query(User).filter_by(
            steamid=self.communityid).first()

        user.salt = self.salt
        db_session.commit()

        db_session.close()

    def send_page(self, plugin_id, page_id, callback,
                  retargeting_callback=None, debug=False):

        session = self.Session(self, self._next_session_id,
                               callback, retargeting_callback)

        self._sessions[self._next_session_id] = session
        self._next_session_id += 1

        if GAME_NAME in MESSED_UP_GAMES:
            url_base = config['motd']['url_csgo']
        else:
            url_base = config['motd']['url']

        url = url_base.format(
            server_addr=SERVER_ADDR,
            server_id=config['server']['id'],
            plugin_id=plugin_id,
            page_id=page_id,
            steamid=self.communityid,
            auth_method=AUTH_BY_SRCDS,
            auth_token=self.get_auth_token(plugin_id, page_id, session.id),
            session_id=session.id,
        )

        VGUIMenu(
            name='info',
            show=True,
            subkeys={
                'title': 'MOTD',
                'type': '0' if debug else '2',
                'msg': url,
            }
        ).send(self.player.index)

        return session


class MOTDPlayerManager(dict):
    def create(self, player):
        self[player.index] = motd_player = MOTDPlayer(player)
        GameThread(target=motd_player.load_from_database).start()

    def delete(self, motd_player):
        motd_player.close_all_sessions("MOTDPLAYER_DELETED")
        del self[motd_player.player.index]

    def get_by_userid(self, userid):
        index = index_from_userid(userid)
        return self.get(index)

    def get_by_communityid(self, communityid):
        for motd_player in self.values():
            if motd_player.communityid == communityid:
                return motd_player
        return None

player_manager = MOTDPlayerManager()


def get_by_index(index):
    return player_manager.get(index)


def get_by_userid(userid):
    return player_manager.get_by_userid(userid)


def send_page(player, plugin_id, page_id, callback, retargeting_callback=None,
              debug=False):

    if isinstance(player, Player):
        motd_player = player_manager.get(player.index)
        if motd_player is None:
            raise ValueError("Corresponding MOTDPlayer doesn't exist")

    elif isinstance(player, int):
        try:
            motd_player = player_manager[player]
            if motd_player is None:
                raise ValueError

        except (OverflowError, ValueError):
            raise ValueError("Passed integer should be valid player index")

    else:
        raise TypeError("Expected either Player instance or a player index, "
                        "got '{}' instead".format(type(player)))

    motd_player.send_page(
        plugin_id, page_id, callback, retargeting_callback, debug)


def on_client_accepted(client):
    SiteClient(client)


def restart_server():
    global server
    if server is not None:
        server.stop()

    server = SockServer(
        host=config['server']['host'],
        port=int(config['server']['port']),
        whitelist=config['server']['whitelist'].split(','),
        on_client_accepted=on_client_accepted,
    )
    server.start()

restart_server()


@OnClientActive
def listener_on_client_active(index):
    player = Player(index)

    # Check if CommunityID conversion will fail
    if player.steamid == "BOT":
        return

    player_manager.create(player)


@OnClientDisconnect
def listener_on_client_disconnect(index):
    motd_player = player_manager.get(index)
    if motd_player is not None:
        player_manager.delete(motd_player)


@OnLevelInit
def listener_on_level_init(map_name):
    for motd_player in tuple(player_manager.values()):
        player_manager.delete(motd_player)
