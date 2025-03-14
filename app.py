#!/usr/bin/env python3
from flask import Flask
from data_definitions import (
    ErrorResponse,
    ExportConfirmationPayload,
    MessageType,
    AGOLExportStatus,
    custom_asdict_factory,
    GeodesignhubDesignDetail,
    GeodesignhubDataStorage,
    GeodesignhubDesignGeoJSON,
    ArcGISDesignPayload,
    AGOLSubmissionPayload,
    GeodesignhubProjectTags,
    AllSystemDetails,
    ImportConfirmationPayload,
)
from notifications_helper import (
    notify_agol_submission_success,
    notify_agol_submission_failure,
)
from dacite import from_dict
from flask import request, Response
from dotenv import load_dotenv, find_dotenv
import os
import utils
from flask import session, redirect, url_for
from dataclasses import asdict
from flask import render_template
from esri_bridge import create_app
import uuid
import geojson
from gdh_downloads_helper import GeodesignhubDataDownloader
import json
from conn import get_redis
from rq import Queue
from worker import conn
from flask_wtf import FlaskForm, CSRFProtect
from flask_bootstrap import Bootstrap5
from wtforms import (
    BooleanField,
    SubmitField,
    HiddenField,
    SelectField,
    StringField,
    FieldList,
    FormField,
)
from wtforms.validators import InputRequired
import logging
from logging.config import dictConfig
import re

load_dotenv(find_dotenv())
ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)
base_dir = os.path.abspath(os.path.dirname(__file__))

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
            }
        },
        "root": {"level": "INFO", "handlers": ["console"]},
    }
)
logger = logging.getLogger("esri-gdh-bridge")

app = Flask(__name__)
r = get_redis()
q = Queue(connection=conn)
csrf = CSRFProtect(app)
bootstrap = Bootstrap5(app)

MIMETYPE = "application/json"


def get_locale():
    # if the user has set up the language manually it will be stored in the session,
    # so we use the locale from the user settings
    try:
        language = session["language"]
    except KeyError:
        language = None
    if language is not None:
        return language
    return request.accept_languages.best_match(app.config["LANGUAGES"].keys())


app, babel = create_app()

app.secret_key = os.getenv("SECRET_KEY", "My Secret key")
app.config["BABEL_TRANSLATION_DIRECTORIES"] = os.path.join(base_dir, "translations")
babel.init_app(app, locale_selector=get_locale)

csrf = CSRFProtect(app)
bootstrap = Bootstrap5(app)


class ExportConfirmationForm(FlaskForm):
    """
    ExportConfirmationForm is a FlaskForm used to handle the export confirmation process.
    Attributes:
        agol_token (HiddenField): A hidden field to store the ArcGIS Online token.
        agol_project_id (HiddenField): A hidden field to store the ArcGIS Online project ID.
        session_id (HiddenField): A hidden field to store the session ID.
        webmap (BooleanField): A boolean field to indicate whether to include the webmap in the export.
        storymap (BooleanField): A boolean field to indicate whether to include the storymap in the export.
        submit (SubmitField): A submit button to trigger the export process.
    """

    agol_token = HiddenField()
    agol_project_id = HiddenField()
    session_id = HiddenField()
    webmap = BooleanField("Include Webmap")
    storymap = BooleanField("Include Storymap")
    submit = SubmitField(label="Export Design to ArcGIS Online →")


class AGOLObjectEntryForm(FlaskForm):
    agol_id = HiddenField()
    name = StringField("Name", validators=[InputRequired()])
    project_or_policy = SelectField(
        "Project or Policy",
        coerce=str,
        validators=[InputRequired()],
        choices=[("project", "Project"), ("policy", "Policy")],
    )
    destination_gdh_system = SelectField(
        "Destination System",
        coerce=int,
        validators=[InputRequired()],
        choices=[(0, "Select System")],
    )


class ImportConfirmationForm(FlaskForm):
    """
    A form for confirming the import of selected data to Geodesignhub.
    Attributes:
        agol_token (HiddenField): A hidden field to store the AGOL token.
        session_id (HiddenField): A hidden field to store the session ID.
        submit (SubmitField): A submit button to confirm the import action.
    """

    agol_token = HiddenField()
    session_id = HiddenField()
    agol_objects = FieldList(FormField(AGOLObjectEntryForm), max_entries=10)
    submit = SubmitField(label="Import selected data to Geodesignhub →")


