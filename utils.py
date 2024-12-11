from arcgis.gis import GIS, Item
from conn import get_redis
import time
from typing import Union
from data_definitions import (
    ArcGISDesignPayload,
    AGOLItemDetails,
    AGOLExportStatus,
    AGOLSubmissionPayload,
    GeodesignhubProjectTags,
    AllSystemDetails,
    AGOLFeatureLayerPublishingResponse,
)
from PIL import ImageColor
import geojson
from geojson import FeatureCollection
import json
from dataclasses import asdict
import logging
import tempfile
import os
import pandas as pd
from arcgis.mapping import WebMap
from storymap_helper import StoryMapPublisher
from esri_fields_schema_helper import AGOLItemSchemaGenerator

logger = logging.getLogger("esri-gdh-bridge")
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
ENV_FILE = find_dotenv()

if ENV_FILE:
    load_dotenv(ENV_FILE)
r = get_redis()


def publish_design_to_agol(agol_submission_payload: AGOLSubmissionPayload):
    """This method one by one submits the designs and the tags data to AGOL"""
    agol_token = agol_submission_payload.agol_token
    my_arc_gis_helper = ArcGISHelper(agol_token)
    agol_export_status = AGOLExportStatus(status=0, message="", success_url="")

    submission_status_details = my_arc_gis_helper.export_design_json_to_agol(
        design_data=agol_submission_payload.design_data,
        gdh_systems_information=agol_submission_payload.gdh_systems_information,
    )

    if submission_status_details.status == 0:
        agol_export_status.status = 0
        agol_export_status.message = "A design with the same ID already exists in your profile in ArcGIS Online, you must delete that first in ArcGIS Online and try the migration again."
    else:
        agol_export_status.status = 1
        agol_export_status.success_url = submission_status_details.url
        agol_export_status.message = (
            "Successfully created Feature Layer on ArcGIS Online"
        )
    logger.info(
        "Found {num_tags} tags in Geodesignhub".format(
            num_tags=len(agol_submission_payload.tags_data.tags)
        )
    )
    if len(agol_submission_payload.tags_data.tags):
        my_arc_gis_helper.export_project_tags_to_agol(
            tags_data=agol_submission_payload.tags_data,
            project_id=agol_submission_payload.design_data.gdh_design_details.project_id,
        )
    submission_processing_result_key = "{session_id}_status".format(
        session_id=agol_submission_payload.session_id
    )

    # Create a web map and publish it
    if submission_status_details.status:
        # Sleep for 10 seconds to allow for layers to be updated
        # logging.info("Sleeping for 15 seconds to allow for publishing...")
        # time.sleep(15)
        my_webmap_item = my_arc_gis_helper.publish_feature_layer_as_webmap(
            feature_layer_item=submission_status_details.item,
            design_data=agol_submission_payload.design_data,
            gdh_systems_information=agol_submission_payload.gdh_systems_information,
        )
        my_storymap_publisher = StoryMapPublisher(
            design_data=agol_submission_payload.design_data,
            gdh_systems_information=agol_submission_payload.gdh_systems_information,
            negotiated_design_item_id=my_webmap_item.itemid,
            gdh_project_details = agol_submission_payload.gdh_project_details,
            gis=my_arc_gis_helper.get_gis(),
        )
        my_storymap_publisher.publish_storymap()

    r.set(submission_processing_result_key, json.dumps(asdict(agol_export_status)))
    r.expire(submission_processing_result_key, time=6000)


