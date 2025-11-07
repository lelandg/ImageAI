"""Wikimedia Commons API client for searching and downloading images."""

import logging
import requests
from typing import List, Dict, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class WikimediaImage:
    """Represents a Wikimedia Commons image."""

    def __init__(self, title: str, url: str, thumb_url: Optional[str] = None,
                 description: Optional[str] = None, width: int = 0, height: int = 0,
                 upload_date: Optional[str] = None):
        self.title = title
        self.url = url
        self.thumb_url = thumb_url or url
        self.description = description or ""
        self.width = width
        self.height = height
        self.upload_date = upload_date or ""
        self.page_url = f"https://commons.wikimedia.org/wiki/{title}"

    def __repr__(self):
        return f"WikimediaImage(title={self.title}, url={self.url})"


class WikimediaClient:
    """Client for interacting with Wikimedia Commons API."""

    BASE_URL = "https://commons.wikimedia.org/w/api.php"
    USER_AGENT = "ImageAI/1.0 (https://github.com/yourusername/ImageAI)"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': self.USER_AGENT
        })

    def search_images(self, query: str, limit: int = 50) -> List[WikimediaImage]:
        """
        Search for images on Wikimedia Commons.

        Args:
            query: Search query string
            limit: Maximum number of results (default 50)

        Returns:
            List of WikimediaImage objects
        """
        logger.info(f"Searching Wikimedia Commons for: {query}")

        params = {
            'action': 'query',
            'format': 'json',
            'generator': 'search',
            'gsrsearch': query,
            'gsrnamespace': 6,  # File namespace
            'gsrlimit': min(limit, 50),  # API limit is 50
            'prop': 'imageinfo',
            'iiprop': 'url|size|extmetadata',
            'iiurlwidth': 300  # Thumbnail width
        }

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            images = []

            # Check if we got any results
            if 'query' not in data or 'pages' not in data['query']:
                logger.warning(f"No results found for query: {query}")
                return images

            pages = data['query']['pages']

            for page_id, page_data in pages.items():
                if 'imageinfo' not in page_data or not page_data['imageinfo']:
                    continue

                image_info = page_data['imageinfo'][0]
                title = page_data.get('title', '')

                # Get URLs
                url = image_info.get('url', '')
                thumb_url = image_info.get('thumburl', url)

                # Get dimensions
                width = image_info.get('width', 0)
                height = image_info.get('height', 0)

                # Get description and upload date from metadata
                description = ""
                upload_date = ""
                if 'extmetadata' in image_info:
                    metadata = image_info['extmetadata']
                    if 'ImageDescription' in metadata:
                        desc_data = metadata['ImageDescription']
                        if 'value' in desc_data:
                            description = desc_data['value']
                            # Strip HTML tags for display
                            import re
                            description = re.sub(r'<[^>]+>', '', description).strip()

                    # Extract upload date
                    if 'DateTime' in metadata:
                        date_data = metadata['DateTime']
                        if 'value' in date_data:
                            upload_date = date_data['value']

                image = WikimediaImage(
                    title=title,
                    url=url,
                    thumb_url=thumb_url,
                    description=description,
                    width=width,
                    height=height,
                    upload_date=upload_date
                )
                images.append(image)

            logger.info(f"Found {len(images)} images for query: {query}")
            return images

        except requests.exceptions.RequestException as e:
            logger.error(f"Error searching Wikimedia Commons: {e}")
            return []
        except Exception as e:
            logger.error(f"Unexpected error searching Wikimedia Commons: {e}")
            return []

    def download_image(self, image: WikimediaImage, output_path: Path) -> bool:
        """
        Download an image from Wikimedia Commons.

        Args:
            image: WikimediaImage object
            output_path: Path where to save the image

        Returns:
            True if successful, False otherwise
        """
        logger.info(f"Downloading image: {image.title} to {output_path}")

        try:
            response = self.session.get(image.url, timeout=30)
            response.raise_for_status()

            # Ensure parent directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write image data
            output_path.write_bytes(response.content)

            logger.info(f"Successfully downloaded: {image.title}")
            return True

        except requests.exceptions.RequestException as e:
            logger.error(f"Error downloading image {image.title}: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error downloading image {image.title}: {e}")
            return False

    def get_image_by_filename(self, filename: str) -> Optional[WikimediaImage]:
        """
        Get image info by exact filename.

        Args:
            filename: Exact filename (e.g., "File:Example.jpg")

        Returns:
            WikimediaImage object or None if not found
        """
        logger.info(f"Getting image info for: {filename}")

        # Ensure filename starts with "File:"
        if not filename.startswith("File:"):
            filename = f"File:{filename}"

        params = {
            'action': 'query',
            'format': 'json',
            'titles': filename,
            'prop': 'imageinfo',
            'iiprop': 'url|size|extmetadata',
            'iiurlwidth': 300
        }

        try:
            response = self.session.get(self.BASE_URL, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if 'query' not in data or 'pages' not in data['query']:
                return None

            pages = data['query']['pages']
            page = next(iter(pages.values()))

            if 'imageinfo' not in page or not page['imageinfo']:
                return None

            image_info = page['imageinfo'][0]
            title = page.get('title', '')
            url = image_info.get('url', '')
            thumb_url = image_info.get('thumburl', url)
            width = image_info.get('width', 0)
            height = image_info.get('height', 0)

            description = ""
            upload_date = ""
            if 'extmetadata' in image_info:
                metadata = image_info['extmetadata']
                if 'ImageDescription' in metadata:
                    desc_data = metadata['ImageDescription']
                    if 'value' in desc_data:
                        description = desc_data['value']
                        import re
                        description = re.sub(r'<[^>]+>', '', description).strip()

                # Extract upload date
                if 'DateTime' in metadata:
                    date_data = metadata['DateTime']
                    if 'value' in date_data:
                        upload_date = date_data['value']

            return WikimediaImage(
                title=title,
                url=url,
                thumb_url=thumb_url,
                description=description,
                width=width,
                height=height,
                upload_date=upload_date
            )

        except Exception as e:
            logger.error(f"Error getting image info for {filename}: {e}")
            return None
