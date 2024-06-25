from esri_bridge import create_app
from flask_sse import sse
import logging
logger = logging.getLogger("esri-gdh-bridge")

def notify_agol_submission_success(job, connection, result, *args, **kwargs):
    # send a message to the room / channel that the shadows is ready
    logger.info("Job with %s completed successfully.." % str(job.id))
    job_id = job.id + ":gdh_to_agol_export"
    app, babel = create_app()
    with app.app_context():
        sse.publish({"job_id": job_id}, type="gdh_agol_export_success")


def notify_agol_submission_failure(job, connection, type, value, traceback):
    logger.info("Job with %s failed.." % str(job.id))
    job_id = job.id + ":gdh_to_agol_export"
    app, babel = create_app()
    with app.app_context():
        sse.publish({"job_id": job_id}, type="gdh_agol_export_failure")


