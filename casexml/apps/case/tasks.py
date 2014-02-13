from celery.task import task


@task
def process_cases(xform, config=None):
    from casexml.apps.case import process_cases
    process_cases(xform, config)
