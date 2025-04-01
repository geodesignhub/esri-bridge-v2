import tempfile
from data_definitions import ImporttoGDHItem
from utils import ArcGISHelper
from dataclasses import dataclass
from typing import List
import logging
import os
from dotenv import load_dotenv, find_dotenv
import GeodesignHub
import fiona
import geopandas as gpd
import boto3
from botocore.exceptions import ClientError
import config
import shutil

logger = logging.getLogger("esri-gdh-bridge")

load_dotenv(find_dotenv())
ENV_FILE = find_dotenv()


@dataclass
class ImporttoGDHPayload:
    """
    Represents the payload for importing items to GDH (Geospatial Data Hub).
    Attributes:
        agol_helper (ArcGISHelper): An instance of the ArcGISHelper class to assist with AGOL operations.
        items_to_migrate (List[ImporttoGDHItem]): A list of items to be migrated to GDH.
        file_type (str): The type of file being processed (e.g., 'shapefile', 'geojson').
    """

    agol_token: str
    items_to_migrate: List[ImporttoGDHItem]
    file_type: str


def process_gdh_import(_migrate_to_gdh_payload: ImporttoGDHPayload):
    """
    Handles the migration of items from ArcGIS Online to Geodesignhub.

    This function facilitates the migration of specified items from ArcGIS Online
    to a Geodesignhub project. It performs the following steps:
    - Downloads the items from ArcGIS Online.
    - Processes the downloaded data (e.g., simplifies geometries, converts formats).
    - Uploads the processed data to an S3 bucket.
    - Sends the processed data to the specified Geodesignhub project.

    Args:
        _migrate_to_gdh_payload (ImporttoGDHPayload): An object containing
            the payload for the migration process, including:
            - agol_helper (ArcGISHelper): Helper object for interacting with ArcGIS Online.
            - items_to_migrate (List[ImporttoGDHItem]): List of items to be migrated.
            - file_type (str): The type of file being processed (e.g., 'shapefile', 'geojson').

    Workflow:
        1. Retrieve the GIS object using the provided AGOL helper.
        2. Fetch each item from ArcGIS Online using its ID.
        3. Download the item to a temporary file.
        4. Load the file into a GeoDataFrame and simplify its geometries.
        5. Save the original and simplified data in GeoJSON and FlatGeobuf formats.
        6. Upload the processed files to an S3 bucket.
        7. Send the processed data to the specified Geodesignhub project.
        8. Clean up temporary files after processing.

    Logs:
        - Logs the start of the migration process with the file type.
        - Logs warnings if an item is not found in ArcGIS Online.
        - Logs errors if any issues occur during processing or uploading.

    Raises:
        Exception: Logs and raises exceptions encountered during the migration process.
    """

    my_agol_helper = ArcGISHelper(agol_token=_migrate_to_gdh_payload.agol_token)
    items_to_migrate = _migrate_to_gdh_payload.items_to_migrate

    file_type = _migrate_to_gdh_payload.file_type
    logger.info(f"Starting migration process for file type: {file_type}")

    S3_CDN_ENDPOINT = config.external_api_settings["S3_ENDPOINT"]
    session = boto3.session.Session()
    client = session.client(
        "s3",
        region_name="ams3",
        endpoint_url="https://ams3.digitaloceanspaces.com",
        aws_access_key_id=config.external_api_settings["S3_KEY"],
        aws_secret_access_key=config.external_api_settings["S3_SECRET"],
    )
    bucket_name = config.external_api_settings["S3_BUCKET_NAME"]
    try:
        client.head_bucket(Bucket=bucket_name)
        logger.info(f"Successfully connected to the bucket '{bucket_name}'.")
    except Exception as e:
        logger.error(f"Failed to connect to the bucket '{bucket_name}': {e}")
        exit(1)

    temp_dir = tempfile.TemporaryDirectory(prefix="esri_gdh_import_")
    
    for item_to_process in items_to_migrate:
        if item_to_process.agol_item_type == file_type == "geojson":
            logger.info(
                f"Processing item {item_to_process.agol_id} of type {file_type}"
            )
            # Get the item from ArcGIS Online
            gis = my_agol_helper.get_gis()
            item = gis.content.get(item_to_process.agol_id)

            if not item:
                logger.warning(f"Item with ID {item_to_process.agol_id} not found.")
                continue

            my_agol_helper.download_geojson_item_to_tmp_file(
                item=item, save_path=temp_dir.name
            )
            # Get all the *.geojson files in the directory
            downloaded_file = [
                f for f in os.listdir(temp_dir.name) if f.endswith(".geojson")
            ][0]
            downloaded_file = os.path.join(temp_dir.name, downloaded_file)
            print(f"Downloaded file: {downloaded_file}")
            # Load the downloaded file into a GeoDataFrame
            try:
                gdf = gpd.read_file(downloaded_file)
            except Exception as e:
                logger.error(f"Error reading file {downloaded_file}: {e}")
                # my_agol_helper.clear_downloaded_tmp_file_directory(temp_dir=temp_dir)
                continue
            # Simplify the geometry
            simplified_gdf = gdf.copy()
            simplified_gdf["geometry"] = simplified_gdf["geometry"].simplify(
                tolerance=0.01, preserve_topology=True
            )

            # Save the original GeoJSON
            original_geojson_path = downloaded_file.name.replace(
                ".tmp", "_original.geojson"
            )
            gdf.to_file(original_geojson_path, driver="GeoJSON")

            # Save the simplified GeoJSON
            simplified_geojson_path = downloaded_file.name.replace(
                ".tmp", "_simplified.geojson"
            )
            simplified_gdf.to_file(simplified_geojson_path, driver="GeoJSON")

            # Delete the downloaded temporary file
            os.unlink(downloaded_file.name)
            # Save as FlatGeobuf (FGB) for original GeoJSON
            original_fgb_path = original_geojson_path.replace(
                "_original.geojson", "_original.fgb"
            )
            with fiona.open(original_geojson_path, "r") as src:
                with fiona.open(
                    original_fgb_path,
                    "w",
                    driver="FlatGeobuf",
                    crs=src.crs,
                    schema=src.schema,
                ) as dst:
                    for feature in src:
                        dst.write(feature)

            # Save as FlatGeobuf (FGB) for simplified GeoJSON
            simplified_fgb_path = simplified_geojson_path.replace(
                "_simplified.geojson", "_simplified.fgb"
            )
            with fiona.open(simplified_geojson_path, "r") as src:
                with fiona.open(
                    simplified_fgb_path,
                    "w",
                    driver="FlatGeobuf",
                    crs=src.crs,
                    schema=src.schema,
                ) as dst:
                    for feature in src:
                        dst.write(feature)

            # Delete the original GeoJSON files
            os.unlink(original_geojson_path)
            os.unlink(simplified_geojson_path)

            # Create a target path in the bucket
            fgb_basepath = os.path.basename(original_fgb_path)
            simplified_fgb_path = os.path.basename(original_fgb_path)

            target_path = f"projects/{item_to_process.target_gdh_project_id}/systems/{item_to_process.target_gdh_system}/"
            logger.info(f"Target path in the bucket: {target_path}")
            # Upload the original FGB to the S3 bucket
            try:
                with open(original_fgb_path, "rb") as f:
                    client.upload_fileobj(
                        f,
                        bucket_name,
                        os.path.join(target_path, fgb_basepath),
                    )
                    logger.info(
                        f"Uploaded {original_fgb_path} to S3 bucket {bucket_name} at {target_path}."
                    )
            except ClientError as e:
                logger.error(f"Failed to upload {original_fgb_path} to S3 bucket: {e}")
                raise

            # Upload the simplified FGB to the S3 bucket
            try:
                with open(simplified_fgb_path, "rb") as f:
                    client.upload_fileobj(
                        f,
                        bucket_name,
                        os.path.join(target_path, simplified_fgb_path),
                    )
                    logger.info(
                        f"Uploaded {simplified_fgb_path} to S3 bucket {bucket_name} at {target_path}."
                    )
            except ClientError as e:
                logger.error(
                    f"Failed to upload {simplified_fgb_path} to S3 bucket: {e}"
                )
                raise

            # Delete the local FGB files after upload
            os.unlink(original_fgb_path)
            os.unlink(simplified_fgb_path)

            # Send to Geodesignhub project
            gdh_api_helper = GeodesignHub.GeodesignHubClient(
                url=config.external_api_settings["GDH_SERVICE_URL"],
                project_id=item_to_process.target_gdh_project_id,
                token=item_to_process.gdh_token,
            )

            def post_to_gdh_external_geometries(url, description):
                gdh_api_helper.post_as_diagram_with_external_geometries(
                    url=url,
                    layer_type="fgb-layer",
                    projectorpolicy=item_to_process.target_gdh_project_or_policy,
                    featuretype="polygon",
                    description=description,
                    sysid=item_to_process.target_gdh_system,
                    fundingtype="pu",
                    cost=0,
                    costtype="t",
                    additional_metadata={},
                )

            print(S3_CDN_ENDPOINT + "/" + target_path + "/" + fgb_basepath)
            print(S3_CDN_ENDPOINT + "/" + target_path + "/" + simplified_fgb_path)
            # # Post original FGB
            # post_to_gdh_external_geometries(
            #     url=S3_CDN_ENDPOINT + "/" + target_path + "/" + fgb_basepath,
            #     description="Imported from AGOL (Original)",
            # )

            # # Post simplified FGB
            # post_to_gdh_external_geometries(
            #     url=S3_CDN_ENDPOINT + "/" + target_path + "/" + simplified_fgb_path,
            #     description="Imported from AGOL (Simplified)",
            # )

            # os.unlink(downloaded_file.name)

        # shutil.rmtree(temp_dir.name, ignore_errors=True)
        # logger.info(f"Temporary directory {temp_dir.name} deleted.")
