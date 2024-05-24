#!/usr/bin/env python3
from flask import Flask
from .data_definitions import ErrorResponse
from flask import request, Response
from dotenv import load_dotenv, find_dotenv
import os
from flask import session, redirect
from dataclasses import asdict
app = Flask(__name__)

load_dotenv(find_dotenv())
ENV_FILE = find_dotenv()
if ENV_FILE:
    load_dotenv(ENV_FILE)
base_dir = os.path.abspath(os.path.dirname(__file__))

MIMETYPE = "application/json"

@app.route("/export/", methods=["GET"])
def export_design():
    """This is the root of the webservice, upon successful authentication a text will be displayed in the browser"""
    try:
        projectid = request.args.get("projectid")
        apitoken = request.args.get("apitoken")
        diagramid = request.args.get("diagramid")

    except KeyError:
        error_msg = ErrorResponse(
            status=0,
            message="Could not parse Project ID, Diagram ID or API Token ID. One or more of these were not found in your JSON request.",
            code=400,
        )
                
    return Response(asdict(error_msg), status=400, mimetype=MIMETYPE)



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
