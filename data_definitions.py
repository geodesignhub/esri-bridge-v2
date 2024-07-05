from dataclasses import dataclass
from typing import List
from geojson import FeatureCollection
from enum import Enum


def custom_asdict_factory(data):

    def convert_value(obj):
        if isinstance(obj, Enum):
            return obj.value
        return obj

    return dict((k, convert_value(v)) for k, v in data)


@dataclass
class GeodesignhubDiagramGeoJSON:
    # Source: https://www.geodesignhub.com/api/#diagrams-api-diagram-detail-get
    geojson: FeatureCollection


@dataclass
class ErrorResponse:
    # A class to hold error resposnes
    message: str
    code: int
    status: int


class MessageType(str, Enum):
    primary = "primary"
    secondary = "secondary"
    success = "success"
    danger = "danger"
    warning = "warning"
    info = "info"
    light = "light"
    dark = "dark"


@dataclass
class GeodesignhubFeatureProperties:
    project_or_policy: str
    diagram_name: str
    color: str
    diagram_id: int
    tag_codes: str
    start_date: str
    end_date: str
    notes: str
    grid_location: str
    system_name: str


@dataclass
class VolumeInformation:
    min_height: float
    max_height: float


@dataclass
class ExportConfirmationPayload:
    agol_token: str
    agol_project_id: str
    message: str
    message_type: MessageType
    geodesignhub_design_feature_count: int
    geodesignhub_design_name: str
    session_id: str


@dataclass
class AGOLGeoJSONUploadPayload:
    design_title: str
    diagram_name: str
    design_id: str
    diagram_id: str
    project_or_policy: str
    tag_codes: str
    start_date: str
    end_date: str
    type: str = "GeoJson"


@dataclass
class GeodesignhubDesignFeatureProperties:
    author: str
    description: str
    height: float
    base_height: float
    color: str
    diagram_id: int
    building_id: str
    areatype: str
    volume_information: VolumeInformation
    tag_codes: str


@dataclass
class AGOLItemDetails:
    title: str
    snippet: str
    description: str
    type: str


@dataclass
class GeodesignhubDesignDetail:
    description: str
    creationdate: str
    id: str


@dataclass
class GeodesignhubTeamDesigns:
    designs: List[GeodesignhubDesignDetail]


@dataclass
class GeodesignhubDesignGeoJSON:
    geojson: FeatureCollection


@dataclass
class GeodesignhubDataStorage:
    design_geojson: GeodesignhubDesignGeoJSON
    design_id: str
    design_team_id: str
    project_id: str
    design_name: str


@dataclass
class ExportToArcGISRequestPayload:
    agol_token: str
    agol_project_id: str
    gdh_design_details: GeodesignhubDataStorage
    session_id: str


@dataclass
class GeodesignhubSystem:
    # Source: https://www.geodesignhub.com/api/#systems-api-systems-collection-get
    id: int
    sysname: str
    syscolor: str


@dataclass
class GeodesignhubSystemDetail:
    id: int
    sysname: str
    syscolor: str
    systag: str
    syscost: int
    sysbudget: int
    current_ha: float
    target_ha: float
    verbose_description: str


@dataclass
class AllSystemDetails:
    systems: List[GeodesignhubSystemDetail]


@dataclass
class GeodesignhubProjectBounds:

    bounds: str


@dataclass
class GeodesignhubProjectTag:
    id: str
    tag: str
    slug: str
    code: str
    diagrams: List[int]


@dataclass
class GeodesignhubProjectTags:

    tags: List[GeodesignhubProjectTag]


@dataclass
class GeodesignhubProjectCenter:
    center: str


@dataclass
class GeodesignhubProjectData:
    systems: List[GeodesignhubSystem]
    system_details: List[GeodesignhubSystemDetail]
    bounds: GeodesignhubProjectBounds
    center: GeodesignhubProjectCenter
    tags: GeodesignhubProjectTags


@dataclass
class AGOLExportStatus:
    status: int
    message: str
    success_url: str
