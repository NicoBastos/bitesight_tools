
import os
import shutil
from pathlib import Path
from datetime import datetime
import time


from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, UploadFile, Form, File
from fastapi.middleware.cors import CORSMiddleware
import requests
from supabase import create_client, Client
import instaloader
from models import InstaAssetForm

import mux_python
from mux_python.rest import ApiException






# Load environment variables
load_dotenv()

# Constants
SUPABASE_URL: str = os.environ.get('NICO_SUPABASE_URL')
SUPABASE_KEY: str = os.environ.get('NICO_API_KEY')
SUPABASE_BUCKET: str = 'bucket'
RESTAURANT_CONCEPT_TABLE: str = "restaurant_concept"
VIDEO_METADATA_TABLE: str = "video_meta_data"
DOWNLOADS_DIR: Path = Path('downloads')

configuration = mux_python.Configuration()
configuration.username = os.getenv('MUX_TOKEN_ID')
configuration.password = os.getenv('MUX_TOKEN_SECRET')
# Initialize FastAPI app
app = FastAPI()

# CORS Middleware
app.add_middleware(
  CORSMiddleware,
  allow_origins=["*"],
  allow_credentials=True,
  allow_methods=["*"],
  allow_headers=["*"],
)

# Create a Mux API client for direct uploads
mux_direct_uploads_api = mux_python.DirectUploadsApi(mux_python.ApiClient(configuration))
mux_assets_api = mux_python.AssetsApi(mux_python.ApiClient(configuration))

# Initialize Supabase client
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

def delete_file_and_siblings(file_path: Path | None):
    if file_path is None:
        return

    try:
        # Delete the file
        file_path.unlink(True)
        
        # Get the parent directory
        parent_dir = file_path.parent
        
        # Delete all sibling files
        for sibling_file in parent_dir.iterdir():
            if sibling_file.is_file():
                sibling_file.unlink(True)
                
        # Delete the parent directory
        shutil.rmtree(parent_dir)
    except Exception as e:
        print(f"Failed to delete file and its siblings: {e}")


def handle_instagram_download(post_url: str) -> Path | None:
    """Download video from Instagram post URL.
    
    Args:
        post_url (str): The URL of the Instagram post.

    Returns:
        Union[Path, None]: The path to the downloaded video or None if not found.
    """
    loader = instaloader.Instaloader(download_pictures=False, download_videos=True, download_video_thumbnails=False, download_geotags=False, download_comments=False)
    shortcode = post_url.split("/")[-2]
    post = instaloader.Post.from_shortcode(loader.context, shortcode)

    if not post.is_video:
        return None

    target_directory = Path(f"downloads/{post.shortcode}")
    target_directory.mkdir(parents=True, exist_ok=True)
    loader.download_post(post, target=target_directory)

    for file in target_directory.iterdir():
        if file.is_file() and file.suffix == '.mp4':
            return file

    return None


def getOrCreateRestaurant(concept_name: str) -> str:
    restaurant_concept_data, count = supabase.table("restaurant_concept").select("*").eq("concept_name", concept_name).execute()
        
    if len(restaurant_concept_data[1]) < 1:
        restaurant_concept_data, count = supabase.table("restaurant_concept").insert({"concept_name": concept_name}).execute()

    return restaurant_concept_data[1][0]['restaurant_concept_id']




def waitForMuxAsset(create_upload_response) -> str:
    # Check for the asset to become ready
    attempts = 0
    while attempts < 5:
        upload_response = mux_direct_uploads_api.get_direct_upload(create_upload_response.data.id)
        mux_asset_id = upload_response.data.asset_id
        if mux_asset_id is not None:
            return mux_asset_id
        attempts += 1
        time.sleep(attempts*2)
        
    raise Exception(f"Mux asset id is not available after {attempts} attempts")


async def uploadToMux(video_path: Path) -> (str, str):
    # Create a new Direct Upload
        create_asset_request = mux_python.CreateAssetRequest(playback_policy=[mux_python.PlaybackPolicy.PUBLIC])
        create_upload_request = mux_python.CreateUploadRequest(new_asset_settings=create_asset_request, cors_origin='*')
        create_upload_response = mux_direct_uploads_api.create_direct_upload(create_upload_request)

        # Get the authenticated URL
        upload_url = create_upload_response.data.url

        # Upload the video file
        with open(video_path, 'rb') as file:
            requests.put(upload_url, data=file)
        
        mux_asset_id = waitForMuxAsset(create_upload_response)

        asset = mux_assets_api.get_asset(mux_asset_id)

        # Now you can access the playback_ids
        mux_playback_id = asset.data.playback_ids[0].id
        return mux_asset_id, mux_playback_id

async def uploadSupabaseStorage(video_path: Path) -> str:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    new_video_filename = f"{video_path.stem}_{timestamp}{video_path.suffix}"

    
    with video_path.open('rb') as video_file:
        upload_response = supabase.storage.from_("videos").upload(new_video_filename, video_file)

        if not upload_response:
            # This line below is kind of sketchy
            raise Exception(f"An error occurred when uploading to supabase: {upload_response.json().get('error', 'Unknown Error')}")

    public_url = supabase.storage.from_("videos").get_public_url(new_video_filename)
    return public_url