def create_import_confirmation_form(
    project_id: str,
    agol_token: str,
    agol_project_id: str,
    session_id: str,
    _gdh_systems: AllSystemDetails,
)->ImportConfirmationForm:
    agol_objects_form = AGOLObjectEntryForm()
    agol_objects_form.agol_id = ("0000-0000-0000-0000",)

    agol_objects_form.destination_gdh_system.choices = [
        (
            system.id,
            system.name,
        )
        for system in _gdh_systems.systems
    ]
    agol_objects_form.name = "Test Label"

    import_confirmation_form = ImportConfirmationForm()

    import_confirmation_form.project_id = project_id
    import_confirmation_form.agol_token = agol_token
    import_confirmation_form.agol_project_id = agol_project_id
    import_confirmation_form.session_id = session_id

    import_confirmation_form.agol_objects = [agol_objects_form]

    return import_confirmation_form


@app.route("/get_agol_processing_result", methods=["GET"])
def get_agol_processing_result():
    session_id = request.args.get("session_id", "0")
    agol_processing_key = session_id + "_status"

    processing_result_exists = r.exists(agol_processing_key)
    if processing_result_exists:
        s = r.get(agol_processing_key)
        agol_status = json.loads(s)
    else:
        agol_export_status = AGOLExportStatus(
            status=2,
            message="Export to ArcGIS Online is still in progress, please check back afer a few minutes",
            success_url="",
        )
        agol_status = asdict(agol_export_status)
    return Response(json.dumps(agol_status), status=200, mimetype=MIMETYPE)


