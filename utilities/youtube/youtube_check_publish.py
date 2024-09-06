import httplib2
import os
import sys
import json
from datetime import datetime
import pytz
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow
from oauth2client.client import flow_from_clientsecrets

# Constants
CLIENT_SECRETS_FILE = "client_secrets.json"
YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"
YOUTUBE_CHANNEL_ID ="your_channel_id"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly"]
SEATTLE_TZ = pytz.timezone("America/Los_Angeles")

# Path to the client secrets file
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
CLIENT_SECRETS_FILE_PATH = os.path.join(SCRIPT_DIR, CLIENT_SECRETS_FILE)

# Message to display if client secrets file is missing
MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0
To run this example, you need to populate the client_secrets.json file found at:
%s
with information from the API Console:
https://console.cloud.google.com/
""" % CLIENT_SECRETS_FILE_PATH

# Authenticate and build the YouTube API client
def get_authenticated_service():
    flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE, scope=SCOPES, message=MISSING_CLIENT_SECRETS_MESSAGE)
    storage = Storage("%s-oauth2.json" % sys.argv[0])
    credentials = storage.get()
    if credentials is None or credentials.invalid:
        credentials = run_flow(flow, storage, argparser.parse_args())
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, credentials=credentials)

# Convert UTC date to Seattle timezone
def convert_to_seattle_time(utc_date_str):
    utc_date = datetime.fromisoformat(utc_date_str.replace("Z", "+00:00")).astimezone(pytz.utc)
    seattle_time = utc_date.astimezone(SEATTLE_TZ)
    return seattle_time.isoformat()

# Get the uploads playlist ID
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

# List scheduled videos
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
        
        print("PlaylistItems Response:", json.dumps(response, indent=4))

        scheduled_videos = []
        for item in response.get("items", []):
            video_id = item["snippet"]["resourceId"]["videoId"]

            # Get the video details
            video_response = youtube.videos().list(
                part="status,snippet",
                id=video_id
            ).execute()

            print("Video Response for {}: {}".format(video_id, json.dumps(video_response, indent=4)))

            for video in video_response.get("items", []):
                status = video["status"]
                snippet = video["snippet"]
                if status["privacyStatus"] == "private" and "publishAt" in status:
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

    except HttpError as e:
        print(f"An HTTP error {e.resp.status} occurred: {e.content}")
    except KeyError as e:
        print(f"KeyError: {str(e)}")
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")

if __name__ == '__main__':
    youtube = get_authenticated_service()
    list_scheduled_videos(youtube)