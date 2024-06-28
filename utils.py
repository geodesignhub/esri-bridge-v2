from arcgis.gis import GIS
from conn import get_redis
from data_definitions import (
    ExportToArcGISRequestPayload,
    AGOLItemDetails,
    AGOLExportStatus,
)
import geojson
from geojson import FeatureCollection
import json
from dataclasses import asdict
from data_definitions import AGOLItemDetails
import logging
import tempfile
import os

logger = logging.getLogger("esri-gdh-bridge")
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
ENV_FILE = find_dotenv()

if ENV_FILE:
    load_dotenv(ENV_FILE)
r = get_redis()


class ArcGISHelper:
    def __init__(self, agol_token: str):
        self.agol_token = agol_token

    def create_gis_object(self) -> GIS:
        gis = GIS("https://www.arcgis.com/", token=self.agol_token)
        return gis

    def check_if_gis_object_exists(self, design_id: str, gis: GIS) -> bool:
        object_already_exists = False
        search_results = gis.content.search(
            query=f"description:{design_id}", item_type="GeoJson"
        )
        if search_results:
            object_already_exists = True

        return object_already_exists


def export_design_json_to_agol(submit_to_arcgis_request: ExportToArcGISRequestPayload):

    _gdh_design_details = submit_to_arcgis_request.gdh_design_details
    agol_token = submit_to_arcgis_request.agol_token
    my_arcgis_helper = ArcGISHelper(agol_token=agol_token)
    gis = my_arcgis_helper.create_gis_object()
    design_id = _gdh_design_details.design_id
    design_exists_in_profile = my_arcgis_helper.check_if_gis_object_exists(
        gis=gis, design_id=design_id
    )
    submission_processing_result_key = "{session_id}_status".format(
        session_id=submit_to_arcgis_request.session_id
    )
    agol_export_status = AGOLExportStatus(status=0, message="", success_url="")

    if design_exists_in_profile:
        logger.info("Design already exists in profile, it cannot be  re-uploaded")
        agol_export_status.status = 0
        agol_export_status.message = "A design with the same ID already exists in your profile in ArcGIS Online, you must delete that first in ArcGIS Online and try the migration again."

    else:
        _gdh_design_feature_collection: FeatureCollection = (
            _gdh_design_details.design_geojson.geojson
        )
        agol_item_details = AGOLItemDetails(
            title=_gdh_design_details.design_name,
            snippet=_gdh_design_details.project_id,
            description=_gdh_design_details.design_id,
            type="GeoJson",
        )

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as output:
            output.write(geojson.dumps(_gdh_design_feature_collection))

        geojson_item = gis.content.add(
            item_properties=asdict(agol_item_details), data=output.name
        )
        os.unlink(output.name)
        output.delete = True

        feature_layer_item = geojson_item.publish(file_type="geojson")
        agol_export_status.status = 1
        agol_export_status.success_url = feature_layer_item.url
        agol_export_status.message = (
            "Successfully created Feature Layer on ArcGIS Online"
        )
    print(submission_processing_result_key)
    r.set(submission_processing_result_key, json.dumps(asdict(agol_export_status)))
    r.expire(submission_processing_result_key, time=6000)
