from django.db import models

from apps.challenge.challenge_leaderboard.managers import LeaderboardEntryManager
from apps.challenge.challenge_submission.models import Submission, TargetMetricValue
from apps.challenge.challenge_targetmetric.models import TargetMetric
from apps.challenge.models import Challenge
from apps.core import identifier
from apps.core.models import Base, IdentifieableMixin
from apps.federation.messages import Message
from apps.user.user_profile.models import Profile


class LeaderboardEntry(IdentifieableMixin, Base):
    objects = LeaderboardEntryManager()
    position = models.PositiveIntegerField()
    challenge = models.ForeignKey('challenge.Challenge', on_delete=models.CASCADE, related_name='leaderboard_entries')
    submission = models.OneToOneField('challenge_submission.Submission', on_delete=models.CASCADE, related_name='leaderboard_entry')
    metrics = models.ManyToManyField('challenge_submission.TargetMetricValue', related_name='metric_values')

    def __str__(self):
        return f'[{self.challenge.name}] {self.position}. {self.submission}'

    def get_target_metric_value(self, target_metric_key):
        v = TargetMetricValue.objects.filter(submission=self.submission, target_metric__key=target_metric_key).first()
        if v is None:
            return '-'
        return v.value

    @staticmethod
    def calculate_leaderboard(challenge: Challenge):
        # 1. get all submissions that have a targetmetricvalue
        # for now only support sorting for one value
        metric = challenge.target_metrics.filter(sort__isnull=False).first()
        order_by_key = '-' if metric.sort == TargetMetric.Order.DESC else ''
        order_by_key += 'value'
        submission_pks = TargetMetricValue.objects.filter(submission__challenge=challenge,
                                                          submission__reference__isnull=True, # if submission.reference is none, then this is the aggregated submission
                                                          target_metric=metric) \
            .order_by(order_by_key) \
            .values('submission', 'pk') \
            .distinct()

        processed_entries = []

        for idx, submission_pk in enumerate(submission_pks):
            # metric_value_pk = submission_pk['pk']
            submission_pk = submission_pk['submission']
            entry = LeaderboardEntry.objects.filter(submission_id=submission_pk).first()
            if entry is not None:
                entry.position = idx
                entry.save()
            else:
                id = identifier.create_random('leaderboard-entry')
                entry = LeaderboardEntry.objects.create(challenge=challenge,
                                                        submission_id=submission_pk,
                                                        position=idx,
                                                        identifier=id)
                # entry.metrics.add(TargetMetricValue.objects.get(pk=metric_value_pk))
            processed_entries.append(entry.pk)

        LeaderboardEntry.objects.filter(challenge=challenge).exclude(id__in=processed_entries).delete()

        # submission_pks = TargetMetricValue.objects.filter(submission__challenge=challenge) \
        #     .order_by(order_by_key).distinct()

        # 2. sort by the values asc or desc as required
        # 3. update positions and/or create
        # 4. done

    @staticmethod
    def import_leaderboard(**kwargs):
        message: Message = kwargs.get('message')
        recipient = Profile.objects.get_by_identifier(identifier.from_string(message.to))
        sender = Profile.objects.get_by_identifier(identifier.from_string(message.from_))
        content = message.object.content
        challenge = Challenge.objects.get_by_identifier(identifier.from_string(content.get('challenge')))
        leaderboard = content.get('leaderboard', [])
        for e in leaderboard:
            position = e.get('position')
            submission = Submission.objects.get_by_identifier(
                identifier=identifier.from_string(e.get('submission')),
                                                          **dict(challenge=challenge))
            try:
                entry = LeaderboardEntry.objects.get_by_identifier(
                    identifier=identifier.from_string(e.get('identifier')),
                    **dict(challenge=challenge, submission=submission)
                )
                entry.position = position
                entry.save()
            except LeaderboardEntry.DoesNotExist:
                entry = LeaderboardEntry.objects.create(
                    identifier=identifier.from_string(e.get('identifier')),
                    challenge=challenge,
                    position=position,
                    submission=submission)

            tmvs = TargetMetricValue.import_list(e.get('metrics', []), submission)
            entry.metrics.set(tmvs)