@app.route("/export/", methods=["GET", "POST"])
def export_design():
    """
    This function handles the export of a design from Geodesignhub to ArcGIS Online (AGOL).
    It performs the following steps:
    1. Parses request arguments to extract project and authentication details.
    2. Initializes a session and creates an export confirmation form.
    3. Downloads project details and systems from Geodesignhub.
    4. Validates the export confirmation form and processes the form data.
    5. Retrieves and parses design details and project tags from the session.
    6. Prepares the payload for AGOL submission, including design data, tags, and additional options.
    7. Enqueues a job to publish the design to AGOL and redirects the user upon success.
    8. If the form is not submitted, it downloads design data, details, and tags from Geodesignhub.
    9. Caches the design data and tags in the session.
    10. Renders the export confirmation template with the necessary data.
    Returns:
        Response: A redirect response to the next step in the export process or a rendered template for export confirmation.
    """
    """This is the root of the web service, upon successful authentication a text will be displayed in the browser"""
    try:
        project_id = request.args.get("projectid")
        apitoken = request.args.get("apitoken")
        design_team_id = request.args.get("cteamid")
        design_id = request.args.get("synthesisid")
        agol_token = request.args.get("arcgisToken")
        agol_project_id = request.args.get("gplProjectId")

    except KeyError:
        error_msg = ErrorResponse(
            status=0,
            message="Could not parse Project ID, Diagram ID or API Token ID. One or more of these were not found in your JSON request.",
            code=400,
        )

        return Response(asdict(error_msg), status=400, mimetype=MIMETYPE)

    session_id = uuid.uuid4()
    export_confirmation_form = ExportConfirmationForm(
        project_id=project_id,
        agol_token=agol_token,
        agol_project_id=agol_project_id,
        session_id=session_id,
    )

    my_geodesignhub_downloader = GeodesignhubDataDownloader(
        session_id=session_id,
        project_id=project_id,
        synthesis_id=design_id,
        cteam_id=design_team_id,
        apitoken=apitoken,
    )
    _gdh_project_details = my_geodesignhub_downloader.get_project_details()
    _gdh_systems_raw = my_geodesignhub_downloader.download_project_systems()

    if export_confirmation_form.validate_on_submit():
        diagram_upload_form_data = export_confirmation_form.data
        agol_token = diagram_upload_form_data["agol_token"]
        agol_project_id = diagram_upload_form_data["agol_project_id"]
        existing_session_id = diagram_upload_form_data["session_id"]
        existing_session_key = existing_session_id + "_design"

        design_details_str = r.get(existing_session_key)

        # Capture checkbox values
        include_webmap = export_confirmation_form.webmap.data
        include_storymap = export_confirmation_form.storymap.data

        tags_key = existing_session_id + "_tags"

        project_tags_str = r.get(tags_key)
        _all_project_tags = json.loads(project_tags_str.decode("utf-8"))
        project_tags_parsed = from_dict(
            data_class=GeodesignhubProjectTags, data=_all_project_tags
        )

        _design_feature_collection = json.loads(design_details_str.decode("utf-8"))
        _design_details_parsed = my_geodesignhub_downloader.parse_transform_geojson(
            design_feature_collection=_design_feature_collection["design_geojson"]
        )

        _design_feature_collection["design_geojson"]["geojson"] = _design_details_parsed

        design_details = from_dict(
            data_class=GeodesignhubDataStorage,
            data=_design_feature_collection,
        )

        agol_design_submission = ArcGISDesignPayload(
            gdh_design_details=design_details,
        )
        _gdh_systems = AllSystemDetails(systems=_gdh_systems_raw)
        agol_submission_payload = AGOLSubmissionPayload(
            design_data=agol_design_submission,
            tags_data=project_tags_parsed,
            agol_token=agol_token,
            agol_project_id=agol_project_id,
            session_id=existing_session_id,
            gdh_systems_information=_gdh_systems,
            gdh_project_details=_gdh_project_details,
            include_webmap=include_webmap,  # Add this field to your payload class
            include_storymap=include_storymap,  # Add this field to your payload class
        )

        agol_submission_job = q.enqueue(
            utils.publish_design_to_agol,
            agol_submission_payload,
            on_success=notify_agol_submission_success,
            on_failure=notify_agol_submission_failure,
            job_id=existing_session_id,
            job_timeout=3600,
        )

        return redirect(
            url_for(
                "redirect_after_export",
                agol_token=agol_token,
                session_id=existing_session_id,
                agol_project_id=agol_project_id,
                status=1,
                code=307,
            )
        )

    _design_feature_collection = (
        my_geodesignhub_downloader.download_design_data_from_geodesignhub()
    )
    gj_serialized = json.loads(geojson.dumps(_design_feature_collection))

    design_geojson = GeodesignhubDesignGeoJSON(geojson=gj_serialized)
    _design_details = (
        my_geodesignhub_downloader.download_design_details_from_geodesignhub()
    )
    _project_tags = my_geodesignhub_downloader.download_project_tags()
    design_details = from_dict(
        data_class=GeodesignhubDesignDetail, data=_design_details
    )
    _design_name = design_details.description
    # Make the design name only alpha numeric since AGOL only supports alpha-numeric names
    _design_name = re.sub("[^0-9a-zA-Z]+", "_", _design_name)

    project_tags = from_dict(data_class=GeodesignhubProjectTags, data=_project_tags)

    _num_features = len(gj_serialized["features"])
    gdh_data_for_storage = GeodesignhubDataStorage(
        design_geojson=design_geojson,
        design_id=design_id,
        design_team_id=design_team_id,
        project_id=project_id,
        design_name=_design_name,
    )

    session_key = str(session_id) + "_design"
    # Cache it
    r.set(session_key, json.dumps(asdict(gdh_data_for_storage)))
    r.expire(session_key, time=60000)
    tags_storage_key = str(session_id) + "_tags"
    # Cache it
    r.set(tags_storage_key, json.dumps(asdict(project_tags)))
    r.expire(tags_storage_key, time=60000)

    confirmation_message = "Design is ready for migration"
    message_type = MessageType.primary
    export_confirmation_payload = ExportConfirmationPayload(
        agol_token=agol_token,
        agol_project_id=agol_project_id,
        message_type=message_type,
        message=confirmation_message,
        geodesignhub_design_feature_count=_num_features,
        geodesignhub_design_name=gdh_data_for_storage.design_name,
        session_id=session_id,
    )

    return render_template(
        "export.html",
        export_template_data=asdict(
            export_confirmation_payload, dict_factory=custom_asdict_factory
        ),
        form=export_confirmation_form,
    )


@app.route("/export_result/", methods=["GET"])
def redirect_after_export():
    """
    Handles the redirection after an export operation to ArcGIS Online.
    This function retrieves the status, agol_token, session_id, and agol_project_id
    from the request arguments, constructs a message based on the status, and renders
    the 'design_export_status.html' template with the provided information.
    Args:
        None
    Returns:
        A rendered HTML template with the export status message and relevant information.
    """

    status = int(request.args.get("status"))
    agol_token = request.args["agol_token"]
    session_id = request.args["session_id"]
    agol_project_id = request.args["agol_project_id"]
    message = (
        "Your design is being exported to ArcGIS Online, you can close this window and check ArcGIS.com after a few minutes..."
        if status
        else "Error in exporting the design, please contact your administrator"
    )
    return render_template(
        "export_result/design_export_status.html",
        op=status,
        message=message,
        agol_token=agol_token,
        session_id=session_id,
        agol_project_id=agol_project_id,
    )


