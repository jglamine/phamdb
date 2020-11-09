from celery import (Celery)

from webphamerator import config
# from werkzeug.local import LocalProxy
# from celery.utils import imports as celery_import


def make_celery(app_name=__name__):
    return Celery(app_name, broker=config.CELERY_BROKER_URI)


celery = make_celery()


def init_app(celery, app):
    celery.conf.update(app.config)

    TaskBase = celery.Task

    class ContextTask(TaskBase):
        abstract = True

        def __call__(self, *args, **kwargs):
            with app.app_context():
                return TaskBase.__call__(self, *args, **kwargs)

    celery.Task = ContextTask

    # print(celery.Task())


class TaskHandler:
    def __init__(self):
        self._app = None
        self._celery = None

        self._context_task_maker = None

        self._initialized = False

    def init_app(self, app, celery):
        TaskBase = celery.Task

        class ContextTask(TaskBase):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return TaskBase.__call__(self, *args, **kwargs)

        self._context_task_maker = ContextTask

    @property
    def context_task(self, *args):
        if not self._initialized:
            raise NotInitializedError("Task handler has not been initialzied "
                                      "with a Celery or Flask application.")

        return self._context_task_maker(*args)


class NotInitializedError(Exception):
    pass
