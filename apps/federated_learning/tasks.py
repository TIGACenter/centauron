from celery import shared_task


@shared_task
def setup_fl_training():
    # TODO start fl server image in k8s.
    """
    TODO start fl server image in k8s. Then check the pod state. once it is running, notify the fl clients to start training. this could be as simple as a submission with type training.
    TODO nodes must then start the submission manually before training can start. add data field wait_until (timestamp) until the submission must be started
    TODO docker image must also be provided for the clients and must use the flower framework. this can be made configurable.
    TODO

    """
    pass


def start_fl_server():
    pass


def notify_fl_clients():
    pass
