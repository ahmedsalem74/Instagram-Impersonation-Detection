import os
import hashlib
from typing import List, Tuple, Dict, Optional

from PIL import Image, ImageChops, ImageOps
import imagehash

# Optional robust stage (feature matching)
try:
    import cv2
    import numpy as np
    OPENCV_AVAILABLE = True
except Exception:
    OPENCV_AVAILABLE = False

# ================== CONFIG ==================
HASH_SIZE = 16
SIMILARITY_THRESHOLD = 12     # multi-hash acceptance (tolerates recompression/resizes)
SEARCH_RECURSIVELY = True
ALLOWED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}

# ORB stage (robust similarity)
USE_ORB_FALLBACK = True
ORB_GOOD_MATCHES_MIN = 28     # accept if >= this many good matches
ORB_RATIO = 0.75              # Lowe’s ratio test
ORB_MAX_FEATURES = 2000

# If nothing passes any threshold, still return the single best candidate (True = yes)
ACCEPT_BEST_IF_NONE = True
# ============================================


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def load_image(path: str) -> Image.Image:
    img = Image.open(path)
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def pixel_equal(img1: Image.Image, img2: Image.Image) -> bool:
    if img1.size != img2.size or img1.mode != img2.mode:
        return False
    diff = ImageChops.difference(img1, img2)
    return diff.getbbox() is None


def normalized(img: Image.Image, max_dim: int = 768) -> Image.Image:
    w, h = img.size
    if max(w, h) <= max_dim:
        return img
    if w >= h:
        new_w = max_dim
        new_h = int(h * (max_dim / w))
    else:
        new_h = max_dim
        new_w = int(w * (max_dim / h))
    return img.resize((new_w, new_h), Image.LANCZOS)


def target_variants(target_path: str) -> List[Tuple[str, Image.Image]]:
    base = normalized(load_image(target_path))
    variants = []
    for angle in (0, 90, 180, 270):
        variants.append((f"rot{angle}", base.rotate(angle, expand=True)))
    variants.append(("flipH", base.transpose(Image.FLIP_LEFT_RIGHT)))
    variants.append(("flipV", base.transpose(Image.FLIP_TOP_BOTTOM)))
    return variants


def hash_bundle(img: Image.Image) -> Dict[str, imagehash.ImageHash]:
    return {
        "phash": imagehash.phash(img, hash_size=HASH_SIZE),
        "dhash": imagehash.dhash(img, hash_size=HASH_SIZE),
        "ahash": imagehash.average_hash(img, hash_size=HASH_SIZE),
    }


def min_bundle_distance(a: Dict[str, imagehash.ImageHash],
                        b: Dict[str, imagehash.ImageHash]) -> int:
    return min(a[k] - b[k] for k in a.keys())


def best_distance_to_variants(img_bundle: Dict[str, imagehash.ImageHash],
                              variant_bundles: List[Tuple[str, Dict[str, imagehash.ImageHash]]]) -> Tuple[int, str]:
    best = (10**9, "")
    for name, vb in variant_bundles:
        d = min_bundle_distance(img_bundle, vb)
        if d < best[0]:
            best = (d, name)
    return best


def iter_files(folder: str):
    if SEARCH_RECURSIVELY:
        for root, _, files in os.walk(folder):
            for f in files:
                yield os.path.join(root, f)
    else:
        for f in os.listdir(folder):
            yield os.path.join(folder, f)


def looks_like_image(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in ALLOWED_EXT


# -------- ORB feature matching (robust) --------
def to_cv(img: Image.Image) -> "np.ndarray":
    arr = np.array(img)
    return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)


def orb_good_matches(imgA: Image.Image, imgB: Image.Image) -> int:
    if not OPENCV_AVAILABLE:
        return 0
    gA = to_cv(normalized(imgA, 1000))
    gB = to_cv(normalized(imgB, 1000))
    orb = cv2.ORB_create(nfeatures=ORB_MAX_FEATURES)
    kpa, desa = orb.detectAndCompute(gA, None)
    kpb, desb = orb.detectAndCompute(gB, None)
    if desa is None or desb is None or len(desa) < 2 or len(desb) < 2:
        return 0
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=False)
    matches = bf.knnMatch(desa, desb, k=2)
    good = 0
    for m, n in matches:
        if m.distance < ORB_RATIO * n.distance:
            good += 1
    return good

