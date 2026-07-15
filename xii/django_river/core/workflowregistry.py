class WorkflowRegistry(object):
    def __init__(self):
        self.workflows = {}

    def add(self, name, cls):
        self.workflows.setdefault(cls, set()).add(name)

    def get_class_fields(self, model):
        return self.workflows.get(model, set())

    @property
    def registered_classes(self):
        return list(self.workflows.keys())


workflow_registry = WorkflowRegistry()
