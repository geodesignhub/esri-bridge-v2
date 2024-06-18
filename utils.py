from arcgis.gis import GIS
from conn import get_redis
from data_definitions import AGOLGeoJSONUploadPayload, ExportToArcGISRequestPayload, GeodesignhubFeatureProperties
from geojson import Point, Polygon, LineString, Feature, FeatureCollection
from typing import List
from dataclasses import asdict
from os import environ
from dacite import from_dict
from data_definitions import AGOLGeoJSONUploadPayload
import logging
logger = logging.getLogger("esri-gdh-bridge")
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
ENV_FILE = find_dotenv()

if ENV_FILE:
    load_dotenv(ENV_FILE)
r = get_redis()

class ArcGISHelper():
    def __init__(self, agol_token: str):
        self.agol_token = agol_token
        # self.client_id = client_id

    def create_gis_object(self)->GIS:
        gis = GIS("https://igcollab.maps.arcgis.com/",token = self.agol_token)
        return gis

def export_design_json_to_agol(submit_to_arcgis_request: ExportToArcGISRequestPayload):
    
    _gdh_design_details = submit_to_arcgis_request.gdh_design_details
    agol_token = submit_to_arcgis_request.agol_token
    # my_arcgis_helper = ArcGISHelper(agol_token= agol_token)
    # gis = my_arcgis_helper.create_gis_object()

    _gdh_design_feature_collection:FeatureCollection = _gdh_design_details.design_geojson.geojson
    # point_feature_list: List[Feature] = []
    # linestring_feature_list: List[Feature] = []
    # polygon_feature_list: List[Feature] = []

    for feature in _gdh_design_feature_collection['features']:
        _feature_properties = from_dict(data_class = GeodesignhubFeatureProperties, data = feature['properties'])
        _feature_properties.design_title = _gdh_design_details.design_name       
        
        feature['properties'] = {}
        print(_feature_properties)
        print(feature)
        
        # feature_item = gis.content.add(json.loads(json.dumps(asdict(_feature_properties))), feature)
        # feature_item.publish()
        
