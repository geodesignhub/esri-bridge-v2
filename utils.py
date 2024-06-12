
from data_definitions import (
    ExportToArcGISRequestPayload
)
from arcgis.gis import GIS
from conn import get_redis
from dacite import from_dict

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
    agol_token = submit_to_arcgis_request.agol_token
    my_arcgis_helper = ArcGISHelper(agol_token= agol_token)
    gis = my_arcgis_helper.create_gis_object()
    pass
    # _roads_download_request = from_dict(
    #     data_class=RoadsDownloadRequest, data=roads_download_request
    # )
    # bounds = _roads_download_request.bounds
    # roads_url = _roads_download_request.roads_url
    # session_roads_key = (
    #     _roads_download_request.session_id
    #     + ":"
    #     + _roads_download_request.request_date_time
    #     + ":"
    #     + "roads"
    # )
    # bounds_hash = hashlib.sha512(bounds.encode("utf-8")).hexdigest()

    # """A function to download roads GeoJSON from GDH data server for the given bounds,  """
    # fc = {"type": "FeatureCollection", "features": []}
    # roads_storage_key = bounds_hash[:15] + ":roads"
    # r.set(session_roads_key, roads_storage_key)
    # r.expire(session_roads_key, time=6000)

    # if r.exists(roads_storage_key):
    #     fc_str = r.get(roads_storage_key)
    #     fc = json.loads(fc_str)

    # else:
    #     bounds_filtering = os.getenv("USE_BOUNDS_FILTERING", None)
    #     if bounds_filtering:
    #         # If bounds filtering is enabled, the bounds parameter in the URL is replaced with the current bounds
    #         r_url = roads_url.replace("__bounds__", bounds)
    #     else:
    #         r_url = roads_url
    #     download_request = requests.get(r_url)
    #     if download_request.status_code == 200:
    #         fc = download_request.json()
    #         r.set(roads_storage_key, json.dumps(fc))
    #     else:
    #         print("Error in setting downloaded roads to local memory")
    #         r.set(
    #             roads_storage_key,
    #             json.dumps({"type": "FeatureCollection", "features": []}),
    #         )

    #     r.expire(roads_storage_key, time=60000)

    # return fc

