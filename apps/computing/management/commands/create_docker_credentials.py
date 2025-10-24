import base64
import json
import logging

import kubernetes
from django.conf import settings
from django.core.management.base import BaseCommand
from kubernetes.client import V1Secret, V1ObjectMeta


class Command(BaseCommand):
    help = "Creates the docker credentials on k8s computing cluster."

    def add_arguments(self, parser):
        parser.add_argument("--namespace", nargs="+", type=str, default="default")

    def handle(self, *args, **options):
        kubernetes.config.load_kube_config(config_file=settings.COMPUTING_K8S_CONFIG_FILE)
        k8s_core_api = kubernetes.client.CoreV1Api()
        namespace = options['namespace']

        if settings.DOCKER_CONFIG_FILE is None:
            logging.error('DOCKER_CONFIG_FILE is not set.')
            return

        logging.info('Create docker-credentials k8s secret for namespace %s', namespace)
        # create docker secret now
        with open(settings.DOCKER_CONFIG_FILE) as f:
            docker_config_dict = json.load(f)
        config = base64.b64encode(
            json.dumps(docker_config_dict).encode("utf-8")
        ).decode("utf-8")
        secret = V1Secret(type='kubernetes.io/dockerconfigjson',
                          metadata=V1ObjectMeta(name=settings.PRIVATE_DOCKER_REGISTRY_K8S_SECRET_NAME),
                          data={'.dockerconfigjson': config})
        k8s_core_api.create_namespaced_secret(namespace, secret)
        logging.info('Done.')
