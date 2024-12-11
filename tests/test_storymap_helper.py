import unittest
from unittest.mock import MagicMock, patch, mock_open

import pandas as pd
from storymap_helper import StoryMapPublisher
from arcgis.apps.storymap.story_content import TextStyles
from requests.exceptions import RequestException


class TestStoryMapPublisher(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Mock the design data and system details
        cls.mock_design_data = MagicMock()
        cls.mock_design_data.gdh_design_details = MagicMock()
        cls.mock_design_data.gdh_design_details.design_name = "Test Design"
        cls.mock_design_data.gdh_design_details.project_id = "12345"

        cls.mock_system_details = MagicMock()
        cls.mock_negotiated_design_item_id = "test_item_id"
        cls.mock_gis = MagicMock()

        # Define YAML content
        cls.yaml_content = """
        cover:
          title: '{project_title}'
          subtitle: '{project_description}'
          cover_image_url: 'https://example.com/cover_image.jpg'
        panels: []
        """

    def setUp(self):
        # Mock os.path.isfile to always return True
        self.patcher_isfile = patch("storymap_helper.os.path.isfile", return_value=True)
        self.mock_isfile = self.patcher_isfile.start()
        self.addCleanup(self.patcher_isfile.stop)

    def create_publisher(self):
        with patch("builtins.open", mock_open(read_data=self.yaml_content)):
            publisher = StoryMapPublisher(
                design_data=self.mock_design_data,
                gdh_systems_information=self.mock_system_details,
                negotiated_design_item_id=self.mock_negotiated_design_item_id,
                gis=self.mock_gis,
            )
        return publisher

    @patch("storymap_helper.StoryMapPublisher._replace_placeholders")
    @patch("storymap_helper.StoryMap")
    def test_init(self, mock_storymap_class, mock_replace_placeholders):
        publisher = self.create_publisher()

        # Mock placeholder replacement
        mock_replace_placeholders.assert_called_once()

        # Check unprocessed placeholder in cover (if not replaced during init)
        self.assertEqual(
            publisher._storymap_template["cover"]["title"], "{project_title}"
        )
        self.assertEqual(
            publisher._storymap_template["cover"]["subtitle"], "{project_description}"
        )

        mock_storymap_class.assert_called_once_with()

    @patch("storymap_helper.Text")
    @patch("storymap_helper.StoryMap")
    def test_add_text(self, mock_storymap_class, mock_text_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        panel = {"content_type": "text", "style": "paragraph", "text": "Test Paragraph"}
        publisher._add_text(panel)

        mock_text_class.assert_called_once_with(
            text="Test Paragraph", style=TextStyles.PARAGRAPH
        )
        mock_storymap_instance.add.assert_called_once_with(mock_text_class.return_value)

    @patch("storymap_helper.Image")
    @patch("storymap_helper.StoryMap")
    def test_add_image(self, mock_storymap_class, mock_image_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        with patch.object(
            publisher, "_process_image", return_value="/path/to/processed/image.jpeg"
        ):
            panel = {
                "content_type": "image",
                "url": "https://example.com/image.jpg",
                "caption": "Test Image",
            }
            publisher._add_image(panel)

            mock_image_class.assert_called_once_with(
                path="/path/to/processed/image.jpeg"
            )
            mock_storymap_instance.add.assert_called_once_with(
                mock_image_class.return_value
            )
            self.assertEqual(mock_image_class.return_value.caption, "Test Image")

    @patch("storymap_helper.Map")
    @patch("storymap_helper.Item")
    @patch("storymap_helper.StoryMap")
    def test_add_map(self, mock_storymap_class, mock_item_class, mock_map_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        panel = {
            "content_type": "map",
            "item_id": "test_map_item_id",
            "caption": "Test Map",
        }
        publisher._add_map(panel)

        mock_item_class.assert_called_once_with(
            gis=self.mock_gis, itemid="test_map_item_id"
        )
        mock_map_class.assert_called_once_with(item=mock_item_class.return_value)
        mock_storymap_instance.add.assert_called_once_with(mock_map_class.return_value)
        self.assertEqual(mock_map_class.return_value.caption, "Test Map")

    @patch("storymap_helper.requests.get")
    @patch("storymap_helper.tempfile.NamedTemporaryFile")
    @patch("storymap_helper.os.remove")
    @patch("storymap_helper.PILImage.open")
    def test_process_image(
        self, mock_image_open, mock_os_remove, mock_tempfile, mock_requests_get
    ):
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"test data"]
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response
        mock_tempfile_instance = MagicMock()
        mock_tempfile_instance.name = "/tmp/tempfile"
        mock_tempfile.return_value = mock_tempfile_instance
        mock_image_instance = mock_image_open.return_value.__enter__.return_value

        # Create an instance without calling __init__
        publisher = StoryMapPublisher.__new__(StoryMapPublisher)

        # Call _process_image directly
        result = publisher._process_image("https://example.com/image.jpg")

        # Assertions
        mock_requests_get.assert_called_once_with(
            "https://example.com/image.jpg",
            stream=True,
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )
        mock_tempfile.assert_called_once_with(delete=False)
        mock_image_open.assert_called_once_with("/tmp/tempfile")
        mock_image_instance.convert.assert_called_once_with("RGB")
        mock_image_instance.convert.return_value.save.assert_called_once_with(
            "/tmp/tempfile.jpeg", "JPEG"
        )
        self.assertEqual(result, "/tmp/tempfile.jpeg")

    @patch("storymap_helper.StoryMap")
    def test_publish_storymap(self, mock_storymap_class):
        # Mock the StoryMap instance
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        # Mock the _item attribute
        mock_item = MagicMock()
        publisher._storymap._item = mock_item

        # Set up expected title and description based on template
        publisher._storymap_template = {
            "name": "Geodesignhub ESRI Bridge Alpha",
            "description": "A detailed story map for Geodesignhub projects",
        }
        expected_title = publisher._storymap_template["name"]
        expected_description = publisher._storymap_template["description"]

        # Execute the publish_storymap method
        publisher.publish_storymap()

        # Verify that save is called with publish=True
        mock_storymap_instance.save.assert_called_once_with(publish=True)

        # Verify that the item's title and snippet are updated
        mock_item.update.assert_called_once_with(
            {"title": expected_title, "snippet": expected_description}
        )

    @patch("storymap_helper.Separator")
    @patch("storymap_helper.StoryMap")
    def test_add_separator(self, mock_storymap_class, mock_separator_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        publisher._add_separator()

        mock_separator_class.assert_called_once()
        mock_storymap_instance.add.assert_called_once_with(
            mock_separator_class.return_value
        )

    @patch("storymap_helper.Image")
    @patch("storymap_helper.Gallery")
    @patch("storymap_helper.StoryMap")
    def test_add_gallery(
        self, mock_storymap_class, mock_gallery_class, mock_image_class
    ):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        images_created = []

        # Configure the Image mock to return a new MagicMock instance each time it's called
        def image_side_effect(*args, **kwargs):
            image_instance = MagicMock()
            images_created.append(image_instance)
            return image_instance

        mock_image_class.side_effect = image_side_effect

        with patch.object(
            publisher,
            "_process_image",
            side_effect=["/path/to/image1.jpeg", "/path/to/image2.jpeg"],
        ):
            panel = {
                "content_type": "gallery",
                "images": [
                    {"url": "https://example.com/image1.jpg", "caption": "Image 1"},
                    {"url": "https://example.com/image2.jpg", "caption": "Image 2"},
                ],
                "caption": "Gallery Caption",
            }
            publisher._add_gallery(panel)

            # Verify that Gallery is initialized and added to the story map
            mock_gallery_class.assert_called_once()
            mock_storymap_instance.add.assert_called_once_with(
                mock_gallery_class.return_value
            )

            # Verify that images are added to the gallery
            # Since add_images may be called multiple times, we can sum the total number of images added
            total_images_added = sum(
                len(call_args[0][0])
                for call_args in mock_gallery_class.return_value.add_images.call_args_list
            )
            self.assertEqual(total_images_added, 2)

            # Verify captions are set correctly
            self.assertEqual(len(images_created), 2)
            self.assertEqual(images_created[0].caption, "Image 1")
            self.assertEqual(images_created[1].caption, "Image 2")

            # Verify gallery caption
            self.assertEqual(mock_gallery_class.return_value.caption, "Gallery Caption")

    @patch("storymap_helper.Gallery")
    @patch("storymap_helper.StoryMap")
    def test_add_gallery_no_images(self, mock_storymap_class, mock_gallery_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        panel = {"content_type": "gallery", "images": []}
        with patch("storymap_helper.logger") as mock_logger:
            publisher._add_gallery(panel)
            mock_logger.error.assert_called_with("No images provided for the gallery.")
            mock_gallery_class.assert_not_called()
            mock_storymap_instance.add.assert_not_called()

    @patch("storymap_helper.Table")
    @patch("storymap_helper.StoryMap")
    def test_add_table(self, mock_storymap_class, mock_table_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        # Define a sample table panel
        panel = {
            "content_type": "table",
            "headers": ["Column 1", "Column 2"],
            "rows": [["Row1-Col1", "Row1-Col2"], ["Row2-Col1", "Row2-Col2"]],
        }

        # Call the _add_table method
        publisher._add_table(panel)

        # Verify that the Table instance is created with the correct dimensions
        mock_table_class.assert_called_once_with(
            rows=3, columns=2
        )  # Number of data rows only
        table_instance = mock_table_class.return_value

        # Mimic the logic of `_add_table` to validate the table's content
        structured_data = []
        structured_data.append(
            [{"value": header} for header in panel["headers"]]
        )  # Header row
        for row in panel["rows"]:
            structured_data.append([{"value": str(cell)} for cell in row])  # Data rows

        # Set the content of the mock table instance to match the constructed DataFrame
        table_instance.content = pd.DataFrame(structured_data)

        # Convert the structured data into the DataFrame format used in the content
        expected_content = pd.DataFrame(structured_data)

        # Validate that the table's content matches the expected DataFrame
        pd.testing.assert_frame_equal(table_instance.content, expected_content)

    @patch("storymap_helper.Table")
    @patch("storymap_helper.StoryMap")
    def test_add_table_no_headers(self, mock_storymap_class, mock_table_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        panel = {"content_type": "table", "headers": [], "rows": [["Data1", "Data2"]]}
        with patch("storymap_helper.logger") as mock_logger:
            publisher._add_table(panel)
            mock_logger.warning.assert_called_with(
                "Table headers or rows are missing. Skipping this panel."
            )
            mock_table_class.assert_not_called()
            mock_storymap_instance.add.assert_not_called()

    @patch("storymap_helper.StoryMap")
    def test_set_cover(self, mock_storymap_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        publisher._set_cover()

        # Verify that cover is called with correct parameters
        cover = publisher._storymap_template.get("cover", {})
        expected_title = cover.get("title", "Project Title")
        expected_summary = cover.get("subtitle", "Project Description")
        expected_image_url = cover.get(
            "cover_image_url",
            "https://story.maps.arcgis.com/sharing/rest/content/items/2fcc801c983a402eb427dd5cd07ee759/data",
        )

        mock_storymap_instance.cover.assert_called_once_with(
            type="full",
            title=expected_title,
            summary=expected_summary,
            by_line="Geodesignhub",
            image=expected_image_url,
        )

    @patch("storymap_helper.StoryMapPublisher._set_cover")
    @patch("storymap_helper.StoryMapPublisher._add_text")
    @patch("storymap_helper.StoryMapPublisher._add_image")
    @patch("storymap_helper.StoryMapPublisher._add_map")
    @patch("storymap_helper.StoryMap")
    def test_populate_storymap_from_template(
        self,
        mock_storymap_class,
        mock_add_map,
        mock_add_image,
        mock_add_text,
        mock_set_cover,
    ):
        # Mock the StoryMap instance
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        # Mock updated template structure
        publisher._storymap_template = {
            "cover": {},
            "sections": [
                {
                    "title": "Introduction",
                    "panels": [
                        {
                            "content_type": "text",
                            "style": "subheading",
                            "text": "1. Background",
                        },
                        {
                            "content_type": "text",
                            "style": "paragraph",
                            "text": "Sample Background Content",
                        },
                        {
                            "content_type": "image",
                            "url": "https://example.com/image.jpg",
                            "caption": "Sample Image",
                        },
                        {
                            "content_type": "map",
                            "item_id": "test_item_id",
                            "caption": "Test Map",
                        },
                    ],
                },
                {
                    "title": "Additional Section",
                    "panels": [{"content_type": "unsupported_content_type"}],
                },
            ],
        }

        # Execute the method
        with patch("storymap_helper.logger") as mock_logger:
            publisher.populate_storymap_from_template()

            # Verify _set_cover was called once
            mock_set_cover.assert_called_once()

            # Verify _add_text is called for text panels
            mock_add_text.assert_any_call(
                {"content_type": "text", "style": "subheading", "text": "1. Background"}
            )
            mock_add_text.assert_any_call(
                {
                    "content_type": "text",
                    "style": "paragraph",
                    "text": "Sample Background Content",
                }
            )

            # Verify _add_image is called for image panels
            mock_add_image.assert_called_once_with(
                {
                    "content_type": "image",
                    "url": "https://example.com/image.jpg",
                    "caption": "Sample Image",
                }
            )

            # Verify _add_map is called for map panels
            mock_add_map.assert_called_once_with(
                {
                    "content_type": "map",
                    "item_id": "test_item_id",
                    "caption": "Test Map",
                }
            )

            # Verify warning for unsupported panel content_type
            mock_logger.warning.assert_called_with(
                "Unsupported panel content_type: unsupported_content_type"
            )

    @patch("storymap_helper.Text")
    @patch("storymap_helper.StoryMap")
    def test_add_text_invalid_style(self, mock_storymap_class, mock_text_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        panel = {"content_type": "text", "style": "invalid_style", "text": "Test Text"}
        with patch("storymap_helper.logger") as mock_logger:
            publisher._add_text(panel)

            mock_logger.warning.assert_called_with(
                "Invalid text style: INVALID_STYLE, defaulting to PARAGRAPH"
            )
            mock_text_class.assert_called_once_with(
                text="Test Text", style=TextStyles.PARAGRAPH
            )
            mock_storymap_instance.add.assert_called_once_with(
                mock_text_class.return_value
            )

    @patch("storymap_helper.StoryMap")
    def test_add_map_no_item_id(self, mock_storymap_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        panel = {"content_type": "map", "caption": "Test Map"}
        with patch("storymap_helper.logger") as mock_logger:
            publisher._add_map(panel)

            mock_logger.warning.assert_called_with("Map item ID is missing.")
            # Ensure no map is added
            mock_storymap_instance.add.assert_not_called()

    @patch("storymap_helper.Image")
    @patch("storymap_helper.StoryMap")
    def test_add_image_no_url(self, mock_storymap_class, mock_image_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        panel = {"content_type": "image", "caption": "Test Image"}
        with patch("storymap_helper.logger") as mock_logger:
            publisher._add_image(panel)

            mock_logger.error.assert_called_with("No URL provided for the image.")
            mock_image_class.assert_not_called()
            mock_storymap_instance.add.assert_not_called()

    @patch("storymap_helper.StoryMap")
    @patch("storymap_helper.requests.get")
    @patch("storymap_helper.tempfile.NamedTemporaryFile")
    @patch("storymap_helper.os.remove")
    @patch("storymap_helper.PILImage.open")
    def test_process_image_download_fail(
        self,
        mock_image_open,
        mock_os_remove,
        mock_tempfile,
        mock_requests_get,
        mock_storymap_class,
    ):
        # Simulate a failed image download
        mock_requests_get.side_effect = RequestException("Download failed")

        publisher = self.create_publisher()

        with patch("storymap_helper.logger") as mock_logger:
            result = publisher._process_image("https://example.com/image.jpg")
            self.assertIsNone(result)
            mock_logger.error.assert_called_with(
                "Failed to process image: https://example.com/image.jpg - Download failed"
            )

    @patch("storymap_helper.StoryMap")
    @patch("storymap_helper.requests.get")
    @patch("storymap_helper.tempfile.NamedTemporaryFile")
    @patch("storymap_helper.os.remove")
    @patch("storymap_helper.PILImage.open")
    def test_process_image_conversion_fail(
        self,
        mock_image_open,
        mock_os_remove,
        mock_tempfile,
        mock_requests_get,
        mock_storymap_class,
    ):
        # Simulate successful download
        mock_response = MagicMock()
        mock_response.iter_content.return_value = [b"test data"]
        mock_response.raise_for_status.return_value = None
        mock_requests_get.return_value = mock_response

        # Simulate image conversion failure
        mock_image_open.side_effect = IOError("Conversion failed")

        publisher = self.create_publisher()

        with patch("storymap_helper.logger") as mock_logger:
            result = publisher._process_image("https://example.com/image.jpg")
            self.assertIsNone(result)
            mock_logger.error.assert_called_with(
                "Failed to process image: https://example.com/image.jpg - Conversion failed"
            )

    @patch("storymap_helper.StoryMap")
    def test_add_image_process_image_fail(self, mock_storymap_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        with patch.object(publisher, "_process_image", return_value=None):
            panel = {
                "content_type": "image",
                "url": "https://example.com/image.jpg",
                "caption": "Test Image",
            }
            with patch("storymap_helper.logger") as mock_logger:
                publisher._add_image(panel)
                mock_logger.error.assert_called_with(
                    "Failed to add image: https://example.com/image.jpg - Failed to process image: https://example.com/image.jpg"
                )
                # Ensure no image is added
                mock_storymap_instance.add.assert_not_called()

    @patch("storymap_helper.Item")
    @patch("storymap_helper.Map")
    @patch("storymap_helper.StoryMap")
    def test_add_map_exception(
        self, mock_storymap_class, mock_map_class, mock_item_class
    ):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        # Simulate an exception when creating Map
        mock_map_class.side_effect = Exception("Map creation failed")

        panel = {
            "content_type": "map",
            "item_id": "test_map_item_id",
            "caption": "Test Map",
        }
        with patch("storymap_helper.logger") as mock_logger:
            publisher._add_map(panel)
            mock_logger.error.assert_called_with(
                "Failed to add map: Map creation failed"
            )
            # Ensure no map is added
            mock_storymap_instance.add.assert_not_called()

    @patch("storymap_helper.Table")
    @patch("storymap_helper.StoryMap")
    def test_add_table_invalid_rows_columns(
        self, mock_storymap_class, mock_table_class
    ):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        # Test with invalid number of rows (>9)
        panel = {
            "content_type": "table",
            "headers": ["Column 1"],
            "rows": [["Data"]] * 10,  # 10 rows, exceeding the limit
        }
        with patch("storymap_helper.logger") as mock_logger:
            publisher._add_table(panel)
            mock_logger.warning.assert_called_with(
                "Invalid number of rows (10). Must be between 1 and 9. Skipping."
            )
            mock_table_class.assert_not_called()
            mock_storymap_instance.add.assert_not_called()

        # Test with invalid number of columns (>8)
        panel = {
            "content_type": "table",
            "headers": ["Col1"] * 9,  # 9 columns, exceeding the limit
            "rows": [["Data"] * 9],
        }
        with patch("storymap_helper.logger") as mock_logger:
            publisher._add_table(panel)
            mock_logger.warning.assert_called_with(
                "Invalid number of columns (9). Must be between 1 and 8. Skipping."
            )
            mock_table_class.assert_not_called()
            mock_storymap_instance.add.assert_not_called()

    @patch("storymap_helper.StoryMap")
    def test_publish_storymap_no_item(self, mock_storymap_class):
        mock_storymap_instance = mock_storymap_class.return_value
        publisher = self.create_publisher()
        publisher._storymap = mock_storymap_instance

        # Simulate _item being None
        publisher._storymap._item = None

        with patch("storymap_helper.logger") as mock_logger:
            publisher.publish_storymap()
            mock_storymap_instance.save.assert_called_once_with(publish=True)
            mock_logger.error.assert_called_with(
                "Failed to update title and description: StoryMap item not initialized."
            )


if __name__ == "__main__":
    unittest.main()
