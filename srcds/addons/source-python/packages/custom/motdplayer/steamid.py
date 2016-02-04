from core import GAME_NAME


# My steamid is STEAM_0:0:33051913 but in CS:GO it's STEAM_1:0:33051913
LEGACY_UNIVERSE = 1 if GAME_NAME == 'csgo' else 0

ACCOUNT_TYPE_TO_INSTANCE = {
    1: 1,
    3: 1,
    7: 0,
}


ACCOUNT_TYPE_CHAR_TO_INT = {
    'I': 0,
    'U': 1,
    'M': 3,
    'G': 3,
    'A': 4,
    'P': 5,
    'C': 6,
    'g': 7,
    'T': 8,
    'c': 8,
    'L': 8,
    'a': 10,
}


class SteamID:
    def __init__(self, source):
        self.universe = 1
        self.account_type = 1
        self.instance = 1
        self.account_id = -1

        if isinstance(source, int):
            if source > 1 << 32:
                self._load_from_steamid64(source)
            else:
                self._load_from_steamid64short(source)
        else:
            if source.startswith('['):
                if source.count(':') == 2:
                    self._load_from_steamid3short(source)
                elif source.count(':') == 3:
                    self._load_from_steamid3(source)
            elif source.startswith('STEAM_'):
                self._load_from_legacy(source)

        if self.account_id < 0:
            raise ValueError("Couldn't load SteamID: '{}'".format(source))

    @staticmethod
    def _account_type_to_char(account_type):
        for char, account_type_ in ACCOUNT_TYPE_CHAR_TO_INT.items():
            if account_type_ == account_type:
                return char

        raise ValueError("Unknown Accout Type ({})".format(account_type))

    def _load_from_steamid64(self, source):
        self.universe = (source >> 56) & ((1 << 8) - 1)
        self.account_type = (source >> 52) & ((1 << 4) - 1)
        self.instance = (source >> 32) & ((1 << 20) - 1)
        self.account_id = source & ((1 << 32) - 1)

    def _load_from_steamid64short(self, source):
        raise NotImplementedError

    def _load_from_steamid3(self, source):
        c, u, a, i = source.strip('[]').split(':')
        if c not in ACCOUNT_TYPE_CHAR_TO_INT:
            raise ValueError("Unknown Account Type character '{}'".format(c))

        self.universe = int(u)
        self.account_type = ACCOUNT_TYPE_CHAR_TO_INT[c]
        self.instance = int(i)
        self.account_id = int(a)

    def _load_from_steamid3short(self, source):
        c, u, a = source.strip('[]').split(':')

        if c not in ACCOUNT_TYPE_CHAR_TO_INT:
            raise ValueError("Unknown Account Type character '{}'".format(c))

        c0 = ACCOUNT_TYPE_CHAR_TO_INT[c]
        if c0 not in ACCOUNT_TYPE_TO_INSTANCE:
            raise ValueError("Couldn't find default instance "
                             "for '{}' ({})".format(c, c0))

        self.universe = int(u)
        self.account_type = c0
        self.instance = ACCOUNT_TYPE_TO_INSTANCE[c0]
        self.account_id = int(a)

    def _load_from_legacy(self, source):
        source = source[len('STEAM_'):]
        u0, j, k = source.split(':')
        if int(u0) != LEGACY_UNIVERSE:
            raise ValueError("Unknown legacy universe: ({})".format(u0))

        self.universe = 1
        self.account_id = int(j) + 2 * int(k)

    @property
    def steamid64(self):
        return (
            (self.universe << 56) |
            (self.account_type << 52) |
            (self.instance << 32) |
            self.account_id
        )

    @property
    def steamid64short(self):
        raise NotImplementedError

    @property
    def steamid3(self):
        return "[{}:{}:{}:{}]".format(
            self._account_type_to_char(self.account_type),
            self.universe,
            self.account_id,
            self.instance,
        )

    @property
    def steamid3short(self):
        return "[{}:{}:{}]".format(
            self._account_type_to_char(self.account_type),
            self.universe,
            self.account_id,
        )

    @property
    def legacy(self):
        if self.universe != 1:
            raise ValueError("Can't convert ({}) universe "
                             "to legacy universe".format(self.universe))

        u0 = LEGACY_UNIVERSE
        j = self.account_id & 1
        k = (self.account_id >> 1) & ((1 << 31) - 1)
        return "STEAM_{}:{}:{}".format(u0, j, k)
