from ftplib import FTP

from django.conf import settings


class FugaFTPConnection:
    def __enter__(self):
        self.ftp_connection = FTP(
            settings.FUGA_FTP_HOSTNAME,
            settings.FUGA_FTP_USERNAME,
            settings.FUGA_FTP_PASSWORD,
        )

        return self.ftp_connection

    def __exit__(self, *args):
        self.ftp_connection.quit()