class ArcGISHelper:
    def __init__(self, agol_token: str):
        self.agol_token = agol_token
        self.gis = self.create_gis_object()

    def get_gis(self) -> GIS:
        return self.gis

    def create_gis_object(self) -> GIS:
        gis = GIS("https://www.arcgis.com/", token=self.agol_token)
        return gis

    def check_if_tags_exist(self, project_id: str, gis: GIS) -> bool:
        object_already_exists = False
        search_results = gis.content.search(
            query=f"snippet:{project_id}", item_type="CSV"
        )
        if search_results:
            object_already_exists = True

        return object_already_exists

    def check_if_design_exists(self, design_id: str, gis: GIS) -> bool:
        object_already_exists = False
        search_results = gis.content.search(
            query=f"description:{design_id}", item_type="GeoJson"
        )
        if search_results:
            object_already_exists = True

        return object_already_exists

    def export_project_tags_to_agol(
        self, tags_data: GeodesignhubProjectTags, project_id: str
    ) -> Union[int, Item]:
        """This method exports project tags as a CSV file"""

        _all_gdh_project_tags = tags_data
        t = asdict(_all_gdh_project_tags)

        tags_df = pd.json_normalize(t["tags"])

        agol_item_details = AGOLItemDetails(
            title=f"Tags for {project_id}",
            snippet=project_id,
            description="All project tags as a CSV",
            type="CSV",
        )

        tags_exist_in_profile = self.check_if_tags_exist(
            gis=self.gis, project_id=project_id
        )
        if tags_exist_in_profile:
            logger.info("Design already exists in profile, it cannot be re-uploaded")
            return 0

        else:
            temp_csv_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
            tags_df.to_csv(temp_csv_file.name, encoding="utf-8", index=False)
            logger.info("Uploading tags to AGOL...")
            csv_item = self.gis.content.add(
                item_properties=asdict(agol_item_details), data=temp_csv_file.name
            )
            logger.info("Tags uploaded successfully...")
            os.unlink(temp_csv_file.name)
            temp_csv_file.delete = True

            published_item = csv_item.publish()
            return published_item

    def create_uv_infos(
        self, gdh_project_systems: AllSystemDetails, geometry_type: str
    ):
        """Create unique value information for AGOL"""
        unique_value_infos = []
        for project_system in gdh_project_systems.systems:
            system_id = project_system.id
            name = project_system.name
            verbose_description = project_system.verbose_description
            color = project_system.color
            _symbol = self.create_symbol(geometry_type, color)
            unique_value_infos.append(
                {
                    "value": name,
                    "label": name,  # or verbose_description if available
                    "description": verbose_description,  # or verbose_description if available
                    "symbol": _symbol,
                }
            )

        return unique_value_infos

    def create_symbol(self, geometry_type, symbol_color, opacity=0.65):
        """Create a symbol for AGOL"""
        _symbol_type_by_geometry = {
            "esriGeometryPolygon": "esriSFS",
            "esriGeometryPolyline": "esriSLS",
            "esriGeometryPoint": "esriSMS",
        }
        (r, g, b) = ImageColor.getcolor(symbol_color, mode="RGB")
        alpha = opacity * 255
        _symbol_type = _symbol_type_by_geometry[geometry_type]
        return {
            "type": _symbol_type,
            "style": "esriSFSSolid",
            "color": (r, g, b, alpha),
            "outline": None,
        }

    def create_uv_renderer(
        self,
        geometry_type: str,
        unique_field_name: str,
        gdh_project_systems: AllSystemDetails,
    ):
        """Create a renderer based on the field and system details"""
        _uv_infos = self.create_uv_infos(gdh_project_systems, geometry_type)
        return {
            "type": "uniqueValue",
            "field1": unique_field_name,
            "field2": "",
            "field3": "",
            "fieldDelimiter": ",",
            "defaultSymbol": self.create_symbol(
                geometry_type=geometry_type, symbol_color="#cccccc"
            ),
            "defaultLabel": "Other System",
            "uniqueValueInfos": _uv_infos,
        }

    def publish_feature_layer_as_webmap(
        self,
        feature_layer_item: Item,
        design_data: ArcGISDesignPayload,
        gdh_systems_information: AllSystemDetails,
    ) -> Item:
        _gdh_design_details = design_data.gdh_design_details
        logger.info("Getting the published feature layer...")
        new_published_layers = feature_layer_item.layers
        wm = WebMap()

        # Initialize extent variable to store combined extent
        combined_extent = None

        for new_published_layer in new_published_layers:
            logger.info(
                f"{new_published_layer.properties.name} - {new_published_layer.properties.geometryType}"
            )

            logger.info("Getting the layer manager...")
            # the layer manager
            my_layer_manager = new_published_layer.manager
            # update layer renderer
            logger.info("Update layer renderer...")
            renderer = self.create_uv_renderer(
                geometry_type=new_published_layer.properties.geometryType,
                unique_field_name="system_name",
                gdh_project_systems=gdh_systems_information,
            )
            # set the renderer on the layer item
            new_published_layer.renderer = renderer
            # set the renderer on the layer service
            my_layer_manager.update_definition({"drawingInfo": {"renderer": renderer}})
            wm.add_layer(new_published_layer)

            # Combine extents for the webmap
            layer_extent = new_published_layer.properties.extent
            if layer_extent:
                if not combined_extent:
                    combined_extent = layer_extent
                else:
                    # Expand the combined extent to include this layer's extent
                    combined_extent = {
                        "xmin": min(combined_extent["xmin"], layer_extent["xmin"]),
                        "ymin": min(combined_extent["ymin"], layer_extent["ymin"]),
                        "xmax": max(combined_extent["xmax"], layer_extent["xmax"]),
                        "ymax": max(combined_extent["ymax"], layer_extent["ymax"]),
                        "spatialReference": layer_extent["spatialReference"],
                    }
        
        # Set the webmap's extent
        if combined_extent:
            wm.extent = combined_extent
        
        web_map_title = "Webmap for {design_name}".format(
            design_name=_gdh_design_details.design_name
        )
        web_map_properties = {
            "title": web_map_title,
            "snippet": "This map shows design synthesis details from a negotiation in Geodesignhub",
            "tags": "Geodesignhub",
            "extent": wm.extent, # Set extent property for wm
        }

        # Call the save() with web map item's properties.
        web_map_item = wm.save(item_properties=web_map_properties)
        return web_map_item

    def export_design_json_to_agol(
        self,
        design_data: ArcGISDesignPayload,
        gdh_systems_information: AllSystemDetails,
    ) -> AGOLFeatureLayerPublishingResponse:

        _gdh_design_details = design_data.gdh_design_details
        _gdh_project_systems = gdh_systems_information
        design_id = _gdh_design_details.design_id

        design_exists_in_profile = self.check_if_design_exists(
            gis=self.gis, design_id=design_id
        )
        if design_exists_in_profile:
            logger.info("Design already exists in profile, it cannot be  re-uploaded")
            return AGOLFeatureLayerPublishingResponse(status=0, item=None, url="")

        _gdh_design_feature_collection: FeatureCollection = (
            _gdh_design_details.design_geojson.geojson
        )
        agol_item_details = AGOLItemDetails(
            title=_gdh_design_details.design_name,
            snippet=_gdh_design_details.project_id,
            description=design_id,
            type="GeoJson",
        )

        with tempfile.NamedTemporaryFile(mode="w", delete=False) as output:
            output.write(geojson.dumps(_gdh_design_feature_collection))

        geojson_item = self.gis.content.add(
            item_properties=asdict(agol_item_details), data=output.name
        )
        os.unlink(output.name)
        output.delete = True
        # my_esri_field_schema_generator = AGOLItemSchemaGenerator(
        # item_name=_gdh_design_details.design_name
        # )
        # publish_parameters = my_esri_field_schema_generator.publish_parameters


        feature_layer_item = geojson_item.publish(
            file_type="geojson"
        )
        feature_layer_item_url = feature_layer_item.url
        # the layer
        logger.info("Layer is published as Feature Collection")
        logger.info("Getting the published feature layer...")
        new_published_layers = feature_layer_item.layers

        for new_published_layer in new_published_layers:
            logger.info(
                f"{new_published_layer.properties.name} - {new_published_layer.properties.geometryType}"
            )

            logger.info("Getting the layer manager...")
            # the layer manager
            test_layer_manager = new_published_layer.manager
            # update layer renderer
            logger.info("Update layer renderer...")
            test_layer_manager.update_definition(
                {
                    "drawingInfo": {
                        "renderer": self.create_uv_renderer(
                            geometry_type=new_published_layer.properties.geometryType,
                            unique_field_name="system_name",
                            gdh_project_systems=_gdh_project_systems,
                        )
                    }
                }
            )

        return AGOLFeatureLayerPublishingResponse(
            status=1, item=feature_layer_item, url=feature_layer_item_url
        )