@app.route("/import/", methods=["GET", "POST"])
def import_agol_data():
    """
    Handles the import of data from ArcGIS Online (AGOL) based on the provided request parameters.
    This function extracts necessary parameters from the request, validates the import confirmation form,
    and either redirects to a confirmation page or renders the import template with the appropriate data.
    Request Parameters:
    - projectid: The ID of the project.
    - apitoken: The API token for authentication.
    - cteamid: The ID of the design team.
    - synthesisid: The ID of the design.
    - arcgisToken: The token for accessing ArcGIS Online.
    - gplProjectId: The ID of the AGOL project.
    Returns:
        Response: A redirect response to the confirmation page if the form is valid, or a rendered template
                  with the import confirmation form and data.
    """

    try:
        project_id = request.args.get("projectid")
        apitoken = request.args.get("apitoken")
        design_team_id = request.args.get("cteamid")
        design_id = request.args.get("synthesisid")
        agol_token = request.args.get("arcgisToken")
        agol_project_id = request.args.get("gplProjectId")

    except KeyError:
        error_msg = ErrorResponse(
            status=0,
            message="Could not parse Project ID, Diagram ID or API Token ID. One or more of these were not found in your JSON request.",
            code=400,
        )

        return Response(asdict(error_msg), status=400, mimetype=MIMETYPE)

    session_id = uuid.uuid4()
    my_geodesignhub_downloader = GeodesignhubDataDownloader(
        session_id=session_id,
        project_id=project_id,
        synthesis_id=design_id,
        cteam_id=design_team_id,
        apitoken=apitoken,
    )

    _gdh_systems_raw = my_geodesignhub_downloader.download_project_systems()
    _gdh_systems = AllSystemDetails(systems=_gdh_systems_raw)
    
    import_confirmation_form = create_import_confirmation_form(
        project_id=project_id, agol_token= agol_token,  agol_project_id=agol_project_id, session_id=session_id, _gdh_systems=_gdh_systems)
    
    if import_confirmation_form.validate_on_submit():
        diagram_upload_form_data = import_confirmation_form.data
        agol_token = diagram_upload_form_data["agol_token"]
        agol_project_id = diagram_upload_form_data["agol_project_id"]
        existing_session_id = diagram_upload_form_data["session_id"]

        return redirect(
            url_for(
                "redirect_after_import",
                agol_token=agol_token,
                session_id=existing_session_id,
                agol_project_id=agol_project_id,
                status=1,
                code=307,
            )
        )

    confirmation_message = "Select data you want to import.."
    message_type = MessageType.primary
    import_confirmation_payload = ImportConfirmationPayload(
        agol_token=agol_token,
        agol_project_id=agol_project_id,
        message_type=message_type,
        message=confirmation_message,
        session_id=session_id,
    )

    return render_template(
        "import.html",
        import_template_data=asdict(
            import_confirmation_payload, dict_factory=custom_asdict_factory
        ),
        form=import_confirmation_form,
    )


@app.route("/import_result/", methods=["GET"])
def redirect_after_import():
    """
    Handles the redirection after an import operation from AGOL (ArcGIS Online) to Geodesignhub.
    Retrieves the status, AGOL token, session ID, and AGOL project ID from the request arguments.
    Depending on the status, it sets an appropriate message indicating the success or failure of the import operation.
    Renders the 'import_result/design_import_status.html' template with the operation status, message, AGOL token, session ID, and AGOL project ID.
    Returns:
        Response: Rendered HTML template with the import status and related information.
    """

    status = int(request.args.get("status"))
    agol_token = request.args["agol_token"]
    session_id = request.args["session_id"]
    agol_project_id = request.args["agol_project_id"]
    message = (
        "Your AGOL data is being migrated to Geodesignhub, check your Geodesignhub project in a few minutes..."
        if status
        else "Error in importing your AGOL data, please contact your administrator"
    )
    return render_template(
        "import_result/design_import_status.html",
        op=status,
        message=message,
        agol_token=agol_token,
        session_id=session_id,
        agol_project_id=agol_project_id,
    )


@app.context_processor
def inject_conf_var():
    return dict(
        AVAILABLE_LANGUAGES=app.config["LANGUAGES"],
        CURRENT_LANGUAGE=session.get(
            "language",
            request.accept_languages.best_match(app.config["LANGUAGES"].keys()),
        ),
    )


@app.route("/")
def ping(language=None):
    return Response(json.dumps({"status": "healthy"}), status=200, mimetype=MIMETYPE)


@app.route("/language/<language>")
def set_language(language=None):
    session["language"] = language
    return redirect(request.referrer)


if __name__ == "__main__":
    app.debug = os.environ.get("IS_DEBUG", False)
    port = int(os.environ.get("PORT", 5001))
    app.run(port=port)
