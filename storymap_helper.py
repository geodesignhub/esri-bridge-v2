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
    TextStyles,
    Separator,
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
from dotenv import load_dotenv, find_dotenv


logger = logging.getLogger("esri-gdh-bridge")

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

        # Load the YAML template
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

        # Replace placeholders in the template
        self._replace_placeholders()

        # Create the StoryMap object with the title
        self._storymap = self.create_new_storymap()

    def _replace_placeholders(self):
        """Replace placeholders in the YAML template with actual values."""
 
        placeholders = {
            "{project_title}": "Storymap for {design_name}".format(
                design_name=self._gdh_design_details.gdh_design_details.design_name
            ),
            "{project_description}": "A story map for Geodesignhub negotiation with project id {project_id}".format(
                project_id=self._gdh_design_details.gdh_design_details.project_id
            ),
            "{negotiated_design_item_id}": self._negotiated_design_item_id,
        }

        yaml_str = yaml.dump(self._storymap_template)
        for placeholder, value in placeholders.items():
            yaml_str = yaml_str.replace(placeholder, value)
        self._storymap_template = yaml.safe_load(yaml_str)

    def create_new_storymap(self) -> StoryMap:
        """Create a blank StoryMap with the given title and return the instance."""
        # Use the title from the template or fallback to a default

        my_geodesignhub_project_story = StoryMap()
        return my_geodesignhub_project_story
    
    def populate_storymap_from_template(self):
        """Populate the StoryMap using the YAML template."""
        # Set the cover
        self._set_cover()

        # Iterate over the panels and add content accordingly
        panels = self._storymap_template.get("panels", [])
        for panel in panels:
            panel_type = panel.get("type")
            if panel_type == "text":
                self._add_text(panel)
            elif panel_type == "map":
                self._add_map(panel)
            elif panel_type == "image":
                self._add_image(panel)
            elif panel_type == "gallery":
                self._add_gallery(panel)
            elif panel_type == "separator":
                self._add_separator()
            else:
                logger.warning(f"Unsupported panel type: {panel_type}")

    def _set_cover(self):
        """Set the cover of the StoryMap."""
        if self._storymap is None:
            return  # Exit if StoryMap is not initialized

        # Construct the cover directly using available template data and format strings
        cover = self._storymap_template.get("cover", {})
        title = cover.get("title", "Project Title")
        summary = cover.get("subtitle", "Project Description")
        cover_image_url = cover.get("cover_image_url", "https://story.maps.arcgis.com/sharing/rest/content/items/2fcc801c983a402eb427dd5cd07ee759/data")

        # Use the `cover()` method on `self._storymap` to set these properties directly
        self._storymap.cover(
            type="full",
            title=title,
            summary=summary,
            by_line="Geodesignhub",  # Replace with actual byline if available in the template
            image=cover_image_url,
        )


    def _add_map(self, panel):
        logger.info("Adding the map...")
        """Add a map element to the StoryMap."""
        item_id = panel.get("item_id")
        caption = panel.get("caption", "")
        if item_id:
            try:
                map_item = Item(gis=self._gis, itemid=item_id)
                new_map = Map(item=map_item, caption=caption)
                self._storymap.add(new_map)
            except Exception as e:
                logger.error(f"Failed to add map: {e}")
        else:
            logger.warning("Map item ID is missing.")

    def _add_text(self, panel):
        """Add a text element to the StoryMap."""
        logger.info("Adding the text...")
        text_content = panel.get("text", "")
        style = panel.get("style", "paragraph").upper()
        if style not in TextStyles.__members__:
            logger.warning(f"Invalid text style: {style}, defaulting to PARAGRAPH")
            style = "PARAGRAPH"
       # Split text by line breaks and add a bullet to each line if multiple lines are detected
        text_lines = text_content.split("\n")
        if len(text_lines) > 1:
            for line in text_lines:
                bullet_text = f"• {line.strip()}"  # Add a bullet and strip extra whitespace
                text = Text(text=bullet_text, style=TextStyles[style])
                self._storymap.add(text)
        else:
            # For single-line content, add it directly without bullets
            text = Text(text=text_content, style=TextStyles[style])
            self._storymap.add(text)
            
    # Adding a gallery element to the StoryMap using valid item references
    def _add_gallery(self, panel):
        """Add a gallery element to the StoryMap."""

        images_info = panel.get("images", [])
        images = []

        # Loop through each image entry in the YAML data
        for image_info in images_info:
            image_url = image_info.get("url")
            caption = image_info.get("caption", "")

            if not image_url:
                continue

            try:
                # Create an Image instance directly with the provided URL and caption
                image = Image(path=image_url, caption=caption)
                images.append(image)
            except Exception as e:
                logger.error(f"Failed to create Image object for URL: {image_url} - {e}")

        # Proceed only if there are valid images
        if images:
            gallery_caption = panel.get("caption", "Gallery Caption")
            try:
                # Create a Gallery object without images initially and add it to the StoryMap
                gallery = Gallery()
                self._storymap.add(gallery)
                gallery.caption = gallery_caption

                # Add images to the gallery after it's part of the StoryMap
                gallery.add_images(images)
            except Exception as e:
                logger.error(f"Failed to add gallery to StoryMap - {e}")
        else:
            logger.error("No valid images to add to gallery.")
            

    def _add_separator(self):
        logger.info("Adding the separator...")
        """Add a separator element to the StoryMap."""
        separator = Separator()
        self._storymap.add(separator)

    def publish_storymap(self):
        logger.info("Populating the StoryMap from template...")
        self.populate_storymap_from_template()
        logger.info("Publishing StoryMap...")
        # Save the StoryMap (without item_properties)
        self._storymap.save(publish=True)

        # Retrieve title and description from the template or set defaults
        storymap_title = self._storymap_template.get("name", "Geodesignhub StoryMap")
        storymap_description = self._storymap_template.get("description", "A story map for the Geodesignhub project")

        # Update the title and description after saving
        if self._storymap._item:  # Ensure _item is initialized
            logger.info("Updating StoryMap item properties (title and description)...")
            self._storymap._item.update({
            "title": storymap_title,
            "snippet": storymap_description
            })
            logger.info("StoryMap item properties updated successfully.")
        else:
            logger.error("Failed to update title and description: StoryMap item not initialized.")
