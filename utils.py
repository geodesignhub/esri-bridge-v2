from arcgis.gis import GIS
from conn import get_redis
from data_definitions import (
    ExportToArcGISRequestPayload,    
    AGOLItemDetails,
)
import geojson
from geojson import FeatureCollection
import json
from dataclasses import asdict
from data_definitions import AGOLItemDetails
import logging

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
        # self.client_id = client_id

    def create_gis_object(self) -> GIS:
        gis = GIS("https://www.arcgis.com/", token=self.agol_token)
        return gis


def export_design_json_to_agol(submit_to_arcgis_request: ExportToArcGISRequestPayload):

    _gdh_design_details = submit_to_arcgis_request.gdh_design_details
    agol_token = submit_to_arcgis_request.agol_token
    my_arcgis_helper = ArcGISHelper(agol_token=agol_token)
    gis = my_arcgis_helper.create_gis_object()

    _gdh_design_feature_collection: FeatureCollection = (
        _gdh_design_details.design_geojson.geojson
    )
    agol_item_details = AGOLItemDetails(
        title=_gdh_design_details.design_name,
        snippet=_gdh_design_details.project_id,
        description=_gdh_design_details.design_id,
        type="GeoJson",
    )

    geojson_item = gis.content.add(
        json.loads(json.dumps(asdict(agol_item_details))), json.loads(geojson.dumps(_gdh_design_feature_collection))
    )
    feature_layer_item = geojson_item.publish()
    # TODO: Display the FL title etc. from the ArcGIS link
    # Show me the item
    # Show me the map
