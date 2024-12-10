from dataclasses import dataclass, field, asdict
from typing import List, Union, Dict, Optional
from geojson import FeatureCollection
from enum import Enum
from arcgis.gis import Item
from arcgis.mapping import WebMap


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
    # A class to hold error responses
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
class ArcGISDesignPayload:
    gdh_design_details: GeodesignhubDataStorage


@dataclass
class GeodesignhubSystem:
    # Source: https://www.geodesignhub.com/api/#systems-api-systems-collection-get
    id: int
    name: str
    color: str
    verbose_description: str

@dataclass
class GeodesignhubProjectDetails:
    id: str
    project_title: str
    project_description: str
    
@dataclass
class GeodesignhubSystemDetail:
    id: int
    name: str
    color: str
    tag: str
    cost: int
    budget: int
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


@dataclass
class AGOLSubmissionPayload:
    design_data: GeodesignhubDataStorage
    tags_data: GeodesignhubProjectTags
    agol_token: str
    agol_project_id: str
    session_id: str
    gdh_systems_information: AllSystemDetails


@dataclass
class AGOLFeatureLayerPublishingResponse:
    status: int
    item: Union[None, Item]
    url: str


@dataclass
class AGOLWebMapPublishingResponse:
    status: int
    item: Union[None, WebMap]


@dataclass
class ESRIFieldDefinition:
    name: str
    type_: str
    sqlType: str
    alias: str
    precision: int
    Noneable: bool = True
    editable: bool = False
    domain: str = None
    defaultValue: str = None
    length: Optional[int] = 0

    @staticmethod
    def dict_factory(x):
        raw_dict = {k: v for (k, v) in x}
        # Remove the length property
        if raw_dict["length"] == 0 and raw_dict["precision"] != 0:
            raw_dict.pop("length")
        # Remove the precision property
        if raw_dict["precision"] == 0:
            raw_dict.pop("precision")
        raw_dict["type"] = raw_dict["type_"]
        raw_dict.pop("type_")
        return raw_dict


@dataclass
class ESRIField:
    definition: ESRIFieldDefinition


@dataclass
class ESRIFeatureLayer:
    name: str
    geometryType: str
    objectIdField: str
    fields: List[ESRIField]
    type_: str = "Feature Layer"

    @staticmethod
    def dict_factory(x):
        raw_dict = {k: v for (k, v) in x}
        raw_dict["type"] = raw_dict["type_"]
        raw_dict.pop("type_")
        return raw_dict


@dataclass
class AGOLItemSchema:
    field_definitions: List[ESRIFieldDefinition]
    item_name: str
    esri_fields_schema: List[ESRIField] = field(init=False)
    publish_parameters: Dict[str, any] = field(init=False)

    def __post_init__(self):
        self.esri_fields_schema = [
            asdict(fd, dict_factory=ESRIFieldDefinition.dict_factory)
            for fd in self.field_definitions
        ]

        self.publish_parameters = {
            "type": "geojson",
            "name": self.item_name,
            "layers": [
                asdict(
                    ESRIFeatureLayer(
                        name=f"{self.item_name}_polygons",
                        geometryType="esriGeometryPolygon",
                        objectIdField="ObjectId",
                        fields=self.esri_fields_schema,
                    ),
                    dict_factory=ESRIFeatureLayer.dict_factory,
                ),
                asdict(
                    ESRIFeatureLayer(
                        name=f"{self.item_name}_points",
                        geometryType="esriGeometryPoint",
                        objectIdField="ObjectId",
                        fields=self.esri_fields_schema,
                    ),
                    dict_factory=ESRIFeatureLayer.dict_factory,
                ),
                asdict(
                    ESRIFeatureLayer(
                        name=f"{self.item_name}_lines",
                        geometryType="esriGeometryPolyline",
                        objectIdField="ObjectId",
                        fields=self.esri_fields_schema,
                    ),
                    dict_factory=ESRIFeatureLayer.dict_factory,
                ),
            ],
        }
