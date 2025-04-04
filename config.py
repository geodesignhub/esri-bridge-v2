from dotenv import load_dotenv
from os import environ
import os

basedir = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(basedir, ".env"))


class Config(object):
    REDIS_URL = environ.get("REDIS_URL", "redis://localhost:6379")
    LANGUAGES = {"en": "English"}


external_api_settings = {
    "S3_BUCKET_NAME": environ.get("S3_BUCKET_NAME", "default-bucket"),
    "S3_KEY": environ.get("S3_KEY", "default-key"),
    "S3_SECRET": environ.get("S3_SECRET", "default-secret"),
    "S3_CDN_ENDPOINT": environ.get("S3_CDN_ENDPOINT", "https://cdn.example.com"),
    "GDH_SERVICE_URL": environ.get(
        "SERVICE_URL", "https://www.geodesignhub.com/api/v1/"
    ),
}
