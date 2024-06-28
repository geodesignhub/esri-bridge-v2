from data_definitions import (
    ErrorResponse,
    GeodesignhubProjectBounds,
    GeodesignhubSystem,
    GeodesignhubProjectData,
    GeodesignhubDesignFeatureProperties,
    GeodesignhubFeatureProperties,
    GeodesignhubProjectCenter,
    GeodesignhubProjectTags,
    GeodesignhubSystemDetail,
)
import json
from shapely.geometry.base import BaseGeometry
from json import encoder
from shapely.geometry import mapping
from dacite import from_dict
from typing import List, Union
from geojson import Feature, FeatureCollection, Polygon, LineString
import GeodesignHub
from dataclasses import asdict
import config


from uuid import uuid4


class ShapelyEncoder(json.JSONEncoder):
    """Encodes JSON strings into shapes processed by Shapely"""

    def default(self, obj):
        if isinstance(obj, BaseGeometry):
            return mapping(obj)
        return json.JSONEncoder.default(self, obj)


def export_to_json(data):
    """Export a shapely output to JSON"""
    encoder.FLOAT_REPR = lambda o: format(o, ".6f")
    return json.loads(json.dumps(data, sort_keys=True, cls=ShapelyEncoder))


class GeodesignhubDataDownloader:
    """
    A class to download and process data from Geodesignhub
    """

    def __init__(
        self,
        session_id: uuid4,
        project_id: str,
        apitoken: str,
        cteam_id=None,
        synthesis_id=None,
        diagram_id=None,
    ):
        self.session_id = session_id
        self.project_id = project_id
        self.apitoken = apitoken
        self.cteam_id = cteam_id
        self.synthesis_id = synthesis_id
        d = int(diagram_id) if diagram_id else None
        self.diagram_id = d
        self.api_helper = GeodesignHub.GeodesignHubClient(
            url=config.apisettings["serviceurl"],
            project_id=self.project_id,
            token=self.apitoken,
        )

    def download_project_systems(
        self,
    ) -> Union[ErrorResponse, List[GeodesignhubSystem]]:
        s = self.api_helper.get_all_systems()
        # Check responses / data
        try:
            assert s.status_code == 200
        except AssertionError:
            error_msg = ErrorResponse(
                status=0,
                message="Could not parse Project ID, Diagram ID or API Token ID. One or more of these were not found in your JSON request.",
                code=400,
            )

            return error_msg

        systems = s.json()
        all_systems: List[GeodesignhubSystem] = []
        for s in systems:
            current_system = from_dict(data_class=GeodesignhubSystem, data=s)
            all_systems.append(current_system)

        return all_systems

    def download_project_bounds(
        self,
    ) -> Union[ErrorResponse, GeodesignhubProjectBounds]:
        b = self.api_helper.get_project_bounds()
        try:
            assert b.status_code == 200
        except AssertionError:
            error_msg = ErrorResponse(
                status=0,
                message="Could not parse Project ID, Diagram ID or API Token ID. One or more of these were not found in your JSON request.",
                code=400,
            )
            return error_msg

        bounds = from_dict(data_class=GeodesignhubProjectBounds, data=b.json())

        return bounds

    def download_project_tags(self) -> Union[ErrorResponse, GeodesignhubProjectTags]:
        t = self.api_helper.get_project_tags()
        try:
            assert t.status_code == 200
        except AssertionError:
            error_msg = ErrorResponse(
                status=0,
                message="Could not parse Project ID, Diagram ID or API Token ID. One or more of these were not found in your JSON request.",
                code=400,
            )
            return error_msg
        return t.json()

    def download_project_center(
        self,
    ) -> Union[ErrorResponse, GeodesignhubProjectCenter]:
        c = self.api_helper.get_project_center()
        try:
            assert c.status_code == 200
        except AssertionError:
            error_msg = ErrorResponse(
                status=0,
                message="Could not parse Project ID, Diagram ID or API Token ID. One or more of these were not found in your JSON request.",
                code=400,
            )

            return error_msg
        center = from_dict(data_class=GeodesignhubProjectCenter, data=c.json())
        return center

    def download_design_details_from_geodesignhub(
        self,
    ):
        r = self.api_helper.get_single_synthesis_details(
            teamid=int(self.cteam_id), synthesisid=self.synthesis_id
        )

        try:
            assert r.status_code == 200
        except AssertionError:
            error_msg = ErrorResponse(
                status=0,
                message="Could not parse Project ID, Diagram ID or API Token ID. One or more of these were not found in your JSON request.",
                code=400,
            )
            return error_msg

        _design_details_raw = r.json()

        return _design_details_raw

    def parse_transform_geojson(self, design_feature_collection) -> FeatureCollection:
        _design_details_feature_collection = design_feature_collection["geojson"]        
        _all_features: List[Feature] = []
        for f in _design_details_feature_collection["features"]:
            _diagram_properties_raw = {}
            _f_props = f["properties"]            
            _diagram_properties_raw["diagram_id"] = _f_props["diagramid"]
            _diagram_properties_raw["project_or_policy"] = _f_props["areatype"]
            _diagram_properties_raw["diagram_name"] = _f_props["description"]
            _diagram_properties_raw["color"] = _f_props["color"]
            _diagram_properties_raw["tag_codes"] = _f_props["tag_codes"]
            _diagram_properties_raw["notes"] = _f_props["notes"]
            _diagram_properties_raw["start_date"] = _f_props["start_date"]
            _diagram_properties_raw["end_date"] = _f_props["end_date"]
            _diagram_properties_raw["grid_location"] = _f_props["grid_location"]                      

            _feature_properties = from_dict(
                data_class=GeodesignhubFeatureProperties, data=_diagram_properties_raw
            )

            # We assume that GDH will provide a polygon
            if f["geometry"]["type"] == "Polygon":
                _geometry = Polygon(coordinates=f["geometry"]["coordinates"])
            elif f["geometry"]["type"] == "LineString":
                _geometry = LineString(coordinates=f["geometry"]["coordinates"])
            else:
                return None
            _feature = Feature(geometry=_geometry, properties=asdict(_feature_properties))
            _all_features.append(_feature)

        _diagram_feature_collection = FeatureCollection(features=_all_features)
        
        return _diagram_feature_collection

    def download_design_data_from_geodesignhub(
        self,
    ) -> Union[ErrorResponse, dict]:
        r = self.api_helper.get_single_synthesis(
            teamid=int(self.cteam_id), synthesisid=self.synthesis_id
        )

        try:
            assert r.status_code == 200
        except AssertionError:
            error_msg = ErrorResponse(
                status=0,
                message="Could not parse Project ID, Diagram ID or API Token ID. One or more of these were not found in your JSON request.",
                code=400,
            )
            return error_msg

        _esri_design_details_raw = r.json()

        return _esri_design_details_raw

    def download_esri_design_data_from_geodesignhub(
        self,
    ) -> Union[ErrorResponse, dict]:
        r = self.api_helper.get_single_synthesis_esri_json(
            teamid=int(self.cteam_id), synthesisid=self.synthesis_id
        )

        try:
            assert r.status_code == 200
        except AssertionError:
            error_msg = ErrorResponse(
                status=0,
                message="Could not parse Project ID, Diagram ID or API Token ID. One or more of these were not found in your JSON request.",
                code=400,
            )
            return error_msg

        _esri_design_details_raw = r.json()

        return _esri_design_details_raw

    def download_project_data_from_geodesignhub(
        self,
    ) -> Union[ErrorResponse, GeodesignhubProjectData]:
        my_api_helper = GeodesignHub.GeodesignHubClient(
            url=config.apisettings["serviceurl"],
            project_id=self.project_id,
            token=self.apitoken,
        )
        # Download Data
        s = my_api_helper.get_all_systems()
        b = my_api_helper.get_project_bounds()
        c = my_api_helper.get_project_center()
        t = my_api_helper.get_project_tags()

        # Check responses / data
        try:
            assert s.status_code == 200
        except AssertionError:
            error_msg = ErrorResponse(
                status=0,
                message="Could not parse Project ID, Diagram ID or API Token ID. One or more of these were not found in your JSON request.",
                code=400,
            )
            return error_msg

        systems = s.json()
        all_systems: List[GeodesignhubSystem] = []
        all_system_details: List[GeodesignhubSystemDetail] = []
        for s in systems:
            current_system = from_dict(data_class=GeodesignhubSystem, data=s)
            sd = my_api_helper.get_single_system(system_id=current_system.id)
            sd_raw = sd.json()
            current_system_details = from_dict(
                data_class=GeodesignhubSystemDetail, data=sd_raw
            )
            all_system_details.append(current_system_details)
            all_systems.append(current_system)

        try:
            assert b.status_code == 200
        except AssertionError:
            error_msg = ErrorResponse(
                status=0,
                message="Could not parse Project ID, Diagram ID or API Token ID. One or more of these were not found in your JSON request.",
                code=400,
            )
            return error_msg

        center = from_dict(data_class=GeodesignhubProjectCenter, data=c.json())
        bounds = from_dict(data_class=GeodesignhubProjectBounds, data=b.json())
        tags = from_dict(data_class=GeodesignhubProjectTags, data={"tags": t.json()})
        project_data = GeodesignhubProjectData(
            systems=all_systems,
            system_details=all_system_details,
            bounds=bounds,
            center=center,
            tags=tags,
        )

        return project_data
