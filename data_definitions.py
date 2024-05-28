from dataclasses import dataclass
from typing import List
from geojson import FeatureCollection

@dataclass
class ErrorResponse:
    # A class to hold error resposnes
    message: str
    code: int
    status: int

@dataclass
class GeodesignhubFeatureProperties:
    sysid: int
    description: str
    height: float
    base_height: float
    color: str
    diagram_id: int
    building_id: str


@dataclass
class VolumeInformation:
    min_height: float
    max_height: float



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
class GeodesignhubDiagramGeoJSON:
    # Source: https://www.geodesignhub.com/api/#diagrams-api-diagram-detail-get
    geojson: FeatureCollection



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