def get_instagram_url_from_path(file_path: str) -> str:
    """
    Extracts the filename without extension from a full path and
    constructs a potential Instagram profile URL.
    Handles filenames with multiple dots.
    """
    # Use pathlib to get the filename without the extension
    from pathlib import Path
    base_name = Path(file_path).stem
    # Construct the Instagram URL
    instagram_url = f"https://www.instagram.com/{base_name}/"
    return instagram_url

# -----------------------------------------------


def find_image_in_folder(folder_path: str, target_image_path: str):
    # Byte-identical shortcut
    try:
        target_sha = sha256_file(target_image_path)
    except Exception as e:
        print(f" Could not read target image: {e}")
        return

    # Prepare variants & bundles
    try:
        variants = target_variants(target_image_path)
        variant_bundles = [(name, hash_bundle(img)) for name, img in variants]
        target_img_original = [img for name, img in variants if name == "rot0"][0]
    except Exception as e:
        print(f" Failed preparing target variants: {e}")
        return

    exact_matches = []
    similar_matches = []        # (path, dist, via)
    orb_similar_matches = []    # (path, good_matches)

    debug_closest = []          # (path, dist, via)

    # Scan
    for fpath in iter_files(folder_path):
        if not os.path.isfile(fpath) or not looks_like_image(fpath):
            continue

        # byte-identical
        try:
            if sha256_file(fpath) == target_sha:
                exact_matches.append(fpath)
                continue
        except Exception:
            pass

        # image checks
        try:
            img = load_image(fpath)

            # pixel-identical (same dims)
            if pixel_equal(img, target_img_original):
                exact_matches.append(fpath)
                continue

            # multi-hash similarity
            img_bundle = hash_bundle(normalized(img))
            dist, via = best_distance_to_variants(img_bundle, variant_bundles)
            debug_closest.append((fpath, dist, via))
            if dist <= SIMILARITY_THRESHOLD:
                similar_matches.append((fpath, dist, via))
                continue

            # ORB fallback (heavy-duty)
            if USE_ORB_FALLBACK and OPENCV_AVAILABLE:
                gm = orb_good_matches(img, target_img_original)
                if gm >= ORB_GOOD_MATCHES_MIN:
                    orb_similar_matches.append((fpath, gm))

        except Exception:
            continue

    # -------- Results --------
    if exact_matches:
        print("\n Exact matches:")
        for p in exact_matches:
            print("   →", p)

    reported = False

    if similar_matches:
        similar_matches.sort(key=lambda x: x[1])
        print("\n Similar matches (multi-hash; lower distance = closer):")
        for p, d, v in similar_matches:
            print(f"   → {p}   (distance={d}, via={v})")
        reported = True

    if orb_similar_matches:
        orb_similar_matches.sort(key=lambda x: -x[1])
        print("\n Similar matches (ORB features; higher = closer):")
        for p, gm in orb_similar_matches:
            instagram_url = get_instagram_url_from_path(p)
            print(f"   → {p}   (good_matches={gm})")
            print(f"      Instagram URL: {instagram_url}")
        reported = True

    # If still nothing accepted, optionally return best candidate
    if not exact_matches and not similar_matches and not orb_similar_matches:
        debug_closest.sort(key=lambda x: x[1])
        print("\n No matches passed thresholds.")
        if debug_closest:
            print("\n Closest by hash (top 5):")
            for p, d, v in debug_closest[:5]:
                print(f"   • {p}   (distance={d}, via={v})")

            if ACCEPT_BEST_IF_NONE:
                best_path, best_d, best_v = debug_closest[0]
                print("\n Returning best candidate anyway (ACCEPT_BEST_IF_NONE=True):")
                print(f"   → {best_path}   (distance={best_d}, via={best_v})")
                reported = True

    if not reported and not exact_matches:
        print("\n No exact or similar matches found.")


if __name__ == "__main__":
    folder = input(" Enter the folder path that contains images: ").strip('"').strip()
    target = input(" Enter the target image path: ").strip('"').strip()
    find_image_in_folder(folder, target)
