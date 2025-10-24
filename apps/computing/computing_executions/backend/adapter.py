from apps.computing.computing_executions.models import ComputingJobExecution



class BaseAdapter:

    def prepare(self, job:ComputingJobExecution):
        pass

    def execute(self, job: ComputingJobExecution):
        pass

    def delete(self, job: ComputingJobExecution):
        pass
