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
from conn import get_redis
import redis

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

    session_id: str
    agol_token: str
    items_to_migrate: List[ImporttoGDHItem]
    file_type: str


def log_to_redis(message: str, session_id: str, redis_instance: redis.Redis):
    """
    Logs a message to Redis associated with the session ID.
    """
    logger.info(message)
    redis_instance.lpush(f"session_logs:{session_id}", message)


def process_geopackage_layers(
    downloaded_file: str, session_id: str, redis_instance: redis.Redis
) -> List[gpd.GeoDataFrame]:
    """
    Processes layers from a GeoPackage file and returns a list of GeoDataFrames.

    Args:
        downloaded_file (str): Path to the downloaded GeoPackage file.
        session_id (str): Session ID for logging purposes.
        redis_instance (redis.Redis): Redis instance for logging.

    Returns:
        List[gpd.GeoDataFrame]: A list of GeoDataFrames for each processed layer.
    """
    log_to_redis(
        f"Reading layers from GeoPackage file: {downloaded_file}.",
        session_id,
        redis_instance,
    )
    all_gdf: List[gpd.GeoDataFrame] = []
    for layername in fiona.listlayers(downloaded_file):
        log_to_redis(
            f"Processing layer: {layername}.",
            session_id,
            redis_instance,
        )
        with fiona.open(downloaded_file, layer=layername):
            # Read the file into a GeoDataFrame
            gdf: gpd.GeoDataFrame = gpd.read_file(downloaded_file, layer=layername)
            if gdf.empty:
                log_to_redis(
                    "Encountered an empty GeoDataFrame, skipping.",
                    session_id,
                    redis_instance,
                )
            else:
                exploded = gdf.explode(index_parts=False)

                filtered = exploded.filter(["geometry"])
                rp_gdf = filtered.to_crs(epsg=4326)

                all_gdf.append(rp_gdf)

    return all_gdf


