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
    def check_if_gis_object_exists(self, design_id:str, gis:GIS)->bool:
        object_already_exists = False
    
        search_response = gis.content.search(
            query=f"description:{design_id}", item_type="GeoJson"
        )
        search_results = search_response["results"]
        if len(search_results) > 0:
            object_already_exists = True

        return object_already_exists


def export_design_json_to_agol(submit_to_arcgis_request: ExportToArcGISRequestPayload):

    _gdh_design_details = submit_to_arcgis_request.gdh_design_details
    agol_token = submit_to_arcgis_request.agol_token
    my_arcgis_helper = ArcGISHelper(agol_token=agol_token)
    gis = my_arcgis_helper.create_gis_object()
    design_id = _gdh_design_details.design_id
    design_exists_in_profile = my_arcgis_helper.check_if_gis_object_exists(gis= gis, design_id = design_id)

    if design_exists_in_profile: 
        logger.info("Design already exists in profile, cannot re-upload it")
    else:

        _gdh_design_feature_collection: FeatureCollection = (
            _gdh_design_details.design_geojson.geojson
        )
        agol_item_details = AGOLItemDetails(
            title=_gdh_design_details.design_id,
            snippet=_gdh_design_details.project_id,
            description=_gdh_design_details.design_id,
            type="GeoJson",
        )
        
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as output:
            output.write(geojson.dumps(_gdh_design_feature_collection))


        geojson_item = gis.content.add(item_properties= asdict(agol_item_details), data= output.name
        )
        os.unlink(output.name)
        output.delete = True

        feature_layer_item = geojson_item.publish(file_type='geojson')
        print(feature_layer_item.url)
        
        # TODO: Display the FL title etc. from the ArcGIS link
        # Show me the item
        # Show me the map
