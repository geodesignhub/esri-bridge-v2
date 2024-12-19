from arcgis.gis import GIS, Item
from arcgis.apps.storymap.story import StoryMap
from arcgis.apps.storymap.story_content import (
    Image,
    TextStyles,
    Map,
    Table,
    Text,
    TextStyles,
    Separator,
    Gallery,
)

import os
import yaml
import pandas as pd
import tempfile
from PIL import Image as PILImage
import requests
from data_definitions import ArcGISDesignPayload, AllSystemDetails, GeodesignhubProjectDetails
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
        gdh_project_details:GeodesignhubProjectDetails,
        gis: GIS,
    ):
        """Initialize the story map publisher with information to publish the map"""
        self._gdh_design_details = design_data
        self._gis = gis
        self._negotiated_design_item_id = negotiated_design_item_id
        self._gdh_project_details  = gdh_project_details

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
        # Dynamic values to be substituted
        dynamic_values = {
            "design_name": self._gdh_design_details.gdh_design_details.design_name,
            "project_id": self._gdh_design_details.gdh_design_details.project_id,
            "negotiated_design_item_id": self._negotiated_design_item_id,
            "gdh_project_name":self._gdh_project_details.project_title,
            "verbose_project_description":self._gdh_project_details.project_description
        }

        # Extract placeholders from the template (as a dictionary)
        placeholders = self._storymap_template.get("placeholders", {})

        if not isinstance(placeholders, dict):
            raise ValueError(
                "Expected 'placeholders' to be a dictionary in the YAML template."
            )

        # Iterate over placeholders and perform replacements
        yaml_str = yaml.dump(self._storymap_template)
        for key, default_value in placeholders.items():
            replacement_value = default_value.format(**dynamic_values)
            yaml_str = yaml_str.replace(f"{{{key}}}", replacement_value)

        # Reload the updated YAML string into the template
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

        # Iterate over the sections
        sections = self._storymap_template.get("sections", [])
        for section in sections:
            section_title = section.get("title", "Untitled Section")
            panels = section.get("panels", [])

            # Add a heading for the section
            self._add_text(
                {"content_type": "text", "style": "heading", "text": section_title}
            )

            # Add the panels within the section
            for panel in panels:
                content_type = panel.get("content_type")
                if content_type == "text":
                    self._add_text(panel)
                elif content_type == "map":
                    self._add_map(panel)
                elif content_type == "image":
                    self._add_image(panel)
                elif content_type == "gallery":
                    self._add_gallery(panel)
                elif content_type == "separator":
                    self._add_separator()
                elif content_type == "table":
                    self._add_table(panel)
                else:
                    logger.warning(f"Unsupported panel content_type: {content_type}")

    def _set_cover(self):
        """Set the cover of the StoryMap."""
        if self._storymap is None:
            return  # Exit if StoryMap is not initialized

        # Construct the cover directly using available template data and format strings
        cover = self._storymap_template.get("cover", {})
        title = cover.get("title", "Project Title")
        summary = cover.get("subtitle", "Project Description")
        cover_image_url = cover.get(
            "cover_image_url",
            "https://igcollab-com.maps.arcgis.com/sharing/rest/content/items/7d973317b8434f298e4c543f37e0b0c8/data",
        )

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
                new_map = Map(item=map_item)

                # Clear conflicting properties
                new_map._zoom = None  # Ensure zoom doesn't override extent
                new_map._viewpoint = None  # Clear any predefined viewpoint

                # Add the map to the StoryMap
                self._storymap.add(new_map)
                new_map.caption = caption

            except Exception as e:
                logger.error(f"Failed to add map: {e}")
        else:
            logger.warning("Map item ID is missing.")

    def _add_image(self, panel):
        """Add a single image element to the StoryMap."""
        logger.info("Adding a single image...")

        image_url = panel.get("url")
        caption = panel.get("caption", "")

        if not image_url:
            logger.error("No URL provided for the image.")
            return

        processed_image_path = None
        try:
            # Process the image (download/convert if needed)
            processed_image_path = self._process_image(image_url)
            if not processed_image_path:
                raise ValueError(f"Failed to process image: {image_url}")

            # Add the image to the StoryMap
            image = Image(path=processed_image_path)
            self._storymap.add(image)
            image.caption = caption
            logger.info(
                f"Image added successfully: {image_url} with caption: '{caption}'"
            )
        except Exception as e:
            logger.error(f"Failed to add image: {image_url} - {e}")
        finally:
            # Clean up the converted image file
            if processed_image_path and processed_image_path.startswith(
                tempfile.gettempdir()
            ):
                os.remove(processed_image_path)

    def _add_text(self, panel):
        """Add a text element to the StoryMap."""
        logger.info("Adding the text...")
        text_content = panel.get("text", "")
        style = panel.get("style", "paragraph").upper()
        if style not in TextStyles.__members__:
            logger.warning(f"Invalid text style: {style}, defaulting to PARAGRAPH")
            style = "PARAGRAPH"

        # Add the text directly, whether single-line or multiline
        text = Text(text=text_content.strip(), style=TextStyles[style])
        self._storymap.add(text)

    def _add_gallery(self, panel):
        """Add a gallery element to the StoryMap."""
        logger.info("Adding a gallery...")

        images_info = panel.get("images", [])
        if not images_info:
            logger.error("No images provided for the gallery.")
            return

        # Initialize an empty Gallery object
        try:
            gallery = Gallery()
            self._storymap.add(gallery)
        except Exception as e:
            logger.error(f"Failed to initialize Gallery: {e}")
            return

        processed_image_paths = []
        try:
            for image_info in images_info:
                image_url = image_info.get("url")
                caption = image_info.get("caption", "")

                if not image_url:
                    logger.warning("Skipping image with no URL.")
                    continue

                try:
                    # Process the image (download/convert if needed)
                    processed_image_path = self._process_image(image_url)
                    if not processed_image_path:
                        raise ValueError(f"Failed to process image: {image_url}")

                    # Add the image to the gallery
                    image = Image(path=processed_image_path)
                    gallery.add_images([image])
                    image.caption = caption
                    processed_image_paths.append(processed_image_path)
                    logger.info(
                        f"Image added to gallery: {image_url} with caption: '{caption}'"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to add image to gallery - URL: {image_url} - {e}"
                    )

            # Set the gallery's caption
            gallery_caption = panel.get("caption", "Gallery Caption")
            gallery.caption = gallery_caption
            logger.info(f"Gallery caption set: '{gallery_caption}'")
        finally:
            # Clean up all processed image files
            for path in processed_image_paths:
                if path and path.startswith(tempfile.gettempdir()):
                    os.remove(path)

    def _add_separator(self):
        logger.info("Adding the separator...")
        """Add a separator element to the StoryMap."""
        separator = Separator()
        self._storymap.add(separator)

    def _add_table(self, panel):
        """Add a table element to the StoryMap."""
        logger.info("Adding a table...")

        # Retrieve headers and rows from the panel
        headers = panel.get("headers", [])
        rows = panel.get("rows", [])

        if not headers or not rows:
            logger.warning("Table headers or rows are missing. Skipping this panel.")
            return

        try:
            # Validate the number of rows and columns
            num_data_rows = len(rows)  # Number of data rows
            num_columns = len(headers)

            if num_data_rows > 9 or num_data_rows < 1:
                logger.warning(
                    f"Invalid number of rows ({num_data_rows}). Must be between 1 and 9. Skipping."
                )
                return

            if num_columns > 8 or num_columns < 1:
                logger.warning(
                    f"Invalid number of columns ({num_columns}). Must be between 1 and 8. Skipping."
                )
                return

            # Create the Table instance
            table = Table(rows=num_data_rows + 1, columns=num_columns)
            self._storymap.add(table)

            # Construct the DataFrame
            structured_data = []

            # Add the header row
            structured_data.append([{"value": header} for header in headers])

            # Add the data rows
            for row in rows:
                structured_data.append([{"value": str(cell)} for cell in row])

            # Convert structured_data into a DataFrame
            df = pd.DataFrame(structured_data)

            # Assign the DataFrame to the table's content
            table.content = df

            logger.info(
                f"Table added successfully with headers: {headers} and {len(rows)} data rows."
            )
        except Exception as e:
            logger.error(f"Failed to add table to StoryMap: {e}")

    def _process_image(self, image_url):
        """Download and convert an image to JPEG if necessary."""
        temp_file_path = None
        converted_path = None

        try:
            # Download the image
            response = requests.get(
                image_url,
                stream=True,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            response.raise_for_status()

            # Save to a temporary file
            temp_file_path = tempfile.NamedTemporaryFile(delete=False).name
            with open(temp_file_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)

            # Convert to JPEG
            converted_path = f"{temp_file_path}.jpeg"
            with PILImage.open(temp_file_path) as img:
                img.convert("RGB").save(converted_path, "JPEG")

            return converted_path  # Return the path to the converted file
        except Exception as e:
            logger.error(f"Failed to process image: {image_url} - {e}")
            return None
        finally:
            # Clean up only the downloaded file (not the converted JPEG)
            if temp_file_path and os.path.exists(temp_file_path):
                os.remove(temp_file_path)

    def publish_storymap(self):
        logger.info("Populating the StoryMap from template...")
        self.populate_storymap_from_template()
        logger.info("Publishing StoryMap...")
        # Save the StoryMap (without item_properties)
        self._storymap.save(publish=True)

        # Retrieve title and description from the template or set defaults
        storymap_title = self._storymap_template.get(
            "name", "Geodesignhub ESRI Bridge Alpha"
        )
        storymap_description = self._storymap_template.get(
            "description", "A story map for the Geodesignhub project"
        )

        # Update the title and description after saving
        if self._storymap._item:  # Ensure _item is initialized
            logger.info("Updating StoryMap item properties (title and description)...")
            self._storymap._item.update(
                {"title": storymap_title, "snippet": storymap_description}
            )
            logger.info("StoryMap item properties updated successfully.")
        else:
            logger.error(
                "Failed to update title and description: StoryMap item not initialized."
            )
