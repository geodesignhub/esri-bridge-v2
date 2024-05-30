#!/usr/bin/env python3
from flask import Flask
from data_definitions import ErrorResponse, ExportConfirmationPayload, MessageType, custom_asdict_factory
from flask import request, Response
from dotenv import load_dotenv, find_dotenv
import os
from flask import session, redirect
from dataclasses import asdict
from flask import render_template
from esri_bridge import create_app
import uuid


app = Flask(__name__)
load_dotenv(find_dotenv())
ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)
base_dir = os.path.abspath(os.path.dirname(__file__))

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


@app.route("/export/", methods=["GET"])
def export_design():
    """This is the root of the webservice, upon successful authentication a text will be displayed in the browser"""
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
    # Download Design from Geodesignhub
    # Cache it
    session_id = uuid.uuid4()
    confirmation_message = "Ready for migration"
    message_type = MessageType.success
    export_confirmation_payload = ExportConfirmationPayload(
        agol_token=agol_token,
        agol_project_id=agol_project_id,
        message_type=message_type,
        message=confirmation_message,
        geodesignhub_design_feature_count=10,
        geodesignhub_design_name="V2",
        session_id=session_id,
    )

    return render_template("export.html", data=asdict(export_confirmation_payload, dict_factory= custom_asdict_factory))


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
