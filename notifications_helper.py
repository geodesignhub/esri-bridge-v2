import logging
logger = logging.getLogger("esri-gdh-bridge")

def notify_agol_submission_success(job, connection, result, *args, **kwargs):
    # send a message to the room / channel that the shadows is ready

    job_id = job.id + ":gdh_to_agol_export"
    logger.info("Job with %s completed successfully.." % job_id)

def notify_agol_submission_failure(job, connection, type, value, traceback):
    job_id = job.id + ":gdh_to_agol_export"
    logger.info("Job with %s failed.." % str(job.id))

