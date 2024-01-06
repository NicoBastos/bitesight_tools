to run: uvicorn main:app --reload

Video Asset Management API

This API facilitates the management of video assets related to restaurant concepts, including uploading videos from local sources, Instagram, and integrating with external services like Mux for video processing and Supabase for data storage. The API is built using FastAPI, and it includes functionality for CORS handling, environment variable management, file handling, and integration with Instagram, Mux, and Supabase services.
Dependencies

    os: For interacting with the operating system.
    shutil: For high-level file operations.
    pathlib.Path: For filesystem paths.
    datetime: For working with dates and times.
    time: For time-related functions.
    dotenv: For loading environment variables from a .env file.
    fastapi: For building the API.
    fastapi.middleware.cors: For handling Cross-Origin Resource Sharing (CORS).
    requests: For making HTTP requests.
    supabase: For interacting with Supabase.
    instaloader: For downloading content from Instagram.
    models: For defining data models.
    mux_python: For interacting with the Mux API.

Environment Variables

    NICO_SUPABASE_URL: URL of the Supabase instance.
    NICO_API_KEY: API key for Supabase.
    MUX_TOKEN_ID: Mux token ID.
    MUX_TOKEN_SECRET: Mux token secret.

Endpoints
/ManualAddVideoAsset/

    Method: POST
    Description: Manually add a video asset.
    Form Parameters:
        dish_name: Name of the dish.
        restaurant_name: Name of the restaurant.
        file: Video file to upload.
        source: Source of the video.

/InstaAddVideoAsset/

    Method: POST
    Description: Add a video asset from an Instagram URL.
    Form Parameters:
        params: Instance of InstaAssetForm containing Instagram URL and other metadata.

/getAllRestaurants/

    Method: GET
    Description: Fetch all restaurant names from the database.

/addRestaurantDynamic

    Method: POST
    Description: Add a new restaurant location using Google Maps URL.

Functions
delete_file_and_siblings(file_path: Path | None)

Delete a file and its sibling files in its directory.
handle_instagram_download(post_url: str) -> Path | None

Download a video from an Instagram post URL.
getOrCreateRestaurant(concept_name: str) -> str

Get or create a restaurant concept in the database.
waitForMuxAsset(create_upload_response) -> str

Wait for a Mux asset to become ready and return its ID.
uploadToMux(video_path: Path) -> (str, str)

Upload a video file to Mux and return asset and playback IDs.
uploadSupabaseStorage(video_path: Path) -> str

Upload a video file to Supabase storage.
uploadFromLocal(video_path: Path | None, src_metadata: dict, restaurant_concept_id: str, dish_name: str) -> dict

Upload a video from the local filesystem to Mux and Supabase.
save_upload_file_tmp(upload_file: UploadFile, path: Path)

Save an uploaded file temporarily.