async def uploadFromLocal(video_path: Path | None, src_metadata: dict, restaurant_concept_id: str, dish_name: str) -> dict:
    if video_path is not None:

        # TODO: test and Make uploadToMux and uploadSupabaseStorage parallel
        # mux_asset_id, mux_playback_id = await uploadToMux(video_path)
        # public_url = await uploadSupabaseStorage(video_path)

        mux_promise = uploadToMux(video_path)
        storage_promise = uploadSupabaseStorage(video_path)

        mux_asset_id, mux_playback_id = await mux_promise
        public_url = await storage_promise
        
        data, count = supabase.table("dish_asset").insert({
            "dish_name": dish_name,
            "mux_playback_id": mux_playback_id, 
            "mux_asset_id": mux_asset_id, 
            "raw_video_url": public_url,
            "restaurant_concept_id": restaurant_concept_id,
            "source_metadata": src_metadata
        }).execute()

        return {"detail": "Video downloaded and uploaded successfully.", "data": data}
    else:
        raise HTTPException(status_code=400, detail="The post does not contain a video or it could not be downloaded.")
    


async def save_upload_file_tmp(upload_file: UploadFile, path: Path):
    # with open(path, "wb") as buffer:
    #     shutil.copyfileobj(upload_file.file, buffer)
       with open(path, "wb+") as file_object:
           file_object.write(await upload_file.read())


# Endpoint to add video asset
@app.post("/ManualAddVideoAsset/")
async def manual_add_video_asset(dish_name: str = Form(...), restaurant_name: str = Form(...), file: UploadFile = File(...), source: str = Form(...)):
    responseDict = None
    video_path = None
    try:
        
        print("restaurant_concept_data: ",dish_name, restaurant_name)
        # Database logic to handle restaurant concept
        # Assuming 'supabases' is an instance of your Supabase client
        
        # Handle video processing
        restaurant_concept_id = getOrCreateRestaurant(restaurant_name)

        # Ensure downloads directory exists
        downloads_dir = Path("downloads")
        downloads_dir.mkdir(parents=True, exist_ok=True)

        # Save the uploaded file and get the path
        video_path = downloads_dir / file.filename
        await save_upload_file_tmp(file, video_path)

        src_metadata = {
            "source": source
        }
        responseDict = await uploadFromLocal(video_path,src_metadata, restaurant_concept_id, dish_name)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        delete_file_and_siblings(video_path)
    return responseDict


@app.post("/InstaAddVideoAsset/")
async def insta_add_video_asset(params : InstaAssetForm):
    """Endpoint to download Instagram video and save to Supabase.

    Args:
        video_asset_form (VideoAssetForm): Video asset data

    Returns:
        dict: Response message.

    """
    responseDict = None
    video_path = None
    try:
        restaurant_concept_id = getOrCreateRestaurant(params.restaurant_name)
    
        video_path = handle_instagram_download(params.post_url)
        src_metadata = {
                    "source": "Instagram",
                    "post_url": params.post_url
                }
        responseDict = await uploadFromLocal(video_path,src_metadata, restaurant_concept_id, params.dish_name)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        delete_file_and_siblings(video_path)
    return responseDict


@app.get("/getAllRestaurants/")
async def get_all_restaurants() -> list[dict]:
    """Fetch all restaurant names from the database.
 
    Returns:
        list[dict]: A list of restaurant names.
    """
    try:
        data, count = supabase.table(RESTAURANT_CONCEPT_TABLE).select("concept_name").execute()
        
        return data[1]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@app.post("/addRestaurantDynamic")
async def add_new_restuarant_location(restaurant_concept_name: str, google_maps_url:str) -> dict:
    """
    This is the endpoint for the google maps extension that takes in the restaurant name
    
    This is going to use the google maps api to create a new restaurant dynamic

    Hopefully we could also use some uber eats api or even the google maps api to add in the urls for the delivery apps
    """
    return {}


"""
0. Clean up your workspace / bring the things in the same repo

1.
Figure out some way to track / log what someone does via their chrome extension client side
Usecase: If someone messes up they can share what they messed up and we can delete it

2.
Figure out best practices with fastapi / apis in general
Should we be using phatttt apis? Should we be using db triggers? Should we do some data pipeline / data orchastration?

3.
Learn how to use python mux api, create a free account. 
Add either a trigger or to the add_dish_asset request something that uploads the video to mux and stores
The mux_asset_id and mux_playback_id in the dish_concept table
Note: Mux (mux.com) is the video hosting / upload processing provider that we use

4.
Add a part to the chrome extension for google maps when you are looking at a restaurant.
Should use google maps id.
Should somehow figure out the google maps placeid of the restaurant you are looking at
Should take in an existing restaurant_concept name as a form param
Create the restaurant_dynamic row for this

5.
Related to step four, figure out if there is a way to auto associate the uber eats url to the restaurant location.
Upload this when you are creating the restaurant_dynamic row in step 4.

https://realpython.com/fastapi-python-web-apis/
Misc:
Figure out how to best host with cicd the fast api application
"""