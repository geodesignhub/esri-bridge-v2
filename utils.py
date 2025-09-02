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
    AGOLWebMapCombinedExtent,
    AGOLWebMapSpatialExtent,
)
import shutil
from PIL import ImageColor
import geojson
from geojson import FeatureCollection
import json
from dataclasses import asdict
import logging
import tempfile
from dacite import from_dict
import os
import pandas as pd
from arcgis.map import Map
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
    my_arc_gis_helper = ArcGISHelper(agol_token=agol_token)
    my_arc_gis_helper.create_folder(
        project_title=agol_submission_payload.gdh_project_details.project_title
    )
    agol_export_status = AGOLExportStatus(status=0, messages=[""], success_url="")

    submission_status_details = my_arc_gis_helper.export_design_json_to_agol(
        design_data=agol_submission_payload.design_data,
        gdh_systems_information=agol_submission_payload.gdh_systems_information,
    )

    if submission_status_details.status == 0:
        agol_export_status.status = 0
        agol_export_status.messages.append("A design with the same ID already exists in your profile in ArcGIS Online, you must delete that first in ArcGIS Online and try the migration again.")
    else:
        agol_export_status.status = 1
        agol_export_status.success_url = submission_status_details.url
        agol_export_status.messages.append(
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
        if agol_submission_payload.include_webmap:
            logger.info("Webmap included in the export")
            my_webmap_item = my_arc_gis_helper.publish_feature_layer_as_webmap(
                feature_layer_item=submission_status_details.item,
                design_data=agol_submission_payload.design_data,
                gdh_systems_information=agol_submission_payload.gdh_systems_information,
            )
        if agol_submission_payload.include_storymap:
            logger.info("Storymap included in the export")
            my_storymap_publisher = StoryMapPublisher(
                design_data=agol_submission_payload.design_data,
                gdh_systems_information=agol_submission_payload.gdh_systems_information,
                negotiated_design_item_id=my_webmap_item.itemid,
                gdh_project_details=agol_submission_payload.gdh_project_details,
                gis=my_arc_gis_helper.get_gis(),
            )
            my_storymap_publisher.publish_storymap()

    r.set(submission_processing_result_key, json.dumps(asdict(agol_export_status)))
    r.expire(submission_processing_result_key, time=6000)


class ArcGISHelper:
    """
    ArcGISHelper is a utility class designed to interact with ArcGIS Online (AGOL) services.
    It provides methods for managing GIS objects, creating folders, checking for existing items,
    exporting data, and publishing feature layers and web maps.
    Attributes:
        agol_token (str): The authentication token for accessing AGOL.
        gis (GIS): The GIS object created using the provided AGOL token.
    Methods:
        __init__(agol_token: str):
            Initializes the ArcGISHelper instance with the provided AGOL token.
        get_gis() -> GIS:
            Returns the GIS object associated with the helper.
        get_ok_for_migration_items():
            Retrieves all items tagged for migration from AGOL.
        create_gis_object() -> GIS:
            Creates and returns a GIS object using the AGOL token.
        create_folder(project_title: str):
            Creates a folder in AGOL for the user based on the project title.
        check_if_tags_exist(project_id: str, gis: GIS) -> bool:
            Checks if tags for a specific project already exist in AGOL.
        check_if_design_exists(project_id: str, design_id: str, gis: GIS) -> bool:
            Checks if a design for a specific project already exists in AGOL.
        export_project_tags_to_agol(tags_data: GeodesignhubProjectTags, project_id: str) -> Union[int, Item]:
            Exports project tags as a CSV file to AGOL.
        create_uv_infos(gdh_project_systems: AllSystemDetails, geometry_type: str):
            Creates unique value information for AGOL based on project systems.
        create_symbol(geometry_type, symbol_color, opacity=0.65):
            Creates a symbol for AGOL based on geometry type and color.
        create_uv_renderer(geometry_type: str, unique_field_name: str, gdh_project_systems: AllSystemDetails):
            Creates a renderer for AGOL based on unique field and system details.
        publish_feature_layer_as_webmap(feature_layer_item: Item, design_data: ArcGISDesignPayload, gdh_systems_information: AllSystemDetails) -> Item:
            Publishes a feature layer as a web map in AGOL.
        remove_code_prefix_from_tag_codes(feature_layer):
            Removes the 'CODE:' prefix from the 'tag_codes' field in all features of a given feature layer.
        export_design_json_to_agol(design_data: ArcGISDesignPayload, gdh_systems_information: AllSystemDetails) -> AGOLFeatureLayerPublishingResponse:
            Exports design data as a GeoJSON file to AGOL and publishes it as a feature layer.
    """

    def __init__(self, agol_token: str):
        self.agol_token = agol_token
        self.gis = self.create_gis_object()
        self.folder = None

    def get_gis(self) -> GIS:
        return self.gis

    def get_layers_for_feature_service(self, item_id: str) -> list:
        """Get all layers for a feature service"""
        item = self.gis.content.get(item_id)
        if item is None:
            raise ValueError(f"Item with ID {item_id} not found.")
        if item.type != "Feature Service":
            raise ValueError(f"Item with ID {item_id} is not a Feature Service.")
        return item.layers

    def get_ok_for_migration_items(self, data_format: str):
        """Get all items that are ok for migration from AGOL"""
        owner = self.gis.users.me.username
        # Define a lookup for data_format
        data_format_lookup = {
            "geojson": "GeoJSON",
            "geopackage": "GeoPackage",
            "feature-service": "Feature Service",
        }

        # Validate and get the format from the lookup
        if data_format not in data_format_lookup:
            raise ValueError(f"Unsupported data format: {data_format}")
        format_type = data_format_lookup[data_format]
        logger.info(f"Data format selected: {format_type}")

        search_results = self.gis.content.search(
            query=f'tags:"migrate_to_geodesignhub" owner:{owner}',
            item_type=f"{format_type}",
        )

        if search_results:
            logger.info(f"Found {len(search_results)} items for migration")

        return search_results

    def clear_downloaded_tmp_file_directory(
        self, temp_dir: tempfile.TemporaryDirectory
    ):
        """
        Clears the contents of the specified temporary directory by deleting it.
        Args:
            temp_dir (tempfile.TemporaryDirectory): The temporary directory to be cleared.
        Notes:
            This function uses `shutil.rmtree` to remove the directory and its contents.
            The `ignore_errors=True` parameter ensures that no exception is raised if the
            directory does not exist or cannot be deleted.
        """

        shutil.rmtree(temp_dir.name, ignore_errors=True)

    def download_geojson_item_to_tmp_file(self, save_path: str, item: Item) -> bool:
        """Download the item to a temporary file"""
        print("Downloading to: %s" % save_path)
        item.download(save_path=save_path)

        logger.info(f"Item downloaded to {save_path}")
        return True

    def create_gis_object(self) -> GIS:
        gis = GIS("https://www.arcgis.com/", token=self.agol_token)
        return gis

    def create_folder(self, project_title: str):
        """Create a folder for the user in ArcGIS Online"""
        cm = self.gis.content
        folders_obj = cm.folders
        folder_name = "Data from Geodesignhub for " + project_title
        item_folder = folders_obj.get(folder=folder_name)
        if not item_folder:
            me = self.gis.users.me
            item_folder = folders_obj.create(folder_name, owner=me)
        self.folder = item_folder

    def check_if_tags_exist(self, project_id: str, gis: GIS) -> bool:
        object_already_exists = False
        search_results = gis.content.search(
            query=f"snippet:{project_id}-tags", item_type="CSV", max_items=1
        )
        if search_results:
            object_already_exists = True

        return object_already_exists

    def check_if_design_exists(self, project_id: str, design_id: str, gis: GIS) -> bool:
        object_already_exists = False
        search_results = gis.content.search(
            query=f"snippet:{design_id}-{project_id}", item_type="GeoJson"
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
            title=f"Geodesignhub Project tags for project ID {project_id}",
            snippet=project_id + "-tags",
            description="All project tags as a CSV",
            type="CSV",
        )

        tags_exist_in_profile = self.check_if_tags_exist(
            gis=self.gis, project_id=project_id
        )
        if tags_exist_in_profile:
            logger.info(
                "Tags for this project already exists in profile, they cannot be re-uploaded"
            )
            return 0

        else:
            temp_csv_file = tempfile.NamedTemporaryFile(mode="w", delete=False)
            tags_df.to_csv(temp_csv_file.name, encoding="utf-8", index=False)
            logger.info("Uploading tags to AGOL...")
            csv_item = self.folder.add(
                item_properties=asdict(agol_item_details), file=temp_csv_file.name
            ).result()

            if csv_item:
                published_item = csv_item.publish()
            else:
                logger.info("Failed to upload tags to AGOL.")
                logger.info(csv_item)
            logger.info("Tags uploaded successfully...")
            os.unlink(temp_csv_file.name)
            temp_csv_file.delete = True

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
            "color": (r, g, b, int(alpha)),
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
        my_map = Map()

        # Initialize extent variable to store combined extent
        combined_extent = None

        for new_published_layer in new_published_layers:
            logger.info(
                f"{new_published_layer.properties.name} - {new_published_layer.properties.geometryType}"
            )

            logger.info("Getting the layer manager...")
            # the layer manager
            # my_layer_manager = new_published_layer.manager
            # update layer renderer
            logger.info("Update layer renderer...")
            renderer = self.create_uv_renderer(
                geometry_type=new_published_layer.properties.geometryType,
                unique_field_name="system_name",
                gdh_project_systems=gdh_systems_information,
            )
            # set the renderer on the layer item
            # new_published_layer.renderer = renderer
            # set the renderer on the layer service
            # my_layer_manager.update_definition({"drawingInfo": {"renderer": renderer}})

            # Get fields from the feature layer
            fields = new_published_layer.properties.fields
            field_infos = []

            # Build fieldInfos dynamically for popup
            for field in fields:
                if field.type != "esriFieldTypeOID" and not field.name.endswith("_ID"):
                    field_infos.append(
                        {
                            "fieldName": field.name,
                            "label": field.alias,
                            "isEditable": False,
                            "visible": True,
                        }
                    )

            # Construct the popupInfo based on the fields
            popup_info_dict = {
                "title": "{diagram_name}",  # Use a main field for title
                "popupElements": [{"type": "fields", "fieldInfos": field_infos}],
            }

            my_map.content.add(
                new_published_layer,
                drawing_info={"renderer": renderer},
                popup_info=popup_info_dict,
            )

            # Combine extents for the webmap
            layer_extent = new_published_layer.properties.extent
            if layer_extent:
                # Check if any coordinate value is missing or empty
                if any(
                    layer_extent.get(key) in [None, ""]
                    for key in ["xmin", "ymin", "xmax", "ymax"]
                ):
                    # Skip this layer and continue with the next one
                    continue

                if not combined_extent:
                    combined_extent = from_dict(
                        data=dict(layer_extent), data_class=AGOLWebMapCombinedExtent
                    )
                else:
                    # Expand the combined extent to include this layer's extent
                    combined_extent = AGOLWebMapCombinedExtent(
                        xmin=min(combined_extent.xmin, layer_extent["xmin"]),
                        ymin=min(combined_extent.ymin, layer_extent["ymin"]),
                        xmax=max(combined_extent.xmax, layer_extent["xmax"]),
                        ymax=max(combined_extent.ymax, layer_extent["ymax"]),
                        spatialReference=AGOLWebMapSpatialExtent(
                            wkid=layer_extent["spatialReference"]["wkid"],
                            latestWkid=layer_extent["spatialReference"]["latestWkid"],
                        ),
                    )

        # Set the webmap's extent
        if combined_extent:
            my_map.extent = asdict(
                combined_extent
            )  # AGOL expects a dictionary for extents

        web_map_title = "Webmap for {design_name}".format(
            design_name=_gdh_design_details.design_name
        )
        web_map_properties = {
            "title": web_map_title,
            "snippet": "This map shows design synthesis details from a negotiation in Geodesignhub",
            "tags": "Geodesignhub",
            "extent": my_map.extent,  # Set extent property for wm
        }

        # Call the save() with web map item's properties.
        web_map_item = my_map.save(item_properties=web_map_properties)
        return web_map_item

    def remove_code_prefix_from_tag_codes(self, feature_layer):
        """
        Removes the 'CODE:' prefix from the 'tag_codes' field
        in all features of the given feature layer.
        """
        query_res = feature_layer.query(where="1=1", out_fields="tag_codes")
        if not query_res.features:
            return

        updated_features = []
        for feat in query_res.features:
            old_val = feat.attributes.get("tag_codes")
            if old_val and old_val.startswith("CODE:"):
                feat.attributes["tag_codes"] = old_val.replace("CODE:", "", 1)
                updated_features.append(feat)

        if updated_features:
            result = feature_layer.edit_features(updates=updated_features)
            logger.info(
                f"Removed CODE: prefix from {len(updated_features)} features. Edit result: {result}"
            )
        else:
            logger.info("No 'CODE:' prefix found to remove.")

    def export_design_json_to_agol(
        self,
        design_data: ArcGISDesignPayload,
        gdh_systems_information: AllSystemDetails,
    ) -> AGOLFeatureLayerPublishingResponse:
        _gdh_design_details = design_data.gdh_design_details
        _gdh_project_systems = gdh_systems_information
        design_id = _gdh_design_details.design_id
        project_id = _gdh_design_details.design_id
        agol_snippet = design_id + "-" + project_id

        design_exists_in_profile = self.check_if_design_exists(
            gis=self.gis, design_id=design_id, project_id=project_id
        )

        if design_exists_in_profile:
            logger.info("Design already exists in profile, it cannot be re-uploaded")
            return AGOLFeatureLayerPublishingResponse(
                status=0,
                item=None,
                url="",
                message="Design already exists in profile, it cannot be re-uploaded",
            )

        # Extract the FeatureCollection
        _gdh_design_feature_collection: FeatureCollection = (
            _gdh_design_details.design_geojson.geojson
        )

        for feature in _gdh_design_feature_collection["features"]:
            props = feature["properties"]
            if "tag_codes" in props:
                original_val = str(props["tag_codes"])
                props["tag_codes"] = f"CODE:{original_val}"

        # Fallback to a safe design name if it's empty or null
        safe_design_name = (
            _gdh_design_details.design_name.strip()
            if _gdh_design_details.design_name
            else "UntitledDesign"
        )
        if not safe_design_name:
            safe_design_name = "UntitledDesign"

        # Prepare item details
        agol_item_details = AGOLItemDetails(
            title=f"{safe_design_name}-geojson",
            snippet=agol_snippet,
            description=design_id,
            type="GeoJson",
        )

        # Write GeoJSON to temp file
        with tempfile.NamedTemporaryFile(mode="w", delete=False) as output:
            output.write(geojson.dumps(_gdh_design_feature_collection))
            temp_geojson_path = output.name

        # Add the item
        geojson_item = self.folder.add(
            item_properties=asdict(agol_item_details), file=temp_geojson_path
        ).result()
        
        if geojson_item:
            feature_layer_published = False
            try:
                feature_layer_item = geojson_item.publish()
            except Exception as e:
                logger.info(f"Error publishing the GeoJSON item to AGOL: {e}")

            else:
                feature_layer_published = True
                feature_layer_item_url = feature_layer_item.url
            finally:
                # Clean up temp file
                os.unlink(temp_geojson_path)
                output.delete = True

            if feature_layer_published:
                logger.info("Layer is published as Feature Collection")
                logger.info("Getting the published feature layer...")
                new_published_layers = feature_layer_item.layers

            else:
                return AGOLFeatureLayerPublishingResponse(
                    status=0,
                    item=None,
                    url="",
                    message="Error publishing the GeoJSON item to ArcGIS online",
                )

            for new_published_layer in new_published_layers:
                logger.info(
                    f"{new_published_layer.properties.name} - {new_published_layer.properties.geometryType}"
                )

                # The layer manager
                test_layer_manager = new_published_layer.manager

                # Update layer renderer
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
                self.remove_code_prefix_from_tag_codes(new_published_layer)

            return AGOLFeatureLayerPublishingResponse(
                status=1,
                item=feature_layer_item,
                url=feature_layer_item_url,
                message="Layer is published as Feature Collection",
            )

        return AGOLFeatureLayerPublishingResponse(
            status=0,
            item=None,
            url="",
            message="Error publishing the Design JSON to ArcGIS online",
        )