def process_gdh_import(_migrate_to_gdh_payload: ImporttoGDHPayload) -> None:
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
    my_agol_helper: ArcGISHelper = ArcGISHelper(
        agol_token=_migrate_to_gdh_payload.agol_token
    )
    items_to_migrate: List[ImporttoGDHItem] = _migrate_to_gdh_payload.items_to_migrate

    file_type: str = _migrate_to_gdh_payload.file_type

    r: redis.Redis = get_redis()

    log_to_redis(
        f"Starting migration process for file type: {file_type}",
        _migrate_to_gdh_payload.session_id,
        r,
    )

    S3_CDN_ENDPOINT: str = config.external_api_settings["S3_CDN_ENDPOINT"]
    session: boto3.session.Session = boto3.session.Session()
    log_to_redis(
        "Initializing S3 client session.", _migrate_to_gdh_payload.session_id, r
    )
    client: boto3.client = session.client(
        "s3",
        region_name="ams3",
        endpoint_url="https://ams3.digitaloceanspaces.com",
        aws_access_key_id=config.external_api_settings["S3_KEY"],
        aws_secret_access_key=config.external_api_settings["S3_SECRET"],
    )
    bucket_name: str = config.external_api_settings["S3_BUCKET_NAME"]
    log_to_redis(
        f"Attempting to connect to the S3 bucket: {bucket_name}.",
        _migrate_to_gdh_payload.session_id,
        r,
    )
    try:
        client.head_bucket(Bucket=bucket_name)
        log_to_redis(
            f"Successfully connected to the bucket '{bucket_name}'.",
            _migrate_to_gdh_payload.session_id,
            r,
        )
    except Exception as e:
        log_to_redis(
            f"Failed to connect to the bucket '{bucket_name}': {e}",
            _migrate_to_gdh_payload.session_id,
            r,
        )
        exit(1)

    temp_dir: tempfile.TemporaryDirectory = tempfile.TemporaryDirectory(
        prefix="esri_gdh_import_", delete=False
    )
    log_to_redis(
        f"Created temporary directory at {temp_dir.name}.",
        _migrate_to_gdh_payload.session_id,
        r,
    )

    for item_to_process in items_to_migrate:
        log_to_redis(
            f"Processing item with ID {item_to_process.agol_id}.",
            _migrate_to_gdh_payload.session_id,
            r,
        )
        if item_to_process.agol_item_type == file_type == "geopackage":
            log_to_redis(
                f"Item {item_to_process.agol_id} matches the file type {file_type}.",
                _migrate_to_gdh_payload.session_id,
                r,
            )
            # Get the item from ArcGIS Online
            log_to_redis(
                "Retrieving GIS object from ArcGIS Online.",
                _migrate_to_gdh_payload.session_id,
                r,
            )
            gis: object = my_agol_helper.get_gis()
            item: object = gis.content.get(item_to_process.agol_id)

            if not item:
                log_to_redis(
                    f"Item with ID {item_to_process.agol_id} not found.",
                    _migrate_to_gdh_payload.session_id,
                    r,
                )
                continue

            log_to_redis(
                f"Downloading item {item_to_process.agol_id} to temporary directory.",
                _migrate_to_gdh_payload.session_id,
                r,
            )
            my_agol_helper.download_geojson_item_to_tmp_file(
                item=item, save_path=temp_dir.name
            )

            # Get all the *.geojson files in the directory
            log_to_redis(
                "Searching for downloaded GeoPackage files.",
                _migrate_to_gdh_payload.session_id,
                r,
            )
            downloaded_file_name: str = [
                f for f in os.listdir(temp_dir.name) if f.endswith(".gpkg")
            ][0]

            downloaded_file: str = os.path.join(temp_dir.name, downloaded_file_name)
            log_to_redis(
                f"Found downloaded file: {downloaded_file}.",
                _migrate_to_gdh_payload.session_id,
                r,
            )
            # Load the downloaded file into a GeoDataFrame

            try:
                all_gdf = process_geopackage_layers(
                    downloaded_file=downloaded_file,
                    session_id=_migrate_to_gdh_payload.session_id,
                    redis_instance=r,
                )

            except Exception as e:
                log_to_redis(
                    f"Error reading file {downloaded_file}: {e}",
                    _migrate_to_gdh_payload.session_id,
                    r,
                )
                continue
            # Simplify the geometry
            for gdf in all_gdf:
                log_to_redis(
                    "Simplifying geometries in GeoDataFrame.",
                    _migrate_to_gdh_payload.session_id,
                    r,
                )
                simplified_gdf: gpd.GeoDataFrame = gdf.copy()
                simplified_gdf["geometry"] = simplified_gdf["geometry"].simplify(
                    tolerance=0.01, preserve_topology=True
                )

                # Save the original GeoDataFrame as FlatGeobuf (FGB)
                original_fgb_path: str = os.path.join(
                    temp_dir.name, f"{item_to_process.agol_id}.fgb"
                )
                gdf.to_file(original_fgb_path, driver="FlatGeobuf")
                # Save the simplified GeoDataFrame as FlatGeobuf (FGB)
                simplified_fgb_path: str = os.path.join(
                    temp_dir.name, f"{item_to_process.agol_id}_generalised.fgb"
                )
                simplified_gdf.to_file(simplified_fgb_path, driver="FlatGeobuf")

                log_to_redis(
                    f"Saved original and simplified FGB files for item {item_to_process.agol_id}.",
                    _migrate_to_gdh_payload.session_id,
                    r,
                )

            original_file_name: str = os.path.basename(original_fgb_path)
            simplified_file_name: str = os.path.basename(simplified_fgb_path)
            target_path: str = f"projects/{item_to_process.target_gdh_project_id}/systems/{item_to_process.target_gdh_system}"
            try:
                log_to_redis(
                    f"Uploading original FGB file to S3 bucket at {target_path}.",
                    _migrate_to_gdh_payload.session_id,
                    r,
                )
                with open(original_fgb_path, "rb") as f:
                    client.upload_fileobj(
                        f,
                        bucket_name,
                        os.path.join(target_path, original_file_name),
                        ExtraArgs={"ACL": "public-read"},
                    )
                    log_to_redis(
                        f"Uploaded {original_fgb_path} to S3 bucket {bucket_name} at {target_path}.",
                        _migrate_to_gdh_payload.session_id,
                        r,
                    )
            except ClientError as e:
                log_to_redis(
                    f"Failed to upload {original_fgb_path} to S3 bucket: {e}",
                    _migrate_to_gdh_payload.session_id,
                    r,
                )
                raise

            # Upload the simplified FGB to the S3 bucket
            try:
                log_to_redis(
                    f"Uploading simplified FGB file to S3 bucket at {target_path}.",
                    _migrate_to_gdh_payload.session_id,
                    r,
                )
                with open(simplified_fgb_path, "rb") as f:
                    client.upload_fileobj(
                        f,
                        bucket_name,
                        os.path.join(target_path, simplified_file_name),
                        ExtraArgs={"ACL": "public-read"},
                    )
                    log_to_redis(
                        f"Uploaded {simplified_fgb_path} to S3 bucket {bucket_name} at {target_path}.",
                        _migrate_to_gdh_payload.session_id,
                        r,
                    )
            except ClientError as e:
                log_to_redis(
                    f"Failed to upload {simplified_fgb_path} to S3 bucket: {e}",
                    _migrate_to_gdh_payload.session_id,
                    r,
                )
                raise

            # Send to Geodesignhub project
            log_to_redis(
                "Initializing GeodesignHub API client.",
                _migrate_to_gdh_payload.session_id,
                r,
            )
            gdh_api_helper: GeodesignHub.GeodesignHubClient = (
                GeodesignHub.GeodesignHubClient(
                    url=config.external_api_settings["GDH_SERVICE_URL"],
                    project_id=item_to_process.target_gdh_project_id,
                    token=item_to_process.gdh_api_token,
                )
            )

            def post_to_gdh_external_geometries(
                gdh_api_helper: GeodesignHub.GeodesignHubClient,
                url: str,
                description: str,
            ) -> None:
                log_to_redis(
                    f"Posting data to GeodesignHub: {description}.",
                    _migrate_to_gdh_payload.session_id,
                    r,
                )
                diagram_response = (
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
                    )
                )
                log_to_redis(
                    f"Posted data to GeodesignHub: {diagram_response.text}.",
                    _migrate_to_gdh_payload.session_id,
                    r,
                )

            original_fgb_url: str = (
                S3_CDN_ENDPOINT + "/" + target_path + "/" + original_file_name
            )

            # Post original FGB
            log_to_redis(
                "Posting original FGB to GeodesignHub.",
                _migrate_to_gdh_payload.session_id,
                r,
            )
            post_to_gdh_external_geometries(
                gdh_api_helper=gdh_api_helper,
                url=original_fgb_url,
                description="Imported from AGOL (Original)",
            )

        log_to_redis(
            f"Cleaning up temporary directory {temp_dir.name}.",
            _migrate_to_gdh_payload.session_id,
            r,
        )
        shutil.rmtree(temp_dir.name, ignore_errors=True)
        log_to_redis(
            f"Temporary directory {temp_dir.name} deleted.",
            _migrate_to_gdh_payload.session_id,
            r,
        )
