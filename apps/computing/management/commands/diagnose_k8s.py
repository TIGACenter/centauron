import logging

import kubernetes
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Connects to k8s."

    def handle(self, *args, **options):
        kubernetes.config.load_kube_config()
        k8s_core_api = kubernetes.client.CoreV1Api()
        d = k8s_core_api.read_namespace(name='default')
        logging.info(d)
        # TODO add a pod that uses the GPU
