import arcgis
from arcgis.gis import GIS, Item
from arcgis.apps.storymap.story import StoryMap
from arcgis.apps.storymap.story_content import (
    Image,
    TextStyles,
    Video,
    Audio,
    Embed,
    Map,
    Text,
    Button,
    Gallery,
    Swipe,
    Sidecar,
    Timeline,
)

import os
import yaml
from data_definitions import ArcGISDesignPayload, AllSystemDetails
import logging
from pathlib import Path

logger = logging.getLogger("esri-gdh-bridge")
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())
ENV_FILE = find_dotenv()


class StoryMapPublisher:
    def __init__(
        self,
        design_data: ArcGISDesignPayload,
        gdh_systems_information: AllSystemDetails,
        negotiated_design_item_id: str,
        gis: GIS,
    ):
        """Initialize the story map publisher with information to publish the map"""
        self._gdh_design_details = design_data
        self._gis = gis
        self._negotiated_design_item_id = negotiated_design_item_id
        _storymap_template_filename = "gdh_default_storymap_template.yaml"
        _BASE_DIR = Path.cwd()
        _storymap_template_filepath = os.path.join(
            _BASE_DIR, "storymap_templates", _storymap_template_filename
        )
        if not os.path.isfile(_storymap_template_filepath):
            logger.error(
                "Invalid filepath provided %s is incorrect, please provide one that exists in the system"
                % _storymap_template_filename
            )
        with open(_storymap_template_filepath, "r") as _storymap_template_file:
            self._storymap_template = yaml.safe_load(_storymap_template_file)

        self._storymap = self.create_new_storymap()

    def _populate_storymap_cover(self):
        my_cover_image = Image(
            path="https://story.maps.arcgis.com/sharing/rest/content/items/2fcc801c983a402eb427dd5cd07ee759/data"
        )
        self._storymap.cover(
            type="full",
            title="Storymap for {design_name}".format(
                design_name=self._gdh_design_details.gdh_design_details.design_name
            ),
            summary="A story map for Geodesignhub negotiation with project id {project_id}".format(
                project_id=self._gdh_design_details.gdh_design_details.project_id
            ),
            by_line="Geodesignhub",
            image=my_cover_image,
        )

    def create_new_storymap(self) -> StoryMap:
        """Create a blank storymap and return the instance"""
        my_geodesignhub_project_story = StoryMap()
        return my_geodesignhub_project_story

    def add_project_text_gallery_to_storymap(self):
        """Add some basic details about Geodesignhub project"""
        mission_heading_text = Text(
            text="Our Mission Statement", style=TextStyles.HEADING
        )
        mission_paragraph = Text(
            text="Our mission description with more information about our goals"
        )
        new_gallery = Gallery(caption="Some important places")
        self._storymap.add(new_gallery)
        self._storymap.add(mission_heading_text)
        self._storymap.add(mission_paragraph)

    def add_geodesignhub_final_design(self):
        """Add the uploaded design from Geodesignhub into the Storymap"""
        new_map = Map(Item(gis=self._gis, itemid=self._negotiated_design_item_id))
        self._storymap.add(new_map)

    def publish_storymap(self):
        logger.info("Populating the storymap cover...")
        self._populate_storymap_cover()
        logger.info("Adding text and gallery to storymap...")
        self.add_project_text_gallery_to_storymap()
        logger.info("Referencing uploaded design to storymap...")
        self.add_geodesignhub_final_design()
        logger.info("Publishing stormay...")
        self._storymap.save(publish=True)
