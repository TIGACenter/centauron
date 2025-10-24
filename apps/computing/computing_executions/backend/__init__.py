from importlib import import_module

from django.conf import settings

COMPUTING_BACKEND = getattr(settings, 'COMPUTING_BACKEND',
                            'apps.computing.computing_executions.backend.k8s.k8s_execution_backend.K8SExecutionBackend')


def get_computing_backend():
    # grab the classname off of the backend string
    package, klass = COMPUTING_BACKEND.rsplit('.', 1)
    # dynamically import the module, in this case app.backends.adapter_a
    module = import_module(package)
    # pull the class off the module and return
    return getattr(module, klass)

if settings.ENABLE_COMPUTING:
    computing_backend = get_computing_backend()()
