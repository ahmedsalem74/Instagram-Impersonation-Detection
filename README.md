# Instagram Impersonation Detection

A modular open-source investigation toolkit designed to identify potential Instagram impersonation accounts. This tool discovers Instagram profiles that match a person's name, collects public metadata via the Meta Graph API, downloads their profile photos, and compares photos to a reference image to detect identical or visually similar profiles.

---

## Key Features

1. Automatic Account Discovery

   * Finds Instagram profiles matching a person's name using Google Custom Search.

2. Metadata Enrichment

   * Retrieves follower counts, bios, post counts, and account details via Meta Graph API.

3. Local Evidence Storage

   * Saves structured CSVs, URL lists, and profile images per investigated name.

4. Advanced Image Matching

   * Compares reference photos to profile pictures using multiple matching techniques:

     * Exact Matching: SHA-256 hashes and pixel-level comparison.
     * Perceptual Hashing: phash, dhash, ahash for near-duplicate detection.
     * Feature Matching: ORB algorithm for robust similarity detection.

5. Safe Re-runs

   * Detects existing data and asks whether to overwrite or reuse previous results.

---

## Prerequisites

* Python 3.7 or higher
* Instagram Business or Creator Account (for Meta Graph API access)
* Google Custom Search Engine API credentials
* Facebook Developer Account with Instagram Basic Display access

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/Instagram-Impersonation-Detection.git
cd Instagram-Impersonation-Detection
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

Or manually:

```bash
pip install requests pandas rapidfuzz pillow imagehash tqdm opencv-python numpy
```

---

## API Setup

### Google Custom Search API

1. Go to Google Cloud Console
2. Create a new project or select an existing one
3. Enable the Custom Search API
4. Create credentials (API Key)
5. Set up a Custom Search Engine at Google CSE
6. Note your Search Engine ID (CX)

### Meta Graph API Setup

1. Go to Facebook Developers
2. Create a new app with "Business" type
3. Add Instagram Basic Display product
4. Configure Valid OAuth Redirect URIs
5. Generate a short-lived User Access Token (the script exchanges it for a long-lived token)

---

## Configuration

Edit the configuration section in `instagram_pipeline.py`:

```python
# API Configuration
GOOGLE_API_KEY = "your_google_api_key_here"
GOOGLE_CX = "your_custom_search_engine_id"
FB_APP_ID = "your_facebook_app_id"
FB_APP_SECRET = "your_facebook_app_secret"
FB_SHORT_TOKEN = "your_facebook_short_lived_token"
IG_USER_ID = "your_instagram_business_account_id"

# Application Settings
GRAPH_VERSION = "v24.0"
MAIN_FOLDER = "Investigation_Results"
```

---

## Usage

### Basic Usage

```bash
python instagram_pipeline.py
```

The script will guide you through:

* Entering the person's name to investigate
* Automatic Instagram profile discovery
* Metadata collection via Graph API
* Profile picture downloads
* Optional image comparison with a target photo

### Advanced Image Matching Options

```python
# Key settings in find_image_match.py
HASH_SIZE = 16
SIMILARITY_THRESHOLD = 12
USE_ORB_FALLBACK = True
ORB_GOOD_MATCHES_MIN = 28
```

### Custom Search Queries

Modify the `build_query()` function to customize search patterns:

```python
def build_query(name: str):
    return (
        f'site:instagram.com "{name}" '
        f'-inurl:reel -inurl:reels -inurl:p/ -inurl:stories '
        f'-inurl:explore -inurl:accounts -inurl:tags -inurl:tv'
    )
```

---

## Output Structure

```
Investigation_Results/
└── Person_Name/
    ├── Person_Name.csv              # Complete account metadata
    ├── profile_urls.txt             # List of profile picture URLs
    └── Images/
        ├── username1.jpg
        ├── username2.png
        └── ...
```

### CSV Output Columns

* Instagram Account Name
* Username
* Profile URL
* Number of Posts
* Number of Followers
* Number of Following
* Bio/Description Text
* Profile Picture URL

---

## Troubleshooting

* **API Rate Limits:** Implement delays between requests (Google CSE: 100 queries/day free, Meta Graph API: ~200 requests/hour)
* **Token Expiration:** Regenerate short-lived token and update configuration
* **No Results Found:** Check CSE configuration and name formatting
* **Image Matching False Positives:** Adjust similarity thresholds and use ORB feature matching

---

## Performance Notes

* Search Time: 2-5 minutes per investigation
* Image Processing: ~1 second per image comparison
* Storage: ~50-200MB per investigated person
* API Costs: Free tiers available, monitor usage for large-scale investigations

---

## Privacy & Compliance

* Only processes publicly available information
* Stores data locally on investigator's machine
* No personal data transmitted to third parties (besides required APIs)
* Use in compliance with platform Terms of Service
* Respect privacy laws and regulations
* Intended for legitimate investigation purposes only

---

## License

This project is licensed under the MIT License — see the LICENSE file for details.

---

## Acknowledgments

* Google Custom Search API for profile discovery
* Meta Graph API for Instagram data access
* OpenCV and PIL for image processing
* RapidFuzz for fuzzy string matching

---

**Disclaimer:** This tool is intended for legitimate investigative purposes, brand protection, and academic research. Users are responsible for complying with all applicable laws and platform terms of service.
