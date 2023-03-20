import os
import requests
import tempfile
from contextlib import closing
from lxml import etree
from requests.exceptions import HTTPError
from django.conf import settings
from amuse.logging import logger
from releases.models import AudibleMagicMatch

STATUS_CODE_SUCCESS = 2000
STATUS_SONG_NOT_FOUND = 2005
STATUS_MATCH = 2006


class AudibleMagicError(Exception):
    pass


def identify_file(song_file):
    with closing(requests.get(song_file.file.url, stream=True, timeout=(5, 180))) as r:
        if r.status_code // 100 is not 2:
            raise HTTPError(
                'Failed to download song file from url %s with code %d'
                % (song_file.file.url, r.status_code)
            )
        media_file_fd, media_file_path = tempfile.mkstemp()
        response_xml_file_fd, response_xml_path = tempfile.mkstemp()
        try:
            with os.fdopen(media_file_fd, 'wb') as media_file:
                for chunk in r.iter_content(None):
                    media_file.write(chunk)
            os.system(
                'cd %s; LD_LIBRARY_PATH=. ./identifyFile -c %s -i %s -o %s > /dev/null 2>&1'
                % (
                    settings.AUDIBLE_MAGIC_DIR,
                    settings.AUDIBLE_MAGIC_CONF,
                    media_file_path,
                    response_xml_path,
                )
            )
            xml_tree = etree.parse(response_xml_path)
            response_status_code = int(xml_tree.xpath('Status/Number/text()')[0])
            response_status_msg = xml_tree.xpath('Status/Description/text()')[0]
            if response_status_code != STATUS_CODE_SUCCESS:
                raise AudibleMagicError(
                    'Audible Magic returned status code %d with message %s for song %d'
                    % (response_status_code, response_status_msg, song_file.song.id)
                )

            for id_response_info in xml_tree.xpath('Details/IdResponseInfo'):
                if (
                    int(id_response_info.xpath('IdResponse/IdStatus/text()')[0])
                    == STATUS_MATCH
                ):
                    AudibleMagicMatch.objects.create(
                        type=id_response_info.xpath('IdResponse/IdDetails/Type/text()')[
                            0
                        ],
                        track=id_response_info.xpath(
                            'IdResponse/IdDetails/Title/text()'
                        )[0],
                        album=id_response_info.xpath(
                            'IdResponse/IdDetails/Music/AlbumTitle/text()'
                        )[0],
                        artist=id_response_info.xpath(
                            'IdResponse/IdDetails/Music/Artist/text()'
                        )[0],
                        upc=id_response_info.xpath(
                            'IdResponse/IdDetails/Music/AlbumUPC/text()'
                        )[0],
                        isrc=id_response_info.xpath(
                            'IdResponse/IdDetails/Music/Isrc/text()'
                        )[0],
                        song=song_file.song,
                    )
        finally:
            os.close(response_xml_file_fd)
            os.remove(media_file_path)
            os.remove(response_xml_path)
