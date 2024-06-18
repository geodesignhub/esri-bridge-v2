from arcgis.gis import GIS
from conn import get_redis
from data_definitions import AGOLGeoJSONUploadPayload
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
ENV_FILE = find_dotenv()

if ENV_FILE:
    load_dotenv(ENV_FILE)
r = get_redis()

class ArcGISHelper():
    """ A class to help connect to AGOL, called async at this time"""
    def __init__(self, agol_token: str):
        self.agol_token = agol_token

    def create_gis_object(self)->GIS:
        gis = GIS("https://igcollab.maps.arcgis.com/",token = self.agol_token)
        return gis

def export_design_json_to_agol(submit_to_arcgis_request):
    
    _gdh_design_details = submit_to_arcgis_request.gdh_design_details
    agol_token = submit_to_arcgis_request.agol_token
    my_arcgis_helper = ArcGISHelper(agol_token= agol_token)
    gis = my_arcgis_helper.create_gis_object()

    _gdh_design_feature_collection = _gdh_design_details.design_geojson.geojson

    for feature in _gdh_design_feature_collection['features']:
        feature['properties'] = {}
        feature_layer_properties = AGOLGeoJSONUploadPayload(
        title= _gdh_design_details.design_name,
        description= "Geodesignhub design ID {design_id}".format(design_id = _gdh_design_details.design_id), 
        diagram_id= 10,)
        print(feature_layer_properties)
        print(feature)
        
        # feature_item = gis.content.add(json.loads(json.dumps(asdict(feature_layer_properties))), feature)
        # feature_item.publish()
        
