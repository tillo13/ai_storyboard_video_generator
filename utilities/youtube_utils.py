import httplib2
import os
import sys
import json
import random
import pytz
import time
from datetime import datetime, timedelta, timezone
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from oauth2client.client import flow_from_clientsecrets
from oauth2client.file import Storage
from oauth2client.tools import argparser, run_flow

# Constants and configurations
httplib2.RETRIES = 1
MAX_RETRIES = 10

RETRIABLE_EXCEPTIONS = (httplib2.HttpLib2Error, IOError, Exception)
RETRIABLE_STATUS_CODES = [500, 502, 503, 504]
QUOTA_EXCEEDED_STATUS_CODE = 403

CLIENT_SECRETS_FILE = "client_secrets.json"
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
    "https://www.googleapis.com/auth/youtube.upload"
]

YOUTUBE_API_SERVICE_NAME = "youtube"
YOUTUBE_API_VERSION = "v3"

MISSING_CLIENT_SECRETS_MESSAGE = """
WARNING: Please configure OAuth 2.0
To make this sample run you will need to populate the client_secrets.json file found at:
%s
with information from the API Console
https://console.cloud.google.com/
""" % os.path.abspath(os.path.join(os.path.dirname(__file__), CLIENT_SECRETS_FILE))

# Quota cost table
QUOTA_COSTS = {
    "activities.list": 1,
    "captions.list": 50,
    "captions.insert": 400,
    "captions.update": 450,
    "captions.delete": 50,
    "channelBanners.insert": 50,
    "channels.list": 1,
    "channels.update": 50,
    "channelSections.list": 1,
    "channelSections.insert": 50,
    "channelSections.update": 50,
    "channelSections.delete": 50,
    "comments.list": 1,
    "comments.insert": 50,
    "comments.update": 50,
    "comments.setModerationStatus": 50,
    "comments.delete": 50,
    "commentThreads.list": 1,
    "commentThreads.insert": 50,
    "commentThreads.update": 50,
    "guideCategories.list": 1,
    "i18nLanguages.list": 1,
    "i18nRegions.list": 1,
    "members.list": 1,
    "membershipsLevels.list": 1,
    "playlistItems.list": 1,
    "playlistItems.insert": 50,
    "playlistItems.update": 50,
    "playlistItems.delete": 50,
    "playlists.list": 1,
    "playlists.insert": 50,
    "playlists.update": 50,
    "playlists.delete": 50,
    "search.list": 100,
    "subscriptions.list": 1,
    "subscriptions.insert": 50,
    "subscriptions.delete": 50,
    "thumbnails.set": 50,
    "videoAbuseReportReasons.list": 1,
    "videoCategories.list": 1,
    "videos.list": 1,
    "videos.insert": 1600,
    "videos.update": 50,
    "videos.rate": 50,
    "videos.getRating": 1,
    "videos.reportAbuse": 50,
    "videos.delete": 50,
    "watermarks.set": 50,
    "watermarks.unset": 50
}

def calculate_estimated_cost(api_calls):
    total_cost = 0
    for call, count in api_calls.items():
        cost_per_call = QUOTA_COSTS.get(call, 1)  # Default to 1 if not found
        total_cost += cost_per_call * count
        print(f"API Call: {call}, Count: {count}, Cost per call: {cost_per_call}, Total cost: {cost_per_call * count}")
    print(f"Estimated total quota cost: {total_cost}")
    return total_cost

def get_authenticated_service(args):
    flow = flow_from_clientsecrets(CLIENT_SECRETS_FILE, scope=YOUTUBE_SCOPES, message=MISSING_CLIENT_SECRETS_MESSAGE)
    credential_storage_file = "{}-oauth2.json".format(os.path.splitext(sys.argv[0])[0])
    storage = Storage(credential_storage_file)
    credentials = storage.get()
    if credentials is None or credentials.invalid:
        credentials = run_flow(flow, storage, args)
    return build(YOUTUBE_API_SERVICE_NAME, YOUTUBE_API_VERSION, http=credentials.authorize(httplib2.Http()))

def check_quota(youtube):
    api_calls = {
        "channels.list": 1,  # Example call in quota check
    }

    try:
        request = youtube.channels().list(
            part="snippet,contentDetails,statistics",
            mine=True
        )
        response = request.execute()
        
        print("Quota check successful. Proceeding with video upload...")
        calculate_estimated_cost(api_calls)
        return True
    except HttpError as e:
        if e.resp.status == QUOTA_EXCEEDED_STATUS_CODE:
            error_response = json.loads(e.content)
            print(f"Quota exceeded. Not attempting the upload.\nFull Error Response: {json.dumps(error_response, indent=4)}")
            return False
        else:
            raise

