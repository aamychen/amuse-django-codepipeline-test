class BaseSongArtistRoleModelError(BaseException):
    def __init__(self, message):
        self.message = message


class SongsIDsDoNotExistError(BaseSongArtistRoleModelError):
    pass


class ArtistsIDsDoNotExistError(BaseSongArtistRoleModelError):
    pass
