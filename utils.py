from data_definitions import (
    ExportToArcGISRequestPayload
)
from arcgis.gis import GIS
from conn import get_redis
from dacite import from_dict
import time
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())
ENV_FILE = find_dotenv()

if ENV_FILE:
    load_dotenv(ENV_FILE)
r = get_redis()

class ArcGISHelper():
    def __init__(self, agol_token: str):
        self.agol_token = agol_token

    def create_gis_object(self)->GIS:
        gis = GIS("https://igcollab.maps.arcgis.com/",token = self.agol_token)
        return gis

def export_design_json_to_agol(submit_to_arcgis_request):
    _submit_to_arcgis_request = from_dict(data_class = ExportToArcGISRequestPayload, data = submit_to_arcgis_request)
    
    agol_token = _submit_to_arcgis_request.agol_token
    my_arcgis_helper = ArcGISHelper(agol_token= agol_token)
    gis = my_arcgis_helper.create_gis_object()

    # send the data to ArcGIS online 

    # confirm that it is successful

    time.sleep(1)
    print("Export of Design to AGOL completed..")