def get_latest_scheduled_video_date(youtube):
    api_calls = {
        "search.list": 1,  # Example call for video scheduling
        "videos.list": 0,
    }

    request = youtube.search().list(
        part="id,snippet",
        forMine=True,
        type="video",
        order="date",
        maxResults=50
    )
    response = request.execute()
    api_calls["videos.list"] += len(response.get("items", []))  # Counting the video details calls

    scheduled_videos = []
    for item in response.get("items", []):
        video_id = item["id"]["videoId"]
        video_details = youtube.videos().list(part="status",id=video_id).execute()
        status = video_details["items"][0]["status"]
        if "publishAt" in status:
            publish_date = datetime.fromisoformat(status["publishAt"].replace('Z', '+00:00'))
            scheduled_videos.append((video_id, publish_date))

    calculate_estimated_cost(api_calls)

    if scheduled_videos:
        latest_scheduled_video = max(scheduled_videos, key=lambda x: x[1])
        print(f"Latest scheduled video ID: {latest_scheduled_video[0]}, Publish At: {latest_scheduled_video[1]}")
        return latest_scheduled_video[1]
    else:
        return None

def schedule_next_video_timezone(latest_publish_date):
    seattle_tz = pytz.timezone('America/Los_Angeles')
    if latest_publish_date:
        next_publish_time = latest_publish_date.astimezone(seattle_tz) + timedelta(days=1)
    else:
        now_utc = datetime.now(timezone.utc)
        next_publish_time = now_utc.astimezone(seattle_tz).replace(hour=8, minute=0, second=0, microsecond=0) + timedelta(days=1)
    
    next_publish_time_utc = next_publish_time.astimezone(pytz.utc)
    print(f"Scheduling next video to publish at: {next_publish_time_utc}")
    return next_publish_time, next_publish_time_utc.isoformat()

def initialize_upload(youtube, options):
    api_calls = {
        "videos.insert": 1,
    }

    tags = None
    if options.keywords:
        tags = options.keywords.split(",")

    latest_publish_date = get_latest_scheduled_video_date(youtube)
    next_publish_time, publishAt = schedule_next_video_timezone(latest_publish_date)

    body = dict(
        snippet=dict(
            title=options.title,
            description=options.description,
            tags=tags,
            categoryId=options.category
        ),
        status=dict(
            privacyStatus=options.privacyStatus,
            publishAt=publishAt
        )
    )
    
    print(f"Upload details: Title: {options.title}, Description: {options.description}, Keywords: {tags}, Category: {options.category}, Privacy Status: {options.privacyStatus}")

    insert_request = youtube.videos().insert(
        part=",".join(body.keys()),
        body=body,
        media_body=MediaFileUpload(options.file, chunksize=-1, resumable=True)
    )

    calculate_estimated_cost(api_calls)
    return resumable_upload(insert_request, next_publish_time, options.title)

def resumable_upload(insert_request, next_publish_time, title):
    response = None
    error = None
    retry = 0
    while response is None:
        try:
            print("Uploading file...")
            status, response = insert_request.next_chunk()
            if response is not None:
                if 'id' in response:
                    video_id = response['id']
                    video_url = f"https://www.youtube.com/watch?v={video_id}"
                    seattle_tz = pytz.timezone('America/Los_Angeles')
                    next_publish_time_pst = next_publish_time.astimezone(seattle_tz).strftime('%Y-%m-%d %I:%M %p %Z')
                    print(f"\nFinal Information:\nVideo '{title}' will be published at {next_publish_time_pst} PST with URL: {video_url}")
                    print(f"Full Response: {response}")
                    print(f"Response Details: {response}")
                else:
                    exit(f"The upload failed with an unexpected response: {response}")
        except HttpError as e:
            if e.resp.status in RETRIABLE_STATUS_CODES:
                error = f"A retriable HTTP error {e.resp.status} occurred:\n{e.content}"
            elif e.resp.status == QUOTA_EXCEEDED_STATUS_CODE:
                error_response = json.loads(e.content)
                print(f"Quota exceeded. Cannot proceed with the upload at this time. Please try again later.\nFull Error Response: {json.dumps(error_response, indent=4)}")
                sys.exit(1)  # Exit the script with a status code indicating an error.
            else:
                raise
        except RETRIABLE_EXCEPTIONS as e:
            error = f"A retriable error occurred: {e}"

        if error is not None:
            print(error)
            retry += 1
            if retry > MAX_RETRIES:
                exit("No longer attempting to retry.")
            max_sleep = 2 ** retry
            sleep_seconds = random.random() * max_sleep
            print(f"Sleeping {sleep_seconds} seconds and then retrying...")
            time.sleep(sleep_seconds)