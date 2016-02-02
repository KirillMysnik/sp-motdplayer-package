from configparser import ConfigParser
from hashlib import sha512
from random import randrange
from warnings import warn

from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from cvars import ConVar
from listeners import OnClientActive, OnClientDisconnect
from messages import VGUIMenu
from paths import CUSTOM_DATA_PATH
from players.entity import Player
from players.helpers import userid_from_index

from .server import SockServer
from .site_client import SiteClient
from .spthread import SPThread
from .steamid import SteamID


AUTH_BY_SRCDS = 1
AUTH_BY_WEB = 2

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
        def __init__(self, motd_player, id_, callback):
            self._closed = False
            self._motd_player = motd_player
            self.id = id_
            self.callback = callback

        def error(self, error):
            if self._closed:
                raise SessionClosedException("Please stop data transmission")

            self.callback(data=None, error=error)

        def receive(self, data):
            if self._closed:
                raise SessionClosedException("Please stop data transmission")

            return self.callback(data=data, error=None)

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

    def discard_session(self, session_id):
        if session_id in self._sessions:
            del self._sessions[session_id]

    def get_auth_token(self, page_id, session_id):
        personal_salt = '' if self.salt is None else self.salt
        return sha512(
            (
                personal_salt + self.communityid + page_id + str(session_id)
            ).encode('ascii') + SECRET_SALT
        ).hexdigest()

    def confirm_new_salt(self, new_salt):
        db_session = Session()

        self.salt = new_salt

        db_session.commit()
        db_session.close()

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

    def send_page(self, page_id, callback, auth_for=None, debug=False):
        if auth_for is None:
            auth_for = page_id

        session = self.Session(self, self._next_session_id, callback)
        self._sessions[self._next_session_id] = session
        self._next_session_id += 1

        url = config['motd']['url'].format(
            server_addr=SERVER_ADDR,
            page_id=page_id,
            steamid=self.communityid,
            auth_method=AUTH_BY_SRCDS,
            auth_token=self.get_auth_token(auth_for, session.id),
            session_id=session.id,
        )

        type_ = '0' if debug else '2'

        VGUIMenu(
            name='info',
            show=True,
            subkeys={
                'title': 'MOTD',
                'type': type_,
                'msg': url,
            }
        ).send(self.player.index)

        return session


class MOTDPlayerManager(dict):
    def create(self, player):
        self[player.userid] = motd_player = MOTDPlayer(player)
        SPThread(target=motd_player.load_from_database).start()

    def delete(self, motd_player):
        SPThread(target=motd_player.save_to_database).start()
        del self[motd_player.player.userid]

    def get_by_index(self, index):
        userid = userid_from_index(index)
        return self.get(userid)

    def get_by_communityid(self, communityid):
        for motd_player in self.values():
            if motd_player.communityid == communityid:
                return motd_player
        return None

player_manager = MOTDPlayerManager()


def get_by_index(index):
    return player_manager.get_by_index(index)


def get_by_userid(userid):
    return player_manager.get(userid)


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
    player_manager.create(player)


@OnClientDisconnect
def listener_on_client_disconnect(index):
    motd_player = player_manager.get_by_index(index)
    if motd_player is not None:
        player_manager.delete(motd_player)
