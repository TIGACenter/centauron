from rest_framework import serializers
from rest_framework.relations import StringRelatedField

from apps.challenge.challenge_leaderboard.models import LeaderboardEntry
from apps.challenge.challenge_submission.models import TargetMetricValue
from apps.challenge.challenge_submission.serializers import TargetMetricValueSerializer
from apps.core.serializers import DynamicFieldsModelSerializer, IdentifierField


# class
class LeaderboardEntrySerializer(DynamicFieldsModelSerializer):
    submission = IdentifierField(read_only=True)
    challenge = IdentifierField(read_only=True)
    identifier = StringRelatedField()
    # metrics = TargetMetricValueSerializer(many=True)
    metrics = serializers.SerializerMethodField()

    class Meta:
        model = LeaderboardEntry
        fields = ('position', 'metrics', 'submission', 'challenge', 'identifier',)

    def get_metrics(self, o:LeaderboardEntry):
        qs = TargetMetricValue.objects.filter(submission=o.submission)
        return TargetMetricValueSerializer(qs, many=True).data
