import httplib2
import os
import sys
import json
import random
import csv
import time
import shutil
from datetime import datetime, timedelta, timezone
import pytz
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

# GLOBAL_VARIABLES
DAILY_POST_FREQUENCY_SCHEDULE = 3
MAXIMUM_UPLOADS_PER_RUN = 1
MAX_RETRIES = 10
RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
QUOTA_EXCEEDED_STATUS_CODE = 403

# Constants and configurations
CLIENT_SECRETS_FILE = "client_secrets.json"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
YOUTUBE_CHANNEL_ID = "your_channel_id"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.upload"
]
SEATTLE_TZ = pytz.timezone("America/Los_Angeles")

# Path to the client secrets file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_FILE_PATH = os.path.join(SCRIPT_DIR, CLIENT_SECRETS_FILE)
QUOTA_COSTS_FILE = os.path.join(SCRIPT_DIR, "quota_costs.json")
QUOTA_CSV_FILE = os.path.join(SCRIPT_DIR, "quota_usage_log.csv")

MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0
To run this example, you need to populate the client_secrets.json file found at:
%s
with information from the API Console:
https://console.cloud.google.com/
""" % CLIENT_SECRETS_FILE_PATH

def initialize_csv_file():
    if not os.path.exists(QUOTA_CSV_FILE):
        with open(QUOTA_CSV_FILE, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["timestamp", "api_name", "units", "status", "description"])

def load_quota_costs():
    with open(QUOTA_COSTS_FILE, 'r') as file:
        return json.load(file)
QUOTA_COSTS = load_quota_costs()

def log_quota_usage(api_name, units, status, description=""):
    with open(QUOTA_CSV_FILE, mode='a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([datetime.now().isoformat(), api_name, units, status, description])

def get_authenticated_service(args=None):
    flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE_PATH, scope=YOUTUBE_SCOPES + SCOPES, message=MISSING_CLIENT_SECRETS_MESSAGE)
    credential_storage_file = "{}-oauth2.json".format(os.path.splitext(sys.argv[0])[0])
    storage = Storage(credential_storage_file)
    credentials = storage.get()
    if credentials is None or credentials.invalid:
        credentials = run_flow(flow, storage, args if args else argparser.parse_args())
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, http=credentials.authorize(httplib2.Http()))

def calculate_estimated_cost(api_calls):
    total_cost = 0
    for call, count in api_calls.items():
        cost_per_call = QUOTA_COSTS.get(call, 1)  # Default to 1 if not found
        total_cost += cost_per_call * count
        log_quota_usage(call, cost_per_call * count, "Estimated", "Cost estimation")
    return total_cost

def initialize_upload(youtube, options, publish_at):
    tags = None
    if options.keywords:
        tags = [keyword.strip() for keyword in options.keywords.split(",")]

    body = dict(
        snippet=dict(
            title=options.title,
            description=options.description,
            tags=tags,
            categoryId=options.category
        ),
        status=dict(
            privacyStatus="private",  # Initially set privacyStatus as private
            publishAt=publish_at  # Set the scheduled publishing time
        )
    )

    api_calls = {"videos.insert": 1}
    calculate_estimated_cost(api_calls)

    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(options.file, chunksize=-1, resumable=True)
    )

    response = resumable_upload(insert_request)
    return response

def resumable_upload(insert_request):
    response = None
    error = None
    retry = 0

    while response is None:
        try:
            status, response = insert_request.next_chunk()
            
            if response is not None:
                if 'uploadStatus' in response['status'] and response['status']['uploadStatus'] == 'uploaded':
                    log_quota_usage("videos.insert", QUOTA_COSTS.get("videos.insert", 1600), "Success", "Video upload successful")

                    # Log a success message and return the response
                    print("Upload successful. Video ID: {}".format(response['id']))
                    return response
                else:
                    # Log details if uploadStatus is not as expected
                    print(f"Unexpected uploadStatus value: {response['status'].get('uploadStatus')}")
                    print("Full response for debugging:")
                    print(json.dumps(response, indent=4))
                    exit(f"The upload failed with an unexpected response: {response}")
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"A retriable HTTP error {e.resp.status} occurred:\n{e.content}"
                log_quota_usage("videos.insert", QUOTA_COSTS.get("videos.insert", 1600), "Retriable", f"HTTP Error: {e.resp.status}")
            elif e.resp.status == 400:
                print("HTTP 400 Error occurred.")
                print(e.content)
                log_quota_usage("videos.insert", QUOTA_COSTS.get("videos.insert", 1600), "Failed", "HTTP 400 Error")
                sys.exit(1)
            elif e.resp.status == QUOTA_EXCEEDED_STATUS_CODE:
                print("Quota exceeded.")
                print(e.content)
                log_quota_usage("videos.insert", QUOTA_COSTS.get("videos.insert", 1600), "Failed", "Quota exceeded")
                sys.exit(1)
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = f"A retriable error occurred: {e}"

        if error is not None:
            print(error)
            retry += 1
            if retry > MAX_RETRIES:
                log_quota_usage("videos.insert", QUOTA_COSTS.get("videos.insert", 1600), "Failed", "Max retries exceeded")
                exit("No longer attempting to retry.")
            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            time.sleep(sleep_seconds)

def convert_to_seattle_time(utc_date_str):
    utc_date = datetime.fromisoformat(utc_date_str.replace("Z", "+00:00")).astimezone(pytz.utc)
    seattle_time = utc_date.astimezone(SEATTLE_TZ)
    return seattle_time.isoformat()

def get_uploads_playlist_id(youtube):
    request = youtube.channels().list(
        part="contentDetails",
        id=YOUTUBE_CHANNEL_ID
    )
    response = request.execute()

    print("Channels Response:", json.dumps(response, indent=4))

    # Check if 'items' key exists
    if 'items' in response and len(response['items']) > 0:
        uploads_playlist_id = response['items'][0]['contentDetails']['relatedPlaylists']['uploads']
        return uploads_playlist_id
    else:
        raise KeyError("The response does not contain 'items' or it is empty. Please check the channel ID and permissions.")

def list_scheduled_videos(youtube):
    try:
        uploads_playlist_id = get_uploads_playlist_id(youtube)

        # Retrieve the list of videos in the uploads playlist
        request = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50
        )
        response = request.execute()

        #print("PlaylistItems Response:", json.dumps(response, indent=4))

        scheduled_videos = []
        for item in response.get("items", []):
            video_id = item["snippet"]["resourceId"]["videoId"]

            # Get the video details
            video_response = youtube.videos().list(
                part="status,snippet",
                id=video_id
            ).execute()

            #print("Video Response for {}: {}".format(video_id, json.dumps(video_response, indent=4)))

            for video in video_response.get("items", []):
                status = video["status"]
                snippet = video["snippet"]
                if "publishAt" in status:  # Checking if 'publishAt' is present
                    publish_time_seattle = convert_to_seattle_time(status["publishAt"])
                    video_info = {
                        "title": snippet["title"],
                        "scheduled_publish_time": publish_time_seattle
                    }
                    scheduled_videos.append(video_info)

        # Print scheduled videos
        if scheduled_videos:
            print("Scheduled Videos:")
            for video in scheduled_videos:
                print("Title: {}, Scheduled Publish Time (Seattle): {}".format(video["title"], video["scheduled_publish_time"]))
        else:
            print("No scheduled videos found.")

        return scheduled_videos

    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred: {e.content}")
    except KeyError as e:
        print(f"KeyError: {str(e)}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        return []

if __name__ == '__main__':
    argparser.add_argument("--file", required=True, help="Video file to upload")
    argparser.add_argument("--title", help="Video title", default="Test Title")
    argparser.add_argument("--description", help="Video description", default="Test Description")
    argparser.add_argument("--category", default="22", help="Numeric video category. See https://developers.google.com/youtube/v3/docs/videoCategories/list")
    argparser.add_argument("--keywords", help="Video keywords, comma separated", default="")
    argparser.add_argument("--privacyStatus", choices=("public", "private", "unlisted"), default="private", help="Video privacy status.")
    argparser.add_argument("--publishAt", help="Scheduled publish time (ISO 8601 format)")
    args = argparser.parse_args()

    if not os.path.exists(args.file):
        exit("Please specify a valid file using the --file= parameter.")

    youtube = get_authenticated_service(args)

    try:
        initialize_csv_file()

        # Calculate the next publish time if publishAt is not provided
        if not args.publishAt:
            seattle_tz = pytz.timezone('America/Los_Angeles')
            now_utc = datetime.now(timezone.utc)

            # Try to get the latest published video from your uploads playlist
            try:
                request = youtube.playlistItems().list(
                    part="snippet",
                    playlistId="YOUR_UPLOAD_PLAYLIST_ID",  # Replace with your actual playlist ID
                    maxResults=50
                )
                response = request.execute()
                latest_publish_date = None

                for item in response.get("items", []):
                    publish_date_str = item['snippet']['publishedAt']
                    publish_date = datetime.fromisoformat(publish_date_str.rstrip('Z'))
                    if not latest_publish_date or publish_date > latest_publish_date:
                        latest_publish_date = publish_date

                if latest_publish_date:
                    next_publish_time = latest_publish_date + timedelta(days=1)
                else:
                    next_publish_time = now_utc.astimezone(seattle_tz).replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)

            except Exception as e:
                print(f"Error fetching the latest published video: {str(e)}")
                next_publish_time = now_utc.astimezone(seattle_tz).replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)

            interval_hours = 24 / DAILY_POST_FREQUENCY_SCHEDULE
            publish_at = (next_publish_time + timedelta(hours=interval_hours)).astimezone(pytz.utc).isoformat()
        else:
            publish_at = args.publishAt

        response = initialize_upload(youtube, args, publish_at)
        print(json.dumps(response, indent=4))

        completed_dir = os.path.join(SCRIPT_DIR, "mosaics", "completed")
        if not os.path.exists(completed_dir):
            os.makedirs(completed_dir)

        shutil.move(args.file, completed_dir)
        print(f"Moved {args.file} to {completed_dir}")

        seattle_tz = pytz.timezone('America/Los_Angeles')
        next_publish_time = datetime.fromisoformat(publish_at.rstrip('Z')).astimezone(seattle_tz)
        print(f"The next video will be scheduled to post at: {next_publish_time.isoformat()} (Seattle time)")

        # Print the final line with scheduling details
        print(f"The latest video is set to post on {next_publish_time.strftime('%Y-%m-%d %H:%M:%S')} Seattle time. Based on your settings of: {DAILY_POST_FREQUENCY_SCHEDULE}, we deduced to post at {next_publish_time.isoformat()} Seattle time for this video.")

    except json.JSONDecodeError as e:
        print("Failed to decode JSON response from YouTube Scheduler.")
        print(f"Error Details: {str(e)}")
        print(e.doc)
        print(e.pos)
    except HttpError as e:
        if e.resp.status == QUOTA_EXCEEDED_STATUS_CODE:
            print(e.content)
            log_quota_usage("general", 0, "Failed", "Quota exceeded in main function")
        else:
            print(e.content)
            log_quota_usage("general", 0, "Failed", f"HTTP Error: {e.resp.status}")
    except Exception as e:
        print(f"Unexpected error: {str(e)}")
        sys.exit(1)