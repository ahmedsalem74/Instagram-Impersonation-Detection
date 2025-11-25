import os
import re
import time
import math
import html
import csv
import requests
import pandas as pd
from rapidfuzz import fuzz
from tqdm import tqdm

# -------------------------
# CONFIGURATION (YOUR KEYS)
# -------------------------
GOOGLE_API_KEY = "AIzaSyCZ2y2xOHFRYVrwaG4naaKCR1SeYnE2B8Y"
GOOGLE_CX      = "d7551ed3e0625445f"
CSE_URL        = "https://www.googleapis.com/customsearch/v1"

FB_APP_ID      = "664783820036054"
FB_APP_SECRET  = "012d6fd2ae5ea4a53ce268071e3fcbe6"
FB_SHORT_TOKEN = "EAAJcngtyF9YBPtJ57tsbE2tLvW0RKJzZCuP5EAp8aIfALMcD2gk9a6ZB806LPZBZC6CE4ZBFgZArXneo4HXI9kW9XgZBaLbkRilCBip5y453ZAJoabHbL838wo5HlcuQarhXXeDaZCwKG4bavp4mxKm0o8CFiK4Eehar6yL8MN8eX29oCII5Q5Lmt0JZB9FJqZCadRsMAZDZD"
IG_USER_ID     = "17841402943094780"

GRAPH_VERSION  = "v24.0"
MAIN_FOLDER    = "Main_Folder"

BAD_SEGMENTS = {"p", "reel", "reels", "stories", "explore", "accounts", "tags", "tv"}

# -------------------------
# UTILITIES
# -------------------------
def ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def clean_path(p: str) -> str:
    """Remove quotes and normalize Windows/Unix paths."""
    if not p:
        return ""
    p = p.strip().strip('\'"')
    p = os.path.expandvars(os.path.expanduser(p))
    return os.path.normpath(p)

def folder_has_existing_csv(base_dir: str) -> bool:
    """True if <base_dir>/<name>.csv exists."""
    name = os.path.basename(base_dir)
    csv_path = os.path.join(base_dir, f"{name}.csv")
    return os.path.isfile(csv_path)

def get_username(url: str):
    m = re.search(r"instagram\.com/([^/?#]+)/?", url)
    if not m:
        return None
    seg = m.group(1)
    return None if seg in BAD_SEGMENTS else seg

def build_query(name: str):
    return (
        f'site:instagram.com "{name}" '
        f'-inurl:reel -inurl:reels -inurl:p/ -inurl:stories '
        f'-inurl:explore -inurl:accounts -inurl:tags -inurl:tv'
    )

def extract_display_name(title: str):
    if not title:
        return ""
    title = html.unescape(title)
    m = re.match(r"^\s*([^()]+?)\s*\(@[A-Za-z0-9._]+?\)", title)
    if m:
        return m.group(1).strip()
    return title.split("•")[0].strip()

def username_to_readable(u: str):
    return re.sub(r"[_\.]+", " ", u).strip()

def fuzzy_score(a: str, b: str):
    return fuzz.token_set_ratio(a, b)

def cse_search(query: str, max_results: int = 30):
    results = []
    start = 1
    pages = math.ceil(max_results / 10)
    for _ in range(pages):
        params = {
            "key": GOOGLE_API_KEY,
            "cx": GOOGLE_CX,
            "q": query,
            "num": min(10, max_results - len(results)),
            "start": start,
        }
        r = requests.get(CSE_URL, params=params, timeout=15)
        if r.status_code != 200:
            raise Exception(f"CSE error: {r.text}")
        data = r.json()
        items = data.get("items", [])
        results.extend(items)
        if not items or len(results) >= max_results:
            break
        start += 10
        time.sleep(0.25)
    return results

# -------------------------
# STEP 1: SEARCH ACCOUNTS
# -------------------------
def search_instagram_accounts(name: str, max_results: int = 40):
    query = build_query(name)
    items = cse_search(query, max_results=max_results)
    candidates = {}

    for it in items:
        link = it.get("link", "")
        title = it.get("title", "")
        username = get_username(link)
        if not username:
            continue
        display_name = extract_display_name(title)
        readable_user = username_to_readable(username)
        score = max(fuzzy_score(name, display_name), fuzzy_score(name, readable_user))
        if username not in candidates or score > candidates[username]["score"]:
            candidates[username] = {
                "username": username,
                "display_name": display_name,
                "profile_url": f"https://instagram.com/{username}/",
                "score": score,
            }

    results = list(candidates.values())
    results.sort(key=lambda x: x["score"], reverse=True)
    return results

# -------------------------
# STEP 2: META GRAPH
# -------------------------
def get_long_lived_token():
    url = f"https://graph.facebook.com/{GRAPH_VERSION}/oauth/access_token"
    params = {
        "grant_type": "fb_exchange_token",
        "client_id": FB_APP_ID,
        "client_secret": FB_APP_SECRET,
        "fb_exchange_token": FB_SHORT_TOKEN,
    }
    resp = requests.get(url, params=params, timeout=20)
    if resp.status_code != 200:
        raise Exception(f"Error: {resp.text}")
    return resp.json()["access_token"]

