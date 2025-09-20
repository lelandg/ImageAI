#!/usr/bin/env python3
"""
Download social media platform icons for ImageAI.
Icons are sourced from official brand resources or CDNs.
"""

import os
import requests
from pathlib import Path
import time

# Create icons directory
icons_dir = Path("assets/icons/social")
icons_dir.mkdir(parents=True, exist_ok=True)

# Define platform icons with their download URLs
# Using Simple Icons CDN (https://simpleicons.org) for consistent SVG icons
# and some direct brand resources where available
PLATFORM_ICONS = {
    "apple-podcasts": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/applepodcasts.svg",
    "bandcamp": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/bandcamp.svg",
    "cd-baby": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/musicbrainz.svg",  # Using music note as placeholder
    "discord": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/discord.svg",
    "facebook": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/facebook.svg",
    "instagram": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/instagram.svg",
    "linkedin": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/linkedin.svg",
    "mastodon": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/mastodon.svg",
    "pinterest": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/pinterest.svg",
    "reddit": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/reddit.svg",
    "snapchat": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/snapchat.svg",
    "soundcloud": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/soundcloud.svg",
    "spotify": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/spotify.svg",
    "threads": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/threads.svg",
    "tiktok": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/tiktok.svg",
    "tumblr": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/tumblr.svg",
    "twitch": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/twitch.svg",
    "twitter": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/twitter.svg",
    "x": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/x.svg",
    "youtube": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/youtube.svg",
    "vimeo": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/vimeo.svg",
    "whatsapp": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/whatsapp.svg",
    "telegram": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/telegram.svg",
    "slack": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/slack.svg",
    "dribbble": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/dribbble.svg",
    "behance": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/behance.svg",
    "github": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/github.svg",
    "medium": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/medium.svg",
    "patreon": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/patreon.svg",
    "etsy": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/etsy.svg",
    "shopify": "https://cdn.jsdelivr.net/npm/simple-icons@v10/icons/shopify.svg",
}

# Additional PNG fallback icons (higher quality branded icons)
PNG_ICONS = {
    "apple-podcasts": "https://www.apple.com/v/apple-podcasts/b/images/overview/hero_icon__c135x5gz14mu_large.png",
    "discord": "https://assets-global.website-files.com/6257adef93867e50d84d30e2/636e0a6a49cf127bf92de1e2_icon_clyde_blurple_RGB.png",
    "facebook": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/05/Facebook_Logo_%282019%29.png/1200px-Facebook_Logo_%282019%29.png",
    "instagram": "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a5/Instagram_icon.png/2048px-Instagram_icon.png",
    "linkedin": "https://upload.wikimedia.org/wikipedia/commons/thumb/c/ca/LinkedIn_logo_initials.png/800px-LinkedIn_logo_initials.png",
    "pinterest": "https://upload.wikimedia.org/wikipedia/commons/0/08/Pinterest-logo.png",
    "reddit": "https://www.redditstatic.com/brand-assets/reddit-logo-png/reddit-mark-circle-orange-on-white.png",
    "spotify": "https://storage.googleapis.com/pr-newsroom-wp/1/2018/11/Spotify_Logo_RGB_Green.png",
    "tiktok": "https://sf-tb-sg.ibytedtos.com/obj/eden-sg/uhtyvueh7nulogpoguhm/tiktok-icon2.png",
    "twitter": "https://abs.twimg.com/icons/apple-touch-icon-192x192.png",
    "x": "https://abs.twimg.com/icons/apple-touch-icon-192x192.png",
    "youtube": "https://www.youtube.com/s/desktop/5e2b5d5c/img/favicon_144x144.png",
}

def download_icon(platform: str, url: str, file_type: str = "svg") -> bool:
    """Download a single icon."""
    try:
        print(f"Downloading {platform} icon...")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        # Save the icon
        file_path = icons_dir / f"{platform}.{file_type}"

        if file_type == "svg":
            # For SVG files, save as text
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(response.text)
        else:
            # For PNG/other binary files
            with open(file_path, 'wb') as f:
                f.write(response.content)

        print(f"  ✓ Saved {platform}.{file_type}")
        return True

    except requests.exceptions.RequestException as e:
        print(f"  ✗ Failed to download {platform}: {e}")
        return False
    except Exception as e:
        print(f"  ✗ Error saving {platform}: {e}")
        return False

def main():
    """Download all platform icons."""
    print("="*60)
    print("Social Media Icon Downloader for ImageAI")
    print("="*60)
    print(f"\nDownloading icons to: {icons_dir.absolute()}\n")

    success_count = 0
    failed = []

    # First try SVG icons (scalable, preferred)
    print("Downloading SVG icons...")
    print("-"*40)

    for platform, url in PLATFORM_ICONS.items():
        if download_icon(platform, url, "svg"):
            success_count += 1
        else:
            failed.append(platform)
        time.sleep(0.1)  # Be nice to the CDN

    # Try PNG fallbacks for failed downloads
    if failed:
        print("\n" + "-"*40)
        print("Attempting PNG fallbacks for failed downloads...")
        print("-"*40)

        retry_list = failed.copy()
        for platform in retry_list:
            if platform in PNG_ICONS:
                if download_icon(platform, PNG_ICONS[platform], "png"):
                    success_count += 1
                    failed.remove(platform)
                time.sleep(0.1)

    # Summary
    print("\n" + "="*60)
    print(f"Download complete!")
    print(f"  Successfully downloaded: {success_count}/{len(PLATFORM_ICONS)} icons")

    if failed:
        print(f"  Failed downloads: {', '.join(failed)}")
        print("\n  For failed icons, you may need to:")
        print("  1. Download manually from the platform's brand resources")
        print("  2. Use a generic placeholder icon")
        print("  3. Create a simple text-based icon")

    # Create a placeholder icon for any missing platforms
    if failed:
        print("\nCreating placeholder icons for missing platforms...")
        create_placeholder_svg(failed)

    print("\nDone!")

def create_placeholder_svg(platforms: list):
    """Create simple SVG placeholder icons for missing platforms."""
    for platform in platforms:
        # Simple circle with first letter
        first_letter = platform[0].upper()
        svg_content = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">
  <circle cx="12" cy="12" r="10" fill="#888888"/>
  <text x="12" y="16" text-anchor="middle" fill="white" font-family="Arial" font-size="12" font-weight="bold">{first_letter}</text>
</svg>'''

        file_path = icons_dir / f"{platform}.svg"
        with open(file_path, 'w') as f:
            f.write(svg_content)
        print(f"  ✓ Created placeholder for {platform}")

if __name__ == "__main__":
    main()