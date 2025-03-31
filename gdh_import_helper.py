from arcgis.gis import GIS, Item

from data_definitions import ImporttoGDHPayload
import logging
import os
from dotenv import load_dotenv, find_dotenv

logger = logging.getLogger("esri-gdh-bridge")

load_dotenv(find_dotenv())
ENV_FILE = find_dotenv()


def process_gdh_import(_migrate_to_gdh_payload: ImporttoGDHPayload):
    
    my_agol_helper = _migrate_to_gdh_payload.agol_helper
    items_to_migrate = _migrate_to_gdh_payload.items_to_migrate
    file_type = _migrate_to_gdh_payload.file_type
    logger.info(f"Starting migration process for file type: {file_type}")
    for item_id in items_to_migrate:
        try:
            # Get the item from ArcGIS Online
            gis = my_agol_helper.get_gis()
            item = gis.content.get(item_id)

            if not item:
                logger.warning(f"Item with ID {item_id} not found.")
                continue
            downloaded_file = my_agol_helper.download_item_to_tmp_file(item_id=item)

            # Create a simplified version of the GeoJSON
            # Save as FGB

            # Upload to S3 bucket

            # Send to Geodesignhub project 
        
            os.unlink(downloaded_file.name)

            
        except Exception as e:
            logger.error(f"Error processing item {item_id}: {e}")