def get_metadata(username: str, token: str):
    fields = (
        "name,website,biography,followers_count,follows_count,media_count,"
        "media{timestamp},profile_picture_url,username"
    )
    url = (
        f"https://graph.facebook.com/{GRAPH_VERSION}/{IG_USER_ID}"
        f"?fields=business_discovery.username({username}){{{fields}}}&access_token={token}"
    )
    r = requests.get(url)
    if r.status_code != 200:
        return None
    data = r.json()
    return data.get("business_discovery")

# -------------------------
# STEP 3: SAVE + DOWNLOAD
# -------------------------
def save_csv_and_urls(name: str, metadata_list: list, folder: str):
    csv_path = os.path.join(folder, f"{name}.csv")
    txt_path = os.path.join(folder, "profile urls.txt")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "Instagram Account name", "Username", "Profile URL",
            "Number of posts", "Number of followers", "Number of following",
            "Bio/description text", "profile_picture_url"
        ])
        for md in metadata_list:
            writer.writerow([
                md.get("name", ""),
                md.get("username", ""),
                f"https://www.instagram.com/{md.get('username','')}/",
                md.get("media_count", ""),
                md.get("followers_count", ""),
                md.get("follows_count", ""),
                md.get("biography", "").replace("\n", " "),
                md.get("profile_picture_url", ""),
            ])

    with open(txt_path, "w", encoding="utf-8") as f:
        for md in metadata_list:
            if md.get("profile_picture_url"):
                f.write(md["profile_picture_url"] + "\n")

def download_images(metadata_list, images_folder):
    ensure_dir(images_folder)
    for md in tqdm(metadata_list, desc="Downloading profile pictures"):
        url = md.get("profile_picture_url")
        if not url:
            continue
        username = md.get("username", "unknown")
        ext = os.path.splitext(url.split("?")[0])[-1].lower() or ".jpg"
        path = os.path.join(images_folder, f"{username}{ext}")
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                with open(path, "wb") as f:
                    f.write(r.content)
        except Exception:
            continue

# -------------------------
# MAIN LOGIC
# -------------------------
if __name__ == "__main__":
    print("=== Instagram Pipeline ===")
    searched_name = input("Enter person’s name: ").strip()
    if not searched_name:
        print("Please enter a name.")
        exit()

    folder_name = re.sub(r'[\\/:*?"<>|]+', "_", searched_name)
    base_dir = os.path.join(MAIN_FOLDER, folder_name)
    images_dir = os.path.join(base_dir, "Images")

    ensure_dir(MAIN_FOLDER)
    already_exists = os.path.isdir(base_dir) and folder_has_existing_csv(base_dir)

    overwrite = True
    if already_exists:
        print(f"\nFound existing data for '{folder_name}' at: {base_dir}")
        overwrite = input("Overwrite existing data (re-run search & metadata & downloads)? [y/N]: ").strip().lower().startswith("y")

    ensure_dir(base_dir)
    ensure_dir(images_dir)

    if overwrite:
        print(f"\n[1] Searching for Instagram profiles for '{searched_name}' ...")
        accounts = search_instagram_accounts(searched_name, max_results=40)
        df = pd.DataFrame(accounts)
        if len(df):
            print(df.to_string(index=False))
        else:
            print("No usernames found.")
            if not already_exists:
                exit()

        usernames = [a["username"] for a in accounts]

        print("\n[2] Getting metadata from Meta Graph API...")
        token = get_long_lived_token()
        metadata_list = []
        for u in tqdm(usernames):
            md = get_metadata(u, token)
            if md:
                metadata_list.append(md)
            time.sleep(0.2)

        if metadata_list:
            df_meta = pd.DataFrame([{
                "Instagram Account name": md.get("name"),
                "Username": md.get("username"),
                "Profile URL": f"https://www.instagram.com/{md.get('username')}/",
                "Number of posts": md.get("media_count"),
                "Number of followers": md.get("followers_count"),
                "Number of following": md.get("follows_count"),
                "Bio/description text": md.get("biography"),
            } for md in metadata_list])
            print("\n[3] Metadata Found")

            save_csv_and_urls(searched_name, metadata_list, base_dir)
            print(f"\nSaved CSV and URLs in: {base_dir}")

            download_images(metadata_list, images_dir)
            print(f"\nProfile pictures saved in: {images_dir}")
        else:
            print("No metadata found for these usernames.")
    else:
        print("Keeping existing data. Skipping name search & metadata.")

    # ===============================================================
    # OPTIONAL: Run local image matcher (find_image_match.py)
    # ===============================================================
    choice = input("\nDo you want to check a target image against the downloaded profile photos? [y/N]: ").strip().lower()
    if choice.startswith("y"):
        try:
            from find_image_match import find_image_in_folder  # 👈 your file

            search_folder = images_dir  # look inside Images folder
            print(f"\nSearching in: {search_folder}")

            target_path = input("Enter the FULL path to your target image: ").strip()
            target_path = clean_path(target_path)

            if not os.path.isfile(target_path):
                print(f"❌ Target image not found: {target_path}")
            else:
                print(f"\n🔍 Comparing: {target_path}\n")
                find_image_in_folder(search_folder, target_path)

        except Exception as e:
            print(f"❌ Could not run the image matching script: {e}")
    else:
        print("Skipping image comparison step.")
