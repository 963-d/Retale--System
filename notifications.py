import os
from googleapiclient.discovery import build
from datetime import datetime, timedelta

class NotificationManager:
    def __init__(self):
        self.youtube = build('youtube', 'v3', developerKey=os.getenv('YOUTUBE_API_KEY'))
        self.last_check = datetime.now()

    async def check_youtube_updates(self, channel_id):
        try:
            request = self.youtube.activities().list(
                part="snippet,contentDetails",
                channelId=channel_id,
                maxResults=5
            )
            response = request.execute()
            
            new_videos = []
            for item in response['items']:
                if item['snippet']['type'] == 'upload':
                    published_at = datetime.strptime(
                        item['snippet']['publishedAt'],
                        '%Y-%m-%dT%H:%M:%SZ'
                    )
                    if published_at > self.last_check:
                        new_videos.append({
                            'title': item['snippet']['title'],
                            'url': f"https://youtube.com/watch?v={item['contentDetails']['upload']['videoId']}",
                            'thumbnail': item['snippet']['thumbnails']['default']['url']
                        })
            return new_videos
        except Exception as e:
            print(f"خطأ في فحص تحديثات يوتيوب: {e}")
            return []

    def update_last_check(self):
        self.last_check = datetime.now() 