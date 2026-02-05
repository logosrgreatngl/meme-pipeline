#!/usr/bin/env python3
"""
Reddit Meme Scraper to Google Drive (No API Required)
Scrapes popular and new memes from Reddit using web scraping and uploads them to Google Drive
"""

import requests
import os
import json
from dotenv import load_dotenv
import re
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import pickle
import time


class RedditMemeScraper:
    def __init__(self, config_file='config_no_api.json'):
        """Initialize the scraper with Google Drive credentials only"""
        # Load environment variables
        load_dotenv()
        
        self.config = self.load_config(config_file)
        self.drive_service = self.setup_google_drive()
        self.download_folder = self.config.get('download_folder', 'memes')
        self.history_file = 'downloaded_history.json'
        
        # Create download folder if it doesn't exist
        if not os.path.exists(self.download_folder):
            os.makedirs(self.download_folder)
        
        # Load download history
        self.downloaded_ids = self.load_history()
        
        # Create a session for better connection handling
        self.session = requests.Session()
        
        # Set up headers to mimic a browser - more realistic
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Referer': 'https://www.reddit.com/',
            'Sec-Fetch-Dest': 'image',
            'Sec-Fetch-Mode': 'no-cors',
            'Sec-Fetch-Site': 'same-site',
            'DNT': '1'
        }
        self.session.headers.update(self.headers)
    
    def load_history(self):
        """Load history of downloaded post IDs"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, 'r') as f:
                    return set(json.load(f))
            except:
                return set()
        return set()
    
    def save_history(self):
        """Save history of downloaded post IDs"""
        try:
            with open(self.history_file, 'w') as f:
                json.dump(list(self.downloaded_ids), f)
        except Exception as e:
            print(f"Warning: Could not save history: {e}")
    
    def load_config(self, config_file):
        """Load configuration from JSON file"""
        with open(config_file, 'r') as f:
            return json.load(f)
    
    def setup_google_drive(self):
        """Setup Google Drive API connection"""
        SCOPES = ['https://www.googleapis.com/auth/drive.file']
        creds = None
        
        # Token file stores the user's access and refresh tokens
        if os.path.exists('token.pickle'):
            with open('token.pickle', 'rb') as token:
                creds = pickle.load(token)
        
        # If there are no valid credentials, let the user log in
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.config['google_drive']['credentials_file'], SCOPES)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            with open('token.pickle', 'wb') as token:
                pickle.dump(creds, token)
        
        service = build('drive', 'v3', credentials=creds)
        return service
    
    def get_or_create_folder(self, folder_name):
        """Get or create a folder in Google Drive"""
        # Search for the folder
        query = f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
        results = self.drive_service.files().list(q=query, fields="files(id, name)").execute()
        items = results.get('files', [])
        
        if items:
            return items[0]['id']
        else:
            # Create the folder
            file_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder'
            }
            folder = self.drive_service.files().create(body=file_metadata, fields='id').execute()
            return folder.get('id')
    
    def download_image(self, url, filename):
        """Download image from URL with retry logic"""
        max_retries = 2
        
        for attempt in range(max_retries):
            try:
                # Decode HTML entities in URL (fix &amp; issues)
                import html
                url = html.unescape(url)
                
                # Special handling for Reddit images - use session for better connection
                response = self.session.get(url, timeout=20, allow_redirects=True)
                response.raise_for_status()
                
                # Check if we got valid image data by size and content
                if len(response.content) < 100:  # Too small to be a real image
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    print(f"  ✗ File too small")
                    return None
                
                # Check if response looks like HTML (Reddit blocking us)
                if response.content[:15].lower().startswith(b'<!doctype html') or response.content[:6].lower().startswith(b'<html'):
                    if attempt < max_retries - 1:
                        time.sleep(2)
                        continue
                    print(f"  ✗ Got HTML instead of image (blocked)")
                    return None
                
                filepath = os.path.join(self.download_folder, filename)
                with open(filepath, 'wb') as f:
                    f.write(response.content)
                
                # Verify the file was written correctly
                if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
                    return filepath
                else:
                    if attempt < max_retries - 1:
                        time.sleep(1)
                        continue
                    print(f"  ✗ File write failed")
                    return None
                    
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    time.sleep(2)
                    continue
                print(f"  ✗ Timeout")
                return None
            except Exception as e:
                if attempt < max_retries - 1:
                    time.sleep(1)
                    continue
                print(f"  ✗ Error: {str(e)[:30]}")
                return None
        
        return None
    
    def upload_to_drive(self, filepath, folder_id):
        """Upload file to Google Drive"""
        try:
            file_metadata = {
                'name': os.path.basename(filepath),
                'parents': [folder_id]
            }
            
            media = MediaFileUpload(filepath, resumable=True)
            file = self.drive_service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id, webViewLink'
            ).execute()
            
            print(f"✓ Uploaded: {os.path.basename(filepath)}")
            return file.get('webViewLink')
        except Exception as e:
            print(f"Error uploading {filepath}: {e}")
            return None
    
    def get_reddit_json(self, subreddit, sort_by='hot', limit=25):
        """
        Fetch Reddit posts using Reddit's JSON API (no authentication needed)
        
        Args:
            subreddit: Name of the subreddit
            sort_by: 'hot', 'new', 'top', or 'rising'
            limit: Number of posts to fetch (max 100)
        """
        # Reddit's public JSON endpoint
        url = f'https://www.reddit.com/r/{subreddit}/{sort_by}.json?limit={limit}'
        
        # For 'top', get posts from today
        if sort_by == 'top':
            time_filter = self.config.get('time_filter', 'day')
            url += f'&t={time_filter}'  # day, week, month, year, all
        
        # Retry logic
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                # Use different headers for JSON endpoint
                json_headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json'
                }
                response = self.session.get(url, headers=json_headers, timeout=20)
                response.raise_for_status()
                
                data = response.json()
                posts = data['data']['children']
                
                return posts
                
            except requests.exceptions.Timeout:
                if attempt < max_retries - 1:
                    print(f"  ⏳ Timeout, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"  ✗ Failed to fetch r/{subreddit} after {max_retries} attempts (timeout)")
                    return []
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"  ⏳ Error, retrying in {retry_delay}s... (attempt {attempt + 1}/{max_retries})")
                    time.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    print(f"  ✗ Error fetching r/{subreddit}: {str(e)[:80]}")
                    return []
        
        return []
    
    def is_image_url(self, url):
        """Check if URL is a direct image link"""
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        return any(url.lower().endswith(ext) for ext in image_extensions)
    
    def extract_image_url(self, post_data):
        """Extract image URL from Reddit post data"""
        import html
        post = post_data['data']
        
        # Check if it's a direct image link
        if self.is_image_url(post.get('url', '')):
            return html.unescape(post['url'])
        
        # Check if it's a Reddit gallery
        if 'gallery_data' in post:
            # Get first image from gallery
            if 'media_metadata' in post:
                for media_id, media in post['media_metadata'].items():
                    if media['e'] == 'Image':
                        # Get the highest quality image
                        if 's' in media and 'u' in media['s']:
                            return html.unescape(media['s']['u'])
        
        # Check preview images
        if 'preview' in post:
            try:
                images = post['preview']['images']
                if images:
                    source = images[0]['source']
                    return html.unescape(source['url'])
            except (KeyError, IndexError):
                pass
        
        return None
    
    def scrape_subreddit(self, subreddit_name, sort_by='hot', limit=25):
        """
        Scrape memes from a subreddit
        
        Args:
            subreddit_name: Name of the subreddit
            sort_by: 'hot', 'new', 'top', or 'rising'
            limit: Number of posts to fetch
        """
        print(f"\n📥 Scraping r/{subreddit_name} ({sort_by})...")
        
        posts = self.get_reddit_json(subreddit_name, sort_by, limit)
        
        if not posts:
            print(f"  ⚠️ No posts found for r/{subreddit_name}")
            return []
        
        downloaded_files = []
        skipped = 0
        already_downloaded = 0
        low_engagement = 0
        
        for post_data in posts:
            try:
                post = post_data['data']
                post_id = post['id']
                
                # Skip if already downloaded
                if post_id in self.downloaded_ids:
                    already_downloaded += 1
                    continue
                
                # Get post metrics
                upvotes = post.get('ups', 0)
                num_comments = post.get('num_comments', 0)
                post_age_hours = (time.time() - post.get('created_utc', 0)) / 3600
                
                # Calculate engagement score
                if post_age_hours > 0:
                    engagement_score = (upvotes + num_comments * 2) / max(post_age_hours, 1)
                else:
                    engagement_score = 0
                
                # Filter by minimum upvotes
                min_upvotes = self.config.get('min_upvotes', 50)
                if upvotes < min_upvotes:
                    low_engagement += 1
                    continue
                
                # Optional: Filter by max age (if specified in config)
                max_age = self.config.get('max_post_age_hours', None)
                if max_age and post_age_hours > max_age:
                    skipped += 1
                    continue
                
                # Extract image URL
                image_url = self.extract_image_url(post_data)
                
                if not image_url:
                    skipped += 1
                    continue
                
                # Create filename
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                
                # Determine extension from URL
                if '.jpg' in image_url.lower() or '.jpeg' in image_url.lower():
                    extension = '.jpg'
                elif '.png' in image_url.lower():
                    extension = '.png'
                elif '.gif' in image_url.lower():
                    extension = '.gif'
                elif '.webp' in image_url.lower():
                    extension = '.webp'
                else:
                    extension = '.jpg'  # default
                
                # Clean filename
                filename = f"{subreddit_name}_{post_id}_{timestamp}{extension}"
                
                # Download image
                filepath = self.download_image(image_url, filename)
                if filepath:
                    downloaded_files.append({
                        'filepath': filepath,
                        'title': post['title'],
                        'url': image_url,
                        'post_id': post_id,
                        'upvotes': upvotes,
                        'engagement_score': engagement_score,
                        'age_hours': post_age_hours
                    })
                    # Mark as downloaded
                    self.downloaded_ids.add(post_id)
                    age_str = f"{post_age_hours:.1f}h ago" if post_age_hours < 24 else f"{post_age_hours/24:.1f}d ago"
                    print(f"  ✓ {post['title'][:50]}... (↑{upvotes}, 💬{num_comments}, 🕐{age_str})")
                
                # Be respectful with requests
                time.sleep(1.0)
                
            except Exception as e:
                print(f"  ✗ Error processing post: {e}")
                skipped += 1
                continue
        
        stats_msg = f"  📊 Downloaded: {len(downloaded_files)}, Skipped: {skipped}"
        if already_downloaded > 0:
            stats_msg += f", Already had: {already_downloaded}"
        if low_engagement > 0:
            stats_msg += f", Low engagement: {low_engagement}"
        print(stats_msg)
        
        # Sort by engagement score (best first)
        downloaded_files.sort(key=lambda x: x['engagement_score'], reverse=True)
        
        return downloaded_files
    
    def run(self):
        """Main execution function"""
        print("🚀 Starting Reddit Meme Scraper (No API)")
        print("=" * 50)
        
        # Get Google Drive folder
        drive_folder_name = self.config.get('drive_folder_name', 'Reddit Memes')
        folder_id = self.get_or_create_folder(drive_folder_name)
        print(f"📁 Google Drive folder: {drive_folder_name}")
        
        # Get subreddits from config
        subreddits = self.config.get('subreddits', ['memes', 'dankmemes'])
        sort_by = self.config.get('sort_by', 'hot')
        limit = self.config.get('limit', 25)
        
        all_files = []
        
        # Scrape each subreddit
        for subreddit in subreddits:
            try:
                files = self.scrape_subreddit(subreddit, sort_by, limit)
                all_files.extend(files)
                
                # Wait between subreddits to be respectful
                time.sleep(2)
            except KeyboardInterrupt:
                print("\n⚠️ Interrupted by user. Uploading downloaded memes...")
                break
            except Exception as e:
                print(f"\n⚠️ Error scraping r/{subreddit}: {e}")
                print("Continuing with next subreddit...")
                continue
        
        if not all_files:
            print("\n⚠️ No memes downloaded. Exiting.")
            return
        
        print(f"\n📤 Uploading {len(all_files)} memes to Google Drive...")
        
        # Upload to Google Drive
        uploaded_count = 0
        failed_uploads = 0
        
        for file_info in all_files:
            try:
                link = self.upload_to_drive(file_info['filepath'], folder_id)
                if link:
                    uploaded_count += 1
                else:
                    failed_uploads += 1
            except Exception as e:
                print(f"  ✗ Upload failed: {os.path.basename(file_info['filepath'])}")
                failed_uploads += 1
        
        # Cleanup - delete local files
        if self.config.get('delete_after_upload', True):
            print("\n🧹 Cleaning up local files...")
            for file_info in all_files:
                try:
                    os.remove(file_info['filepath'])
                except Exception as e:
                    print(f"Error deleting {file_info['filepath']}: {e}")
        
        # Save download history
        self.save_history()
        
        print("\n" + "=" * 50)
        print(f"✅ Done! Uploaded {uploaded_count}/{len(all_files)} memes")
        if failed_uploads > 0:
            print(f"⚠️ Failed uploads: {failed_uploads}")
        print(f"📝 Total unique memes tracked: {len(self.downloaded_ids)}")
        print("=" * 50)


if __name__ == '__main__':
    scraper = RedditMemeScraper()
    scraper.run()