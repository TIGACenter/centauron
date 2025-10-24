import csv
from pathlib import Path

from apps.blockchain.messages import AddMessage, Object
from apps.blockchain.models import Log
from apps.challenge.challenge_dataset.models import Dataset
from apps.storage.models import File
from apps.user.user_profile.models import Profile
from config import celery_app


@celery_app.task
def import_csv(user_pk: str, path: str, dataset_id: str):
    dataset = Dataset.objects.get(pk=dataset_id)
    user = Profile.objects.get(pk=user_pk)

    with Path(path).open() as f:
        reader = csv.DictReader(f)

        # prefer column id over identifier
        if 'id' in reader.fieldnames:
            ids = [r['id'].strip() for r in reader]
            kw = 'id__in'
        elif 'identifier' in reader.fieldnames:
            ids = [r['identifier'].strip() for r in reader]
            kw = 'identifier__in'

        kwargs = {kw: ids}
        qs = dataset.challenge.project.files_for_user(user).filter(**kwargs)
        dataset.files.add(*qs)

        msg = AddMessage(
            actor=user.to_actor(),
            object=Object(model="slide", value=list(qs.values_list('identifier', flat=True))),
            context={"dataset": dataset.to_identifiable(), "challenge": dataset.challenge.to_identifiable()},
        )
        Log.send_broadcast(msg)
