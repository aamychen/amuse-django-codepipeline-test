from rest_framework import serializers
from releases.downloads import GoogleDriveSongFileDownload
from releases.models import SongFileUpload


class SongFileUploadSerializer(serializers.ModelSerializer):
    file = serializers.CharField(required=False)

    class Meta:
        model = SongFileUpload
        fields = ('id', 'file', 'filename', 'link', 'status')

    def create(self, data):
        return SongFileUpload.objects.create(
            user=self.context.get('request').user, **data
        )

    def update(self, instance, data):
        if 'filename' not in data:
            data['filename'] = data.pop('file', None)

        if 'status' not in data:
            data['status'] = SongFileUpload.STATUS_COMPLETED

        return super(SongFileUploadSerializer, self).update(instance, data)


class GoogleDriveSongFileDownloadSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)  # This is SongFileUpload.id
    auth_code = serializers.CharField(write_only=True)
    file_id = serializers.CharField(write_only=True)

    def create(self, data):
        download = GoogleDriveSongFileDownload(
            data.get('auth_code'), data.get('file_id')
        )
        return SongFileUpload.objects.create(
            user=self.context.get('request').user, link=download.get_download_link()
        )


class LinkSongFileDownloadSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)  # This is SongFileUpload.id
    link = serializers.CharField(write_only=True)

    def create(self, data):
        return SongFileUpload.objects.create(
            user=self.context.get('request').user, link=data.get('link')
        )
