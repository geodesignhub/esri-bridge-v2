#!/usr/bin/env python3
from flask import Flask
from data_definitions import (
    ErrorResponse,
    ExportConfirmationPayload,
    MessageType,
    custom_asdict_factory,
    GeodesignhubDesignDetail,
    GeodesignhubDataStorage,
    GeodesignhubDesignGeoJSON,
    ExportToArcGISRequestPayload
)
from notifications_helper import notify_agol_submission_success, notify_agol_submission_failure
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
from wtforms import SubmitField, HiddenField

app = Flask(__name__)
load_dotenv(find_dotenv())
ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)
base_dir = os.path.abspath(os.path.dirname(__file__))
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
    agol_token = HiddenField()
    agol_project_id = HiddenField()
    session_id = HiddenField()
    submit = SubmitField()

@app.route("/export/", methods=["GET", "POST"])
def export_design():
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
        project_id=project_id, agol_token=agol_token, agol_project_id=agol_project_id, session_id = session_id
    )

    my_geodesignhub_downloader = GeodesignhubDataDownloader(
        session_id=session_id,
        project_id=project_id,
        synthesis_id=design_id,
        cteam_id=design_team_id,
        apitoken=apitoken,
    )

    if export_confirmation_form.validate_on_submit():
        diagram_upload_form_data = export_confirmation_form.data
        
        agol_token = diagram_upload_form_data["agol_token"]
        agol_project_id = diagram_upload_form_data["agol_project_id"]
        session_id = diagram_upload_form_data["session_id"]
        session_key = session_id + '_design'
        
        design_details_str = r.get(session_key)
        
        _design_feature_collection = json.loads(design_details_str.decode("utf-8"))
        _design_details_parsed = my_geodesignhub_downloader.parse_transform_geojson(design_feature_collection=_design_feature_collection['design_geojson'])
        
        _design_feature_collection['design_geojson']['geojson'] = _design_details_parsed
        design_details =  from_dict(
        data_class=GeodesignhubDataStorage,
        data=_design_feature_collection,
        )
        
        agol_submission_payload = ExportToArcGISRequestPayload(agol_token = agol_token, agol_project_id=agol_project_id, gdh_design_details=design_details, session_id = session_id)
        agol_submission_job = q.enqueue(
            utils.export_design_json_to_agol,
            agol_submission_payload,
            on_success=notify_agol_submission_success,
            on_failure=notify_agol_submission_failure,
            job_id= session_id
        )

        return redirect(
            url_for(
                "redirect_after_export",
                agol_token=agol_token,
                session_id = session_id, 
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
    _design_details = my_geodesignhub_downloader.download_design_details_from_geodesignhub()
    design_details = from_dict(data_class = GeodesignhubDesignDetail, data = _design_details)
    _design_name = design_details.description
    
    _num_features = len(gj_serialized['features'])
    gdh_data_for_storage = GeodesignhubDataStorage(design_geojson = design_geojson, design_id = design_id, design_team_id = design_team_id, project_id = project_id, design_name = _design_name)
    session_key = str(session_id) + "_design"
    # Cache it
    r.set(session_key, json.dumps(asdict(gdh_data_for_storage)))
    r.expire(session_key, time=60000)

    confirmation_message = "Ready for migration"
    message_type = MessageType.success
    export_confirmation_payload = ExportConfirmationPayload(
        agol_token=agol_token,
        agol_project_id=agol_project_id,
        message_type=message_type,
        message=confirmation_message,
        geodesignhub_design_feature_count=_num_features,
        geodesignhub_design_name="V2",
        session_id=session_id,
    )

    return render_template(
        "export.html",
        export_template_data=asdict(export_confirmation_payload, dict_factory=custom_asdict_factory),
        form=export_confirmation_form,
    )


@app.route("/export_result/", methods=["GET"])
def redirect_after_export():

    status = int(request.args.get("status"))
    agol_token = request.args["agol_token"]
    session_id = request.args["session_id"]
    agol_project_id = request.args["agol_project_id"]
    message = (
        "Design Successfully exported to ArcGIS Online"
        if status
        else "Error in exporting the design, please contact your administrator"
    )
    return render_template(
        "export_result/design_export_status.html",
        op=status,
        message=message,
        agol_token=agol_token,
        session_id = session_id, 
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


@app.route("/language/<language>")
def set_language(language=None):
    session["language"] = language
    return redirect(request.referrer)


if __name__ == "__main__":
    app.debug = os.environ.get("IS_DEBUG", False)
    port = int(os.environ.get("PORT", 5001))
    app.run(port=port)
