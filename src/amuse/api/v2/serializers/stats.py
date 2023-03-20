from rest_framework import serializers


class DailyStatsSerializer(serializers.Serializer):
    date = serializers.DateField()
    streams = serializers.IntegerField()
    downloads = serializers.IntegerField()


class UserDailyStatsSerializer(DailyStatsSerializer):
    user_id = serializers.IntegerField()


class SongDailyStatsSerializer(DailyStatsSerializer):
    song_id = serializers.IntegerField()
