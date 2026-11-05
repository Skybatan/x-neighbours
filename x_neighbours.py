#!/usr/bin/env python3
"""X Neighbours: who replied, quoted, liked, and reposted, plus an occasional picture.

Settings come from config.json. CLI flags override it. The script does not call X.
It reads raw JSON saved from X tool calls (see README.md) in the data folder:

  posts_*.json         get_users_posts pages (expansions=author_id)
  mentions_*.json      get_users_mentions pages (expansions=author_id)
  likes_<postid>.json  get_posts_liking_users
  reposts_<postid>.json get_posts_reposted_by
  quotes_<postid>.json get_posts_quoted_posts
  latest_<userid>.json get_users_posts for one neighbour (their latest posts)
  my_likes_*.json      get_users_liked_posts (posts the owner already liked)
  my_posts_*.json      get_users_posts for the owner, including replies and reposts
  followers_*.json     get_users_me_followers pages
  following_*.json     get_users_me_following pages

Usage:
  python3 x_neighbours.py --handle your_handle --user-id your_user_id
                      [--data data] [--out .] [--now 2026-11-04T18:00:00Z]
                      [--rings 3] [--top 10]
                      [--report likes|replies|both] [--per-post] [--per-day]
                      [--good-neighbours PATH]
"""
import argparse
import glob
import json
import math
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def load(pattern):
    out = []
    for f in sorted(glob.glob(pattern)):
        with open(f, encoding="utf-8") as fh:
            try:
                out.append((f, json.load(fh)))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{f} is not JSON ({exc})") from exc
    return out


def load_soft(pattern):
    """Engagement files are optional. A missing or broken file is ignored."""
    out = []
    for f in sorted(glob.glob(pattern)):
        try:
            with open(f, encoding="utf-8") as fh:
                doc = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(doc, dict):
            out.append(doc)
    return out


def ts(s):
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def fmt_num(n):
    n = n or 0
    if n >= 1_000_000:
        return f"{n/1e6:.1f}M"
    if n >= 1_000:
        return f"{n/1e3:.1f}K"
    return str(n)


def as_list(value):
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(part).strip() for part in value if str(part).strip()]


def as_bool(value):
    if isinstance(value, str):
        return value.strip().lower() not in ("0", "false", "no", "off", "")
    return bool(value)


def counted(n, singular, plural):
    return f"{n} {singular if n == 1 else plural}"


class Data:
    def __init__(self, data_dir, me_id):
        self.data_dir = data_dir
        self.me = str(me_id)
        self.users = {}
        self.posts = {}
        self.mentions = []
        self._mention_ids = set()
        self.likes = {}
        self.reposts = {}
        self.quotes = {}
        self.latest = {}
        self.originals = {}
        self.engaged = set()
        self.owner_replied_to = set()
        self.likes_truncated = []
        for _, doc in load(os.path.join(data_dir, "posts_*.json")):
            for post in doc.get("data") or []:
                if not post.get("id"):
                    continue
                post = dict(post)
                post["id"] = str(post["id"])
                if post.get("author_id") is not None:
                    post["author_id"] = str(post["author_id"])
                if post.get("author_id", self.me) == self.me:
                    self.posts[post["id"]] = post
                    for ref in post.get("referenced_tweets") or []:
                        if ref.get("type") == "replied_to" and ref.get("id"):
                            self.owner_replied_to.add(str(ref["id"]))
            self._users((doc.get("includes") or {}).get("users") or [])
        for _, doc in load(os.path.join(data_dir, "mentions_*.json")):
            for mention in doc.get("data") or []:
                mention = dict(mention)
                mid = mention.get("id")
                if mid is not None:
                    mid = str(mid)
                    mention["id"] = mid
                    if mid in self._mention_ids:
                        continue
                    self._mention_ids.add(mid)
                if mention.get("author_id") is not None:
                    mention["author_id"] = str(mention["author_id"])
                if mention.get("in_reply_to_user_id") is not None:
                    mention["in_reply_to_user_id"] = str(mention["in_reply_to_user_id"])
                refs = []
                for ref in mention.get("referenced_tweets") or []:
                    ref = dict(ref)
                    if ref.get("id") is not None:
                        ref["id"] = str(ref["id"])
                    refs.append(ref)
                if refs:
                    mention["referenced_tweets"] = refs
                self.mentions.append(mention)
            self._users((doc.get("includes") or {}).get("users") or [])
        for path, doc in load(os.path.join(data_dir, "likes_*.json")):
            match = re.search(r"likes_(\d+)", os.path.basename(path))
            if not match:
                raise SystemExit(f"liker file name must contain likes_<post id>: {path}")
            pid = match.group(1)
            users = [self._prepare_user(u) for u in (doc.get("data") or [])]
            self._users(users)
            bucket = self.likes.setdefault(pid, [])
            have = set(bucket)
            for user in users:
                uid = user.get("id")
                if uid and uid not in have:
                    bucket.append(uid)
                    have.add(uid)
        for pid, ids in self.likes.items():
            want = like_count(self.posts.get(pid, {}))
            if want > len(ids):
                self.likes_truncated.append((pid, len(ids), want))
        self._load_user_lists("reposts_*.json", self.reposts, "reposts_<post id>")
        self._load_quotes()
        self._load_latest()
        self._load_engagement()
        self.followers = self._idset("followers_*.json")
        self.following = self._idset("following_*.json")

    def _prepare_user(self, user):
        user = dict(user)
        if user.get("id") is not None:
            user["id"] = str(user["id"])
        url = user.get("profile_image_url") or ""
        if url and not url.startswith(("http://", "https://")):
            local = url[7:] if url.startswith("file://") else url
            if not os.path.isabs(local):
                local = os.path.join(self.data_dir, local)
            if os.path.isfile(local):
                user["profile_image_url"] = os.path.abspath(local)
        return user

    def _users(self, users):
        for user in users:
            user = self._prepare_user(user)
            uid = user.get("id")
            if not uid:
                continue
            old = self.users.get(uid, {})
            fresh = {k: v for k, v in user.items() if v not in (None, "")}
            self.users[uid] = {**old, **fresh}

    def _load_user_lists(self, pattern, dest, label):
        for path, doc in load(os.path.join(self.data_dir, pattern)):
            match = re.search(r"_(\d+)", os.path.basename(path))
            if not match:
                raise SystemExit(f"{label} file name must include an id: {path}")
            pid = match.group(1)
            users = [self._prepare_user(u) for u in (doc.get("data") or [])]
            self._users(users)
            bucket = dest.setdefault(pid, [])
            have = set(bucket)
            for user in users:
                uid = user.get("id")
                if uid and uid not in have:
                    bucket.append(uid)
                    have.add(uid)

    def _load_quotes(self):
        for path, doc in load(os.path.join(self.data_dir, "quotes_*.json")):
            match = re.search(r"quotes_(\d+)", os.path.basename(path))
            if not match:
                raise SystemExit(f"quote file name must contain quotes_<post id>: {path}")
            pid = match.group(1)
            self._users((doc.get("includes") or {}).get("users") or [])
            bucket = self.quotes.setdefault(pid, [])
            have = {item.get("id") for item in bucket}
            for post in doc.get("data") or []:
                post = dict(post)
                if post.get("id") is None:
                    continue
                post["id"] = str(post["id"])
                if post["id"] in have:
                    continue
                if post.get("author_id") is not None:
                    post["author_id"] = str(post["author_id"])
                refs = []
                for ref in post.get("referenced_tweets") or []:
                    ref = dict(ref)
                    if ref.get("id") is not None:
                        ref["id"] = str(ref["id"])
                    refs.append(ref)
                if refs:
                    post["referenced_tweets"] = refs
                post["_on_post"] = pid
                bucket.append(post)
                have.add(post["id"])

    def _load_latest(self):
        for path, doc in load(os.path.join(self.data_dir, "latest_*.json")):
            match = re.search(r"latest_(\d+)", os.path.basename(path))
            if not match:
                continue
            uid = match.group(1)
            self._users((doc.get("includes") or {}).get("users") or [])
            posts = []
            for post in doc.get("data") or []:
                post = dict(post)
                if post.get("id") is None or not post.get("created_at"):
                    continue
                post["id"] = str(post["id"])
                if post.get("author_id") is not None:
                    post["author_id"] = str(post["author_id"])
                if post.get("in_reply_to_user_id") is not None:
                    post["in_reply_to_user_id"] = str(post["in_reply_to_user_id"])
                refs = []
                for ref in post.get("referenced_tweets") or []:
                    ref = dict(ref)
                    if ref.get("id") is not None:
                        ref["id"] = str(ref["id"])
                    refs.append(ref)
                if refs:
                    post["referenced_tweets"] = refs
                if is_original_post(post):
                    posts.append(post)
            if not posts:
                continue
            posts.sort(key=lambda post: ts(post["created_at"]), reverse=True)
            merged = {post["id"]: post for post in self.originals.get(uid, [])}
            for post in posts:
                merged[post["id"]] = post
            ordered = sorted(merged.values(), key=lambda post: ts(post["created_at"]), reverse=True)
            self.originals[uid] = ordered
            self.latest[uid] = ordered[0]

    def _add_owner_targets(self, post):
        if not isinstance(post, dict):
            return
        own = str(post.get("id") or "")
        conversation = post.get("conversation_id")
        if conversation and str(conversation) != own:
            self.engaged.add(str(conversation))
        for key in ("in_reply_to_tweet_id", "in_reply_to_status_id"):
            if post.get(key):
                self.engaged.add(str(post[key]))
        for ref in post.get("referenced_tweets") or []:
            if not isinstance(ref, dict) or ref.get("id") is None:
                continue
            kind = (ref.get("type") or "").lower()
            if kind in ("replied_to", "quoted", "retweeted"):
                self.engaged.add(str(ref["id"]))

    def _load_engagement(self):
        """Post ids the owner already liked, replied to, reposted, or quoted.

        Missing files leave the set empty apart from replies already in posts_*.json.
        """
        self.engaged = set(self.owner_replied_to)
        for post in self.posts.values():
            self._add_owner_targets(post)
        for doc in load_soft(os.path.join(self.data_dir, "my_posts_*.json")):
            for post in doc.get("data") or []:
                self._add_owner_targets(post)
        for doc in load_soft(os.path.join(self.data_dir, "my_likes_*.json")):
            for post in doc.get("data") or []:
                if isinstance(post, dict) and post.get("id") is not None:
                    self.engaged.add(str(post["id"]))

    def _idset(self, pattern):
        found = set()
        for _, doc in load(os.path.join(self.data_dir, pattern)):
            for user in doc.get("data") or []:
                user = self._prepare_user(user)
                uid = user.get("id")
                if not uid:
                    continue
                found.add(uid)
                self.users.setdefault(uid, user)
        return found

    def relation(self, uid):
        follows_you = uid in self.followers
        you_follow = uid in self.following
        if follows_you and you_follow:
            return "mutual"
        if follows_you:
            return "follows-you"
        if you_follow:
            return "you-follow"
        return "neither"

    def _in_window(self, created, since, until):
        if not created:
            return False
        when = ts(created)
        if when < since:
            return False
        if until is not None and when >= until:
            return False
        return True

    def window(self, since, until=None):
        likes, replies = Counter(), Counter()
        for pid, post in self.posts.items():
            if not self._in_window(post.get("created_at"), since, until):
                continue
            for uid in self.likes.get(pid, []):
                if uid != self.me:
                    likes[uid] += 1
        for mention in self.mentions:
            if mention.get("author_id") == self.me:
                continue
            if not self._in_window(mention.get("created_at"), since, until):
                continue
            refs = [ref.get("id") for ref in mention.get("referenced_tweets") or []
                    if ref.get("type") == "replied_to"]
            if mention.get("in_reply_to_user_id") == self.me or any(ref in self.posts for ref in refs):
                replies[mention["author_id"]] += 1
        excluded = getattr(self, "exclude", set())
        for counts in (likes, replies):
            for uid in list(counts):
                if self.users.get(uid, {}).get("username", "").lower() in excluded:
                    del counts[uid]
        return likes, replies


def is_original_post(post):
    """A catch-up post is their own writing: not a reply and not a plain repost.

    Quote posts are kept. A quote that is also a reply is a reply.
    """
    if not post:
        return False
    if post.get("in_reply_to_user_id"):
        return False
    text = post.get("text") or ""
    if text.startswith("RT @"):
        return False
    for ref in post.get("referenced_tweets") or []:
        kind = (ref.get("type") or "").lower()
        if kind in ("replied_to", "retweeted"):
            return False
    return True


def like_count(post):
    return (post.get("public_metrics") or {}).get("like_count", 0) or 0


def summary(user):
    metrics = user.get("public_metrics") or {}
    bio = re.sub(r"\s+", " ", (user.get("description") or "").strip())
    bio = re.sub(r"https?://\S+", "", bio).strip()
    if len(bio) > 90:
        bio = bio[:87].rstrip() + "…"
    stats = (f"{fmt_num(metrics.get('followers_count'))} followers · "
             f"{fmt_num(metrics.get('tweet_count'))} posts")
    return f"{bio or '(no bio)'} — {stats}"


def link(user):
    handle = user.get("username", "?")
    return f"[@{handle}](https://x.com/{handle})"


def score(likes, replies, like_weight, reply_weight):
    ranked = Counter()
    people = set(likes) | set(replies)
    order = sorted(people, key=lambda uid: (
        -(likes[uid] * like_weight + replies[uid] * reply_weight),
        -replies[uid],
        uid,
    ))
    for uid in order:
        ranked[uid] = likes[uid] * like_weight + replies[uid] * reply_weight
    return ranked


def active_counts(likes, replies, report):
    if report == "likes":
        return likes, Counter()
    if report == "replies":
        return Counter(), replies
    return likes, replies


def append_table(lines, title, counts, unit, ranked, data, top, level=2):
    lines += ["#" * level + f" {title}", "",
              f"| # | Who | {unit} | Score | Relationship |",
              "|---|---|---|---|---|"]
    for index, (uid, count) in enumerate(counts.most_common(top), 1):
        user = data.users.get(uid, {"username": uid})
        lines.append(
            f"| {index} | {user.get('name', '')} {link(user)} | {count} | "
            f"{ranked[uid]} | {data.relation(uid)} |"
        )
    if not counts:
        lines.append("| – | none | – | – | – |")
    lines.append("")


def suggestion_detail(report, likes, replies, uid):
    like_text = counted(likes[uid], "like", "likes")
    reply_text = counted(replies[uid], "reply", "replies")
    if report == "likes":
        return like_text
    if report == "replies":
        return reply_text
    return f"{like_text}, {reply_text}"


def kept_user(data, uid):
    if not uid or uid == data.me:
        return False
    handle = data.users.get(uid, {}).get("username", "")
    return handle.lower() not in getattr(data, "exclude", set())


def display_name(data, uid):
    return "@" + data.users.get(uid, {}).get("username", uid)


def each_utc_day(since, until):
    start = since.astimezone(timezone.utc)
    end = until.astimezone(timezone.utc)
    cursor = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    while cursor <= end:
        day_end = cursor + timedelta(days=1)
        yield cursor.date(), max(start, cursor), min(end + timedelta(seconds=1), day_end)
        cursor = day_end


def snippet(text):
    text = re.sub(r"\s+", " ", (text or "").strip())
    if len(text) > 90:
        return text[:87].rstrip() + "…"
    return text


THEMES = {
    "midnight": dict(top=(10, 14, 39), bot=(3, 5, 18), glow=(45, 60, 140), orbit=(120, 140, 220, 55),
                     ring0=(126, 160, 255, 255), ring=(90, 110, 190, 255), label_bg=(5, 8, 25, 170),
                     label=(225, 232, 255, 255), title=(240, 244, 255, 255), sub=(160, 175, 230, 255)),
    "light": dict(top=(248, 250, 255), bot=(226, 233, 246), glow=(255, 255, 255), orbit=(90, 110, 160, 70),
                  ring0=(59, 105, 230, 255), ring=(150, 170, 215, 255), label_bg=(255, 255, 255, 210),
                  label=(25, 35, 60, 255), title=(15, 25, 50, 255), sub=(80, 95, 130, 255)),
    "sunset": dict(top=(58, 18, 74), bot=(232, 106, 72), glow=(255, 170, 110), orbit=(255, 220, 190, 70),
                   ring0=(255, 200, 120, 255), ring=(250, 150, 120, 255), label_bg=(40, 10, 40, 170),
                   label=(255, 240, 225, 255), title=(255, 246, 236, 255), sub=(255, 215, 190, 255)),
}
FONTS = (
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
     "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    ("/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
     "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf"),
    ("/Library/Fonts/Arial Bold.ttf", "/Library/Fonts/Arial.ttf"),
    ("/System/Library/Fonts/Supplemental/Arial Bold.ttf",
     "/System/Library/Fonts/Supplemental/Arial.ttf"),
    ("C:/Windows/Fonts/arialbd.ttf", "C:/Windows/Fonts/arial.ttf"),
)


def font(size, bold=True):
    from PIL import ImageFont
    for bold_path, regular_path in FONTS:
        path = bold_path if bold else regular_path
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
        other = regular_path if bold else bold_path
        if os.path.exists(other):
            return ImageFont.truetype(other, size)
    return ImageFont.load_default()


def fetch_avatar(user, cache_dir, size):
    from PIL import Image, ImageDraw
    url = user.get("profile_image_url") or ""
    path = os.path.join(cache_dir, f"{user.get('id', 'x')}.img")
    img = None
    try:
        if not os.path.exists(path) and url:
            if url.startswith(("http://", "https://")):
                remote = url.replace("_normal", "_400x400")
                req = urllib.request.Request(remote, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    blob = resp.read()
                with open(path, "wb") as fh:
                    fh.write(blob)
            elif os.path.isfile(url):
                with open(url, "rb") as src, open(path, "wb") as fh:
                    fh.write(src.read())
        if os.path.exists(path):
            img = Image.open(path).convert("RGB")
    except Exception:
        img = None
    if img is None:
        img = Image.new("RGB", (400, 400), (60, 70, 110))
        draw = ImageDraw.Draw(img)
        letter = (user.get("username") or "?")[:1].upper()
        face = font(200)
        width = draw.textlength(letter, font=face)
        draw.text(((400 - width) / 2, 80), letter, font=face, fill=(230, 235, 255))
    width, height = img.size
    side = min(width, height)
    img = img.crop(((width - side) // 2, (height - side) // 2,
                    (width + side) // 2, (height + side) // 2))
    img = img.resize((size * 2, size * 2), Image.LANCZOS)
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size * 2 - 1, size * 2 - 1), fill=255)
    img.putalpha(mask)
    return img.resize((size, size), Image.LANCZOS)


def ring_geometry(rings):
    """The original ring layout. Three rings is the usual full picture."""
    if rings >= 4:
        return {
            "cy": 0.545,
            "centre": 0.118,
            "per_ring": [8, 14, 20, 26],
            "radius": [0.150, 0.248, 0.340, 0.430],
            "size": [0.062, 0.048, 0.038, 0.031],
            "name_width": [1.7, 1.35, 1.15, 1.05],
        }
    return {
        "cy": 0.535,
        "centre": 0.165,
        "per_ring": [8, 14, 20][:rings],
        "radius": [0.19, 0.30, 0.395][:rings],
        "size": [0.085, 0.064, 0.05][:rings],
        "name_width": [1.45, 1.45, 1.45][:rings],
    }


def layout_for_count(count, rings):
    """Use fewer, larger rings when only a handful of neighbours showed up."""
    rings = max(1, min(int(rings), 4))
    if count <= 0:
        return {
            "cy": 0.52, "centre": 0.30,
            "per_ring": [], "radius": [], "size": [], "name_width": [],
        }
    if count <= 8:
        return {
            "cy": 0.56,
            "centre": 0.26 if count <= 3 else 0.22,
            "per_ring": [8],
            "radius": [0.36 if count <= 4 else 0.34],
            "size": [0.16 if count <= 3 else 0.13 if count <= 5 else 0.11],
            "name_width": [1.8],
        }
    if count <= 22 and rings >= 2:
        return {
            "cy": 0.55,
            "centre": 0.18,
            "per_ring": [8, 14],
            "radius": [0.24, 0.40],
            "size": [0.105, 0.078],
            "name_width": [1.55, 1.4],
        }
    return ring_geometry(rings)


def draw_house_frame(draw, x, y, size, color, width, gap, roof=0.32):
    """Thin home-shaped outline (roof peak + walls + flat base) around a round avatar."""
    half = size / 2 + gap
    eave = y - size * 0.18
    peak = y - half - size * roof
    overhang = half + size * 0.10
    walls = [(x - half, eave), (x - half, y + half), (x + half, y + half), (x + half, eave)]
    draw.line(walls, fill=color, width=width, joint="curve")
    draw.line([(x - overhang, eave + size * 0.06), (x, peak), (x + overhang, eave + size * 0.06)],
              fill=color, width=width, joint="curve")


def fit_label(draw, text, face, limit):
    while draw.textlength(text, font=face) > limit and len(text) > 4:
        text = text[:-2] + "…"
    return text


def draw_label_at(draw, text, face, x, y, fill_bg, fill_text, scale):
    """Draw a pill whose top-left is (x, y)."""
    text_width = draw.textlength(text, font=face)
    text_height = face.size + 6 * scale
    box = (x - 6 * scale, y - 2 * scale, x + text_width + 6 * scale, y + text_height - 2 * scale)
    draw.rounded_rectangle(box, radius=text_height / 2, fill=fill_bg)
    draw.text((x, y), text, font=face, fill=fill_text)


def draw_label(draw, text, face, x, y, anchor, fill_bg, fill_text, scale):
    text = fit_label(draw, text, face, anchor)
    text_width = draw.textlength(text, font=face)
    draw_label_at(draw, text, face, x - text_width / 2, y, fill_bg, fill_text, scale)


def draw_circle(data, me_user, scores, path, rings=3, show_names=True, width=1200,
                subtitle="Top neighbours of the last 7 days", theme="midnight"):
    theme_colors = THEMES.get(theme, THEMES["midnight"])
    from PIL import Image, ImageDraw, ImageFilter
    cache = os.path.join(os.path.dirname(os.path.abspath(path)), ".avatar_cache")
    os.makedirs(cache, exist_ok=True)
    scale = 2
    canvas_size = width * scale
    background = Image.new("RGB", (canvas_size, canvas_size))
    top, bottom = theme_colors["top"], theme_colors["bot"]
    draw = ImageDraw.Draw(background)
    for y in range(canvas_size):
        blend = y / canvas_size
        color = tuple(int(top[i] + (bottom[i] - top[i]) * blend) for i in range(3))
        draw.line([(0, y), (canvas_size, y)], fill=color)
    glow = Image.new("L", (canvas_size, canvas_size), 0)
    ImageDraw.Draw(glow).ellipse((canvas_size * .18, canvas_size * .18,
                                  canvas_size * .82, canvas_size * .82), fill=90)
    glow = glow.filter(ImageFilter.GaussianBlur(canvas_size * .12))
    background = Image.composite(Image.new("RGB", (canvas_size, canvas_size), theme_colors["glow"]),
                                 background, glow)
    canvas = background.convert("RGBA")
    draw = ImageDraw.Draw(canvas)
    ranked = [uid for uid, _points in scores.most_common()
              if uid in data.users and uid != data.me]
    layout = layout_for_count(len(ranked), rings)
    cx, cy = canvas_size // 2, int(canvas_size * layout["cy"])
    per_ring = layout["per_ring"]
    radius = [canvas_size * r for r in layout["radius"]]
    avatar_size = [int(canvas_size * s) for s in layout["size"]]
    for orbit in radius:
        draw.ellipse((cx - orbit, cy - orbit, cx + orbit, cy + orbit),
                     outline=theme_colors["orbit"], width=2 * scale)
    name_font = [font(max(12, int(size * 0.17))) for size in avatar_size]
    index = 0
    for ring_index in range(len(per_ring)):
        count = min(per_ring[ring_index], max(0, len(ranked) - index))
        if count == 0:
            break
        size = avatar_size[ring_index]
        for slot in range(count):
            uid = ranked[index]
            index += 1
            angle = -math.pi / 2 + 2 * math.pi * slot / count + (ring_index % 2) * math.pi / count
            x = cx + radius[ring_index] * math.cos(angle)
            y = cy + radius[ring_index] * math.sin(angle)
            ring_color = theme_colors["ring0"] if ring_index == 0 else theme_colors["ring"]
            pad = 3 * scale
            draw_house_frame(draw, x, y, size, ring_color, 2 * scale, pad)
            avatar = fetch_avatar(data.users[uid], cache, size)
            canvas.alpha_composite(avatar, (int(x - size / 2), int(y - size / 2)))
            if show_names:
                label = "@" + data.users[uid].get("username", "")
                face = name_font[ring_index]
                wedge = 2 * radius[ring_index] * math.sin(math.pi / max(count, 1))
                limit = min(size * layout["name_width"][ring_index], wedge * 0.92)
                draw_label(draw, label, face, x, y + size / 2 + pad + 4 * scale, limit,
                           theme_colors["label_bg"], theme_colors["label"], scale)
    centre = int(canvas_size * layout["centre"])
    draw_house_frame(draw, cx, cy, centre, theme_colors["ring0"], 5 * scale, 4 * scale, roof=0.2)
    canvas.alpha_composite(fetch_avatar(me_user, cache, centre), (cx - centre // 2, cy - centre // 2))
    title_font = font(int(canvas_size * .032))
    subtitle_font = font(int(canvas_size * .016), bold=False)
    title = f"@{me_user.get('username')}'s X Neighbours"
    while title_font.size > 16 and draw.textlength(title, font=title_font) > canvas_size * 0.9:
        title_font = font(title_font.size - 2)
    draw.text(((canvas_size - draw.textlength(title, font=title_font)) / 2, canvas_size * .018),
              title, font=title_font, fill=theme_colors["title"])
    sub_y = canvas_size * .018 + title_font.size + 10 * scale
    while subtitle_font.size > 12 and draw.textlength(subtitle, font=subtitle_font) > canvas_size * 0.9:
        subtitle_font = font(subtitle_font.size - 1, bold=False)
    draw.text(((canvas_size - draw.textlength(subtitle, font=subtitle_font)) / 2, sub_y),
              subtitle, font=subtitle_font, fill=theme_colors["sub"])
    canvas.convert("RGB").resize((width, width), Image.LANCZOS).save(path, optimize=True)


DEFAULTS = {
    "handle": None,
    "user_id": None,
    "like_weight": 1,
    "reply_weight": 3,
    "exclude": ["grok"],
    "rings": 3,
    "show_names": True,
    "first_run_days": 2,
    "items_per_user": 3,
    "theme": "midnight",
    "windows": ["week"],
    "top": 10,
    "report": "both",
    "per_post": False,
    "per_day": False,
    "good_neighbours": None,
    "timezone": "",
    "fresh_hours": None,
    "state": None,
}
WINDOWS = {
    "day": ("last 24 hours", 1, "Top neighbours of the last 24 hours"),
    "week": ("last 7 days", 7, "Top neighbours of the last 7 days"),
}
REPORTS = ("likes", "replies", "both")
SUBTITLES = {
    "both": {
        "day": "Top neighbours of the last 24 hours",
        "week": "Top neighbours of the last 7 days",
    },
    "likes": {
        "day": "Top likers of the last 24 hours",
        "week": "Top likers of the last 7 days",
    },
    "replies": {
        "day": "Top repliers of the last 24 hours",
        "week": "Top repliers of the last 7 days",
    },
}


def whole_number(value):
    number = float(value)
    return int(number) if number == int(number) else number


def hidden_user(data, uid):
    if not uid or uid == data.me:
        return True
    return data.users.get(uid, {}).get("username", "").lower() in getattr(data, "exclude", set())


def stranger(data, uid):
    return uid not in data.following


def ago(when, now):
    seconds = max(0, (now - when).total_seconds())
    if seconds < 3600:
        return f"{max(1, int(seconds // 60))}m ago"
    if seconds < 86400:
        return f"{max(1, int(seconds // 3600))}h ago"
    return f"{max(1, int(seconds // 86400))}d ago"


def post_text(data, pid):
    text = snippet((data.posts.get(pid) or {}).get("text"))
    return text or "your post"


def status_url(data, uid, post_id):
    handle = data.users.get(uid, {}).get("username", uid)
    return f"https://x.com/{handle}/status/{post_id}"


def load_good_neighbours(path):
    """Personal list. A missing file is an empty list. At most 20 people."""
    if not path or not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
    rows = doc.get("neighbours") if isinstance(doc, dict) else None
    if not isinstance(rows, list):
        return []
    people = []
    for item in rows:
        if not isinstance(item, dict) or not item.get("id") or not item.get("username"):
            continue
        people.append({
            "id": str(item["id"]),
            "username": str(item["username"]).lstrip("@"),
            "name": item.get("name") or str(item["username"]).lstrip("@"),
            "added": item.get("added") or "",
        })
        if len(people) >= 20:
            break
    return people


def good_neighbour_ids(neighbours):
    ids = {person["id"] for person in neighbours}
    names = {person["username"].lower() for person in neighbours}
    return ids, names


def is_good_neighbour(uid, username, ids, names):
    return uid in ids or (username or "").lower() in names


def build_activity(data, since, until, top, like_weight, reply_weight, mode, now,
                   good_neighbours=None):
    items = []
    seen = set()

    def add_item(kind, post, author, on_id):
        if hidden_user(data, author) or post.get("id") in seen:
            return
        if not data._in_window(post.get("created_at"), since, until):
            return
        seen.add(post["id"])
        when = ts(post["created_at"])
        items.append({
            "kind": kind,
            "id": post["id"],
            "author_id": author,
            "text": snippet(post.get("text")) or "(no text)",
            "created_at": when,
            "on_id": on_id,
            "on_text": post_text(data, on_id) if on_id else "your post",
            "url": status_url(data, author, post["id"]),
            "replied": post["id"] in data.owner_replied_to,
        })

    for mention in data.mentions:
        author = mention.get("author_id")
        refs = [ref.get("id") for ref in mention.get("referenced_tweets") or []
                if ref.get("type") == "replied_to"]
        quoted = [ref.get("id") for ref in mention.get("referenced_tweets") or []
                  if ref.get("type") == "quoted"]
        on_reply = next((ref for ref in refs if ref in data.posts), None)
        on_quote = next((ref for ref in quoted if ref in data.posts), None)
        is_reply = mention.get("in_reply_to_user_id") == data.me or on_reply is not None
        if on_quote and not is_reply:
            add_item("quote", mention, author, on_quote)
        elif is_reply:
            add_item("reply", mention, author, on_reply)
    for pid, quotes in data.quotes.items():
        for quote in quotes:
            add_item("quote", quote, quote.get("author_id"), quote.get("_on_post") or pid)

    likes_c, reposts_c = Counter(), Counter()
    reply_c, quote_c = Counter(), Counter()
    for pid, post in data.posts.items():
        if not data._in_window(post.get("created_at"), since, until):
            continue
        for uid in data.likes.get(pid, []):
            if not hidden_user(data, uid):
                likes_c[uid] += 1
        for uid in data.reposts.get(pid, []):
            if not hidden_user(data, uid):
                reposts_c[uid] += 1
    for item in items:
        (quote_c if item["kind"] == "quote" else reply_c)[item["author_id"]] += 1

    def points(uid, which):
        likes = likes_c[uid] if which != "replies" else 0
        reposts = reposts_c[uid] if which != "replies" else 0
        replies = reply_c[uid] if which != "likes" else 0
        quotes = quote_c[uid] if which != "likes" else 0
        if which == "likes":
            replies = quotes = 0
        if which == "replies":
            likes = reposts = 0
        return (likes + reposts) * like_weight + (replies + quotes) * reply_weight

    good = good_neighbours or []
    good_ids, good_names = good_neighbour_ids(good)

    def describe(uid, fallback=None):
        user = data.users.get(uid) or fallback or {"id": uid, "username": uid, "name": uid}
        username = user.get("username") or (fallback or {}).get("username") or uid
        name = user.get("name") or (fallback or {}).get("name") or username
        return {
            "id": uid,
            "name": name,
            "username": username,
            "stranger": uid not in data.following,
            "good": is_good_neighbour(uid, username, good_ids, good_names),
            "user": user if user.get("id") else {**user, "id": uid, "username": username, "name": name},
        }

    people = set(likes_c) | set(reposts_c) | set(reply_c) | set(quote_c)
    ranked = Counter()
    order = sorted(people, key=lambda uid: (-points(uid, "both"), -reply_c[uid] - quote_c[uid], uid))
    for uid in order:
        ranked[uid] = points(uid, "both")
    catch_ranked = sorted(people, key=lambda uid: (-points(uid, mode), -reply_c[uid] - quote_c[uid], uid))

    groups = defaultdict(list)
    for item in items:
        groups[item["author_id"]].append(item)
    threads = []
    for uid, group in groups.items():
        group.sort(key=lambda item: item["created_at"], reverse=True)
        threads.append({
            **describe(uid),
            "items": group,
        })
    threads.sort(key=lambda thread: (
        -len(thread["items"]),
        -thread["items"][0]["created_at"].timestamp(),
        thread["username"],
    ))
    if mode == "likes":
        threads = []

    interactions = []
    for uid in people:
        reply_n = 0 if mode == "likes" else reply_c[uid] + quote_c[uid]
        like_n = 0 if mode == "replies" else likes_c[uid]
        repost_n = 0 if mode == "replies" else reposts_c[uid]
        if mode == "likes" and like_n + repost_n == 0:
            continue
        if mode == "replies" and reply_n == 0:
            continue
        if reply_n + like_n + repost_n <= 0:
            continue
        interactions.append({
            **describe(uid),
            "replies": reply_n,
            "likes": like_n,
            "reposts": repost_n,
        })
    interactions.sort(key=lambda row: (
        -(row["replies"] + row["likes"] + row["reposts"]),
        -row["replies"],
        -row["likes"],
        -row["reposts"],
        row["username"],
    ))

    skipped_engaged = []

    def catch_person(uid, fallback=None):
        chosen = None
        saw_engaged = False
        for post in data.originals.get(uid) or []:
            if not is_original_post(post):
                continue
            if str(post["id"]) in data.engaged:
                saw_engaged = True
                continue
            chosen = post
            break
        if chosen is None:
            if saw_engaged:
                skipped_engaged.append(uid)
            return None
        return {
            **describe(uid, fallback),
            "latest": chosen,
            "latest_url": status_url(data, uid, chosen["id"]),
        }

    catch_up = []
    if good:
        for neighbour in good:
            person = catch_person(neighbour["id"], neighbour)
            if person:
                catch_up.append(person)
    else:
        for uid in catch_ranked:
            if points(uid, mode) <= 0:
                continue
            person = catch_person(uid)
            if not person:
                continue
            catch_up.append(person)
            if len(catch_up) >= top:
                break

    return {
        "totals": {
            "replies": sum(1 for item in items if item["kind"] == "reply"),
            "quotes": sum(1 for item in items if item["kind"] == "quote"),
            "likes": sum(likes_c.values()),
            "reposts": sum(reposts_c.values()),
        },
        "threads": threads,
        "interactions": interactions,
        "catch_up": catch_up,
        "ranked": ranked,
        "has_good_neighbours": bool(good),
        "catch_hint": not good,
        "all_caught_up": not catch_up and bool(skipped_engaged),
    }


def owner_zone(name):
    text = (name or "").strip()
    if not text:
        return timezone.utc
    try:
        return ZoneInfo(text)
    except Exception as exc:
        raise SystemExit(f"Unknown timezone: {name}") from exc


def suggest_good_neighbours(activity, neighbours, limit=5, top=10):
    """Up to five people from Flowers who are not already good neighbours."""
    ids, names = good_neighbour_ids(neighbours or [])
    picked = []
    for row in activity["interactions"][:top]:
        if is_good_neighbour(row["id"], row["username"], ids, names):
            continue
        picked.append({
            "id": row["id"],
            "username": row["username"],
            "name": row["name"],
            "label": f"⭐ @{row['username']}",
        })
        if len(picked) >= limit:
            break
    return picked


def user_markdown(person):
    star = " ⭐" if person.get("good") else ""
    mark = " 👤?" if person.get("stranger") else ""
    return f"**{person['name']}**{star} [@{person['username']}](https://x.com/{person['username']}){mark}"


def on_post_line(text):
    text = text or "your post"
    if not text.endswith("…"):
        text += "…"
    return f"↳ on your post: “{text}”"


def write_chat_report(activity, path, handle, since, now, label, top=10, items_per_user=3):
    end = now.astimezone(timezone.utc)
    start = since.astimezone(timezone.utc)
    totals = activity["totals"]
    lines = [
        f"**X Neighbours · @{handle}**",
        f"{label} ({start.strftime('%b %-d')} – {end.strftime('%b %-d')}) · "
        f"💬 {counted(totals['replies'], 'reply', 'replies')} · "
        f"🔁💬 {counted(totals['quotes'], 'quote', 'quotes')} · "
        f"❤️ {counted(totals['likes'], 'like', 'likes')} · "
        f"🔁 {counted(totals['reposts'], 'repost', 'reposts')}",
    ]
    people = activity["threads"] + activity["interactions"] + activity["catch_up"]
    legend = []
    if any(person["stranger"] for person in people):
        legend.append("👤? = you don't follow them yet")
    if activity.get("has_good_neighbours"):
        legend.append("⭐ = good neighbour")
    if legend:
        lines.append(" · ".join(legend))
    lines.append("")
    rows = activity["interactions"][:top]
    if not rows:
        lines.append("No replies, likes, or reposts in this stretch.")
    else:
        lines += ["### 💐 Flowers from your neighbours",
                  "| User | Replies | Likes | Reposts |",
                  "|---|---|---|---|"]
        for row in rows:
            star = " ⭐" if row.get("good") else ""
            mark = " 👤?" if row["stranger"] else ""
            lines.append(
                f"| {row['name']}{star} [@{row['username']}](https://x.com/{row['username']}){mark} "
                f"| {row['replies']} | {row['likes']} | {row['reposts']} |"
            )
        more_rows = len(activity["interactions"]) - len(rows)
        if more_rows:
            lines.append(f"\n+{more_rows} more people")
    lines.append("")
    catch = activity["catch_up"]
    if not catch:
        if activity.get("all_caught_up"):
            lines.append("You're all caught up with your good neighbours 🎉")
        elif activity.get("catch_hint"):
            lines.append("No one to catch up with in this stretch.")
            lines.append("Add people to your good neighbours list to keep up with them here.")
        else:
            lines.append("No recent original posts from your good neighbours.")
    else:
        lines.append("### Catch up with your good neighbours")
        if activity.get("catch_hint"):
            lines.append("Add people to your good neighbours list to keep up with them here.")
            lines.append("Latest posts from the people who engaged with you most.")
        else:
            lines.append("Latest original posts from your good neighbours.")
        for person in catch:
            lines.append(f"- {user_markdown(person)}")
            latest = person["latest"]
            if not latest:
                lines.append("  - No latest post saved yet.")
                continue
            when = ts(latest["created_at"])
            lines.append(
                f"  - “{snippet(latest.get('text')) or 'Post'}” · {ago(when, now)} · "
                f"[Read post]({person['latest_url']})"
            )
    lines.append("")
    threads = activity["threads"][:top]
    if not threads:
        lines.append("No replies or quote posts in this stretch.")
    else:
        lines.append("### 👋 Greetings from your neighbours")
        for thread in threads:
            lines.append(f"- {user_markdown(thread)}")
            shown = thread["items"][:items_per_user]
            for item in shown:
                kind = "Reply" if item["kind"] == "reply" else "Quote"
                state = "Replied" if item["replied"] else "Not replied yet"
                lines.append(
                    f"  - **{kind}** [“{item['text']}”]({item['url']}) · "
                    f"{ago(item['created_at'], now)} · {state}"
                )
                lines.append(f"    - {on_post_line(item['on_text'])}")
            extra = len(thread["items"]) - len(shown)
            if extra:
                lines.append(f"  - +{extra} more")
        more_people = len(activity["threads"]) - len(threads)
        if more_people:
            lines.append(f"- +{more_people} more people")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def write_thanks(path, thanks):
    lines = ["### Thank your neighbours on X", ""]
    if thanks:
        lines.append(thanks["text"])
        lines.append("")
        lines.append(f"[Post your thank-you]({thanks['intent']})")
    else:
        lines.append("No neighbours to thank in this stretch.")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")


def wrap_text(draw, text, face, width):
    words = (text or "").split()
    if not words:
        return [""]
    lines, current = [], ""
    for word in words:
        trial = word if not current else current + " " + word
        if draw.textlength(trial, font=face) <= width:
            current = trial
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_report(activity, path, handle, since, now, label, top=10, thanks=None,
                  picture_path=None):
    from PIL import Image, ImageDraw
    width = 1100
    margin = 36
    inner = width - margin * 2
    ink = (17, 24, 39)
    muted = (100, 116, 139)
    line = (226, 232, 240)
    blue = (37, 99, 235)
    purple = (109, 40, 217)
    rose = (190, 18, 60)
    green = (4, 120, 87)
    orange = (194, 65, 12)
    ok = (21, 128, 61)
    title_font = font(34)
    sub_font = font(16, bold=False)
    section_font = font(22)
    name_font = font(18)
    body_font = font(15, bold=False)
    small_font = font(13, bold=False)
    stat_font = font(26)
    stat_label = font(13, bold=False)
    dummy = ImageDraw.Draw(Image.new("RGB", (1, 1)))

    blocks = []

    def add(height, painter):
        blocks.append((height, painter))

    def header(_draw, _img, y):
        _draw.text((margin, y), f"X Neighbours  ·  @{handle}", font=title_font, fill=ink)
        end = now.astimezone(timezone.utc)
        start = since.astimezone(timezone.utc)
        _draw.text((margin, y + 46),
                   f"{label}  ·  {start.strftime('%b %-d')} – {end.strftime('%b %-d')}",
                   font=sub_font, fill=muted)

    add(84, header)
    totals = activity["totals"]
    stats = [
        (str(totals["replies"]), "Replies", blue),
        (str(totals["quotes"]), "Quote posts", purple),
        (str(totals["likes"]), "Likes", rose),
        (str(totals["reposts"]), "Reposts", green),
    ]

    def stat_row(_draw, _img, y):
        gap = 14
        box_w = (inner - gap * 3) / 4
        for index, (value, caption, color) in enumerate(stats):
            x = margin + index * (box_w + gap)
            _draw.rounded_rectangle((x, y, x + box_w, y + 78), radius=14, fill=(255, 255, 255),
                                    outline=line, width=2)
            _draw.text((x + 16, y + 10), value, font=stat_font, fill=color)
            _draw.text((x + 16, y + 46), caption, font=stat_label, fill=muted)

    add(96, stat_row)

    def legend(_draw, _img, y):
        _draw.rounded_rectangle((margin, y, margin + 22, y + 22), radius=6, fill=(255, 247, 237),
                                outline=orange, width=2)
        _draw.text((margin + 6, y + 2), "?", font=small_font, fill=orange)
        caption = "you don't follow them yet"
        if activity.get("has_good_neighbours"):
            caption += "      ★ = good neighbour"
        _draw.text((margin + 30, y + 2), caption, font=body_font, fill=muted)

    add(40, legend)

    def draw_name(_draw, x, y, person, face):
        _draw.text((x, y), person["name"], font=face, fill=ink)
        used = dummy.textlength(person["name"], font=face)
        if person.get("good"):
            _draw.text((x + used + 6, y), "★", font=face, fill=(180, 83, 9))
            used += 6 + dummy.textlength("★", font=face)
        return x + used

    def section(title, color):
        def paint(_draw, _img, y, title=title, color=color):
            _draw.rounded_rectangle((margin, y, width - margin, y + 42), radius=10, fill=color)
            _draw.text((margin + 16, y + 8), title, font=section_font, fill=(255, 255, 255))
        add(56, paint)

    section("Flowers from your neighbours", rose)

    def table_head(_draw, _img, y):
        _draw.rectangle((margin, y, width - margin, y + 36), fill=(248, 250, 252))
        columns = [(margin + 16, "User"), (inner * 0.58 + margin, "Replies"),
                   (inner * 0.72 + margin, "Likes"), (inner * 0.86 + margin, "Reposts")]
        for x, caption in columns:
            _draw.text((x, y + 8), caption, font=small_font, fill=muted)

    add(36, table_head)
    table_rows = activity["interactions"][:top]
    if not table_rows:
        def empty_table(_draw, _img, y):
            _draw.text((margin + 16, y + 8), "No replies, likes, or reposts in this window.",
                       font=body_font, fill=muted)
        add(36, empty_table)
    for index, row in enumerate(table_rows):
        def paint_row(_draw, img, y, row=row, index=index):
            fill = (255, 255, 255) if index % 2 == 0 else (248, 250, 252)
            _draw.rectangle((margin, y, width - margin, y + 48), fill=fill)
            avatar = fetch_avatar(row["user"], os.path.join(os.path.dirname(path), ".avatar_cache"), 28)
            img.paste(avatar, (margin + 12, y + 10), avatar)
            draw_name(_draw, margin + 48, y + 6, row, name_font)
            handle_text = "@" + row["username"]
            _draw.text((margin + 48, y + 26), handle_text, font=small_font, fill=muted)
            if row["stranger"]:
                mark_x = margin + 48 + dummy.textlength(handle_text + " ", font=small_font)
                _draw.text((mark_x, y + 24), "?", font=small_font, fill=orange)
            _draw.text((inner * 0.58 + margin, y + 14), str(row["replies"]), font=body_font, fill=ink)
            _draw.text((inner * 0.72 + margin, y + 14), str(row["likes"]), font=body_font, fill=ink)
            _draw.text((inner * 0.86 + margin, y + 14), str(row["reposts"]), font=body_font, fill=ink)
        add(48, paint_row)

    section("Catch up with your good neighbours", green)

    def catch_intro(_draw, _img, y):
        if activity.get("has_good_neighbours"):
            text = "Latest original posts from your good neighbours"
        else:
            text = "Add people to your good neighbours list to keep up with them here."
        _draw.text((margin, y), text, font=body_font, fill=muted)

    add(28, catch_intro)
    if not activity["catch_up"]:
        def empty_catch(_draw, _img, y):
            if activity.get("all_caught_up"):
                text = "You're all caught up with your good neighbours."
            elif activity.get("has_good_neighbours"):
                text = "No recent original posts from your good neighbours."
            else:
                text = "No one to catch up with in this window."
            _draw.text((margin, y), text, font=body_font, fill=muted)
        add(28, empty_catch)
    for person in activity["catch_up"]:
        latest = person["latest"]
        text = snippet(latest.get("text")) if latest else "No latest post saved."
        lines = wrap_text(dummy, text, body_font, inner - 70)
        block_h = 36 + 22 * len(lines) + 8

        def paint_catch(_draw, img, y, person=person, lines=lines, latest=latest):
            avatar = fetch_avatar(person["user"], os.path.join(os.path.dirname(path), ".avatar_cache"), 36)
            img.paste(avatar, (margin, y), avatar)
            handle_x = draw_name(_draw, margin + 48, y, person, name_font) + 8
            _draw.text((handle_x, y + 2), "@" + person["username"], font=body_font, fill=muted)
            if person["stranger"]:
                mark_x = handle_x + dummy.textlength("@" + person["username"] + " ", font=body_font)
                _draw.text((mark_x, y + 2), "?", font=small_font, fill=orange)
            text_y = y + 28
            for row in lines:
                _draw.text((margin + 48, text_y), row, font=body_font, fill=ink)
                text_y += 22
            if latest:
                when = ago(ts(latest["created_at"]), now)
                _draw.text((margin + 48, text_y), when + "   ·   Read post", font=small_font, fill=blue)
        add(block_h + 18, paint_catch)

    section("Greetings from your neighbours", blue)
    if not activity["threads"]:
        def empty_threads(_draw, _img, y):
            _draw.text((margin, y), "No replies or quote posts in this window.", font=body_font, fill=muted)
        add(32, empty_threads)
    for thread in activity["threads"]:
        def paint_user(_draw, img, y, thread=thread):
            avatar = fetch_avatar(thread["user"], os.path.join(os.path.dirname(path), ".avatar_cache"), 42)
            img.paste(avatar, (margin, y), avatar)
            handle_x = draw_name(_draw, margin + 54, y, thread, name_font) + 8
            _draw.text((handle_x, y + 2), "@" + thread["username"], font=body_font, fill=muted)
            if thread["stranger"]:
                mark_x = handle_x + dummy.textlength("@" + thread["username"] + "   ", font=body_font)
                _draw.rounded_rectangle((mark_x, y + 2, mark_x + 28, y + 22), radius=6,
                                        fill=(255, 247, 237), outline=orange, width=1)
                _draw.text((mark_x + 8, y + 2), "?", font=small_font, fill=orange)
        add(52, paint_user)
        for item in thread["items"]:
            kind = "Reply" if item["kind"] == "reply" else "Quote"
            kind_color = blue if item["kind"] == "reply" else purple
            state = "Replied" if item["replied"] else "Not replied yet"
            state_color = ok if item["replied"] else orange
            body_lines = wrap_text(dummy, item["text"], body_font, inner - 150)
            on_lines = wrap_text(dummy, "on your post: “" + item["on_text"] + "”", small_font, inner - 80)
            block_h = 36 + 22 * len(body_lines) + 20 * len(on_lines) + 36

            def paint_item(_draw, _img, y, item=item, kind=kind, kind_color=kind_color,
                           state=state, state_color=state_color, body_lines=body_lines, on_lines=on_lines):
                _draw.rounded_rectangle((margin + 54, y, width - margin, y + block_h - 8),
                                        radius=10, fill=(255, 255, 255), outline=line, width=1)
                _draw.rounded_rectangle((margin + 66, y + 10, margin + 66 + dummy.textlength(kind, font=small_font) + 16, y + 30),
                                        radius=6, fill=kind_color)
                _draw.text((margin + 74, y + 11), kind, font=small_font, fill=(255, 255, 255))
                text_y = y + 36
                for row in body_lines:
                    _draw.text((margin + 66, text_y), row, font=body_font, fill=ink)
                    text_y += 22
                for row in on_lines:
                    _draw.text((margin + 78, text_y), row, font=small_font, fill=muted)
                    text_y += 20
                meta = f"{ago(item['created_at'], now)}   ·   {state}"
                _draw.text((margin + 66, text_y), meta, font=small_font, fill=state_color)
            add(block_h, paint_item)

    section("Thank your neighbours on X", (180, 83, 9))
    thank_text = (thanks or {}).get("text") or "Thank you to my X neighbours."
    thumb = None
    if picture_path and os.path.isfile(picture_path):
        with Image.open(picture_path) as src:
            thumb = src.convert("RGB")
            thumb.thumbnail((220, 220))
    text_width = inner - (thumb.width + 24 if thumb else 0)
    thank_lines = wrap_text(dummy, thank_text, body_font, text_width)
    thank_h = max(thumb.height + 16 if thumb else 0, 22 * len(thank_lines) + 36)

    def paint_thanks(_draw, img, y, thank_lines=thank_lines, thumb=thumb):
        text_x = margin
        if thumb is not None:
            img.paste(thumb, (margin, y))
            text_x = margin + thumb.width + 16
        text_y = y
        for row in thank_lines:
            _draw.text((text_x, text_y), row, font=body_font, fill=ink)
            text_y += 22
        _draw.text((text_x, text_y + 8), "Post your thank-you", font=small_font, fill=blue)

    add(thank_h, paint_thanks)

    height = 28 + sum(block[0] for block in blocks) + 24
    image = Image.new("RGB", (width, height), (241, 245, 249))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((18, 18, width - 18, height - 18), radius=18, fill=(255, 255, 255))
    y = 32
    for block_h, painter in blocks:
        painter(draw, image, y)
        y += block_h
    image.save(path, optimize=True)


WEEKLY_FEEDBACK = (
    "Anything you'd change about X Neighbours? "
    "Tell me and I'll turn it into a feedback link."
)


def thank_you_post(when, zone):
    """Thank-you text with the report date. It never names anyone."""
    local = when.astimezone(zone)
    day = local.strftime("%B %-d")
    text = (
        f"My X neighbours circle, {day}! Thank you all for being here "
        "and taking the time to reply to my posts. I really appreciate it!"
    )
    return text, "https://x.com/intent/post?text=" + urllib.parse.quote(text)


def extra_sections(data, since, now, handle, top, like_weight, reply_weight, per_post, per_day):
    lines = []
    if per_day:
        lines += ["### Per day", ""]
        for day, day_start, day_end in each_utc_day(since, now):
            activity = build_activity(data, day_start, day_end, top, like_weight, reply_weight, "both", now)
            totals = activity["totals"]
            lines.append(
                f"- **{day.isoformat()}** — {totals['replies']} replies, {totals['quotes']} quotes, "
                f"{totals['likes']} likes, {totals['reposts']} reposts"
            )
        lines.append("")
    if per_post:
        lines += ["### Per post", ""]
        posts = []
        for pid, post in data.posts.items():
            if data._in_window(post.get("created_at"), since, now):
                posts.append((ts(post["created_at"]), pid, post))
        posts.sort(reverse=True)
        if not posts:
            lines.append("No posts in this window.")
        for when, pid, post in posts:
            likes = sum(1 for uid in data.likes.get(pid, []) if not hidden_user(data, uid))
            reposts = sum(1 for uid in data.reposts.get(pid, []) if not hidden_user(data, uid))
            text = snippet(post.get("text")) or "Post"
            lines.append(
                f"- {when.strftime('%Y-%m-%d %H:%M UTC')} — {text} — "
                f"{likes} likes, {reposts} reposts — https://x.com/{handle}/status/{pid}"
            )
        lines.append("")
    return "\n".join(lines)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        description="Build an X Neighbours report, and sometimes the neighbours picture."
    )
    parser.add_argument("--config", default=os.path.join(here, "config.json"))
    parser.add_argument("--handle")
    parser.add_argument("--user-id", dest="user_id")
    parser.add_argument("--data", default=os.path.join(here, "data"))
    parser.add_argument("--out", default=here)
    parser.add_argument("--now", help="UTC ISO time the data was fetched (default: now)")
    parser.add_argument("--like-weight", dest="like_weight", type=float)
    parser.add_argument("--reply-weight", dest="reply_weight", type=float)
    parser.add_argument("--exclude", help="comma-separated handles to drop; '' for none")
    parser.add_argument("--rings", type=int)
    parser.add_argument("--top", type=int)
    parser.add_argument("--theme", choices=sorted(THEMES))
    parser.add_argument("--windows", help="comma-separated: day,week")
    parser.add_argument("--report", choices=REPORTS,
                        help="likes, replies, or both (default both)")
    parser.add_argument("--per-post", dest="per_post", action=argparse.BooleanOptionalAction,
                        default=None, help="add a per-post breakdown")
    parser.add_argument("--per-day", dest="per_day", action=argparse.BooleanOptionalAction,
                        default=None, help="add a per-day breakdown to the markdown")
    parser.add_argument("--days", type=int, help="custom period length in days")
    parser.add_argument("--since", help="UTC ISO start for a fresh report since the last one")
    parser.add_argument("--state", help="path to state.json in the bot store")
    parser.add_argument("--timezone", help="IANA timezone for the thank-you date, such as Europe/Stockholm")
    parser.add_argument("--fresh-hours", dest="fresh_hours", type=float,
                        help="owner override for how many hours a report stays fresh")
    parser.add_argument("--first-run", action="store_true",
                        help="report the last first_run_days and always draw the picture")
    parser.add_argument("--report-card", action="store_true",
                        help="also write the report card PNG (off by default)")
    parser.add_argument("--picture", dest="picture", action=argparse.BooleanOptionalAction,
                        default=None, help="include the neighbours picture (default: every report)")
    parser.add_argument("--show-names", dest="show_names", action="store_true", default=None)
    parser.add_argument("--hide-names", dest="show_names", action="store_false")
    parser.add_argument("--no-image", action="store_true")
    parser.add_argument("--good-neighbours", dest="good_neighbours",
                        help="path to the personal good neighbours JSON; a missing file is an empty list")
    args = parser.parse_args()
    cfg = dict(DEFAULTS)
    if os.path.exists(args.config):
        with open(args.config, encoding="utf-8") as fh:
            loaded = json.load(fh)
        if not isinstance(loaded, dict):
            parser.error(f"{args.config} must contain a JSON object")
        cfg.update(loaded)
    for key in DEFAULTS:
        value = getattr(args, key, None)
        if value is not None:
            cfg[key] = as_list(value) if key in ("exclude", "windows") else value
    cfg["exclude"] = [item.lstrip("@") for item in as_list(cfg.get("exclude"))]
    cfg["windows"] = as_list(cfg.get("windows"))
    if not cfg["handle"] or not cfg["user_id"]:
        parser.error("handle and user_id are required (config.json or --handle/--user-id)")
    cfg["handle"] = str(cfg["handle"]).lstrip("@")
    unknown = [name for name in cfg["windows"] if name not in WINDOWS]
    if unknown:
        parser.error("windows must be day, week, or both")
    rings = int(cfg["rings"])
    if not 1 <= rings <= 4:
        parser.error("rings must be from 1 to 4")
    cfg["rings"] = rings
    top = int(cfg["top"])
    if top < 1:
        parser.error("top must be at least 1")
    cfg["top"] = top
    if cfg["theme"] not in THEMES:
        parser.error("theme must be midnight, light, or sunset")
    cfg["show_names"] = as_bool(cfg["show_names"])
    cfg["per_post"] = as_bool(cfg.get("per_post"))
    cfg["per_day"] = as_bool(cfg.get("per_day"))
    if cfg.get("report") not in REPORTS:
        parser.error("report must be likes, replies, or both")
    needs_pillow = args.report_card or args.picture is not False
    if needs_pillow and not args.no_image:
        try:
            import PIL  # noqa: F401
        except ImportError:
            sys.exit("Pillow is required to draw the picture. "
                     "Install it with: python3 -m pip install -r requirements.txt")
    if not os.path.isdir(args.data):
        parser.error(f"data folder not found: {args.data}")
    os.makedirs(args.out, exist_ok=True)
    like_weight = whole_number(cfg["like_weight"])
    reply_weight = whole_number(cfg["reply_weight"])
    me_id = str(cfg["user_id"])
    now = ts(args.now) if args.now else datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    data = Data(args.data, me_id)
    data.exclude = {handle.lower() for handle in cfg["exclude"]}
    neighbours = load_good_neighbours(cfg.get("good_neighbours"))
    me = {"id": me_id, "username": cfg["handle"]}
    stored = data.users.get(me_id, {})
    me.update({k: v for k, v in stored.items() if v not in (None, "")})
    output = {}
    mode = cfg["report"]
    if args.since:
        since_at = ts(args.since)
        if since_at.tzinfo is None:
            since_at = since_at.replace(tzinfo=timezone.utc)
        if since_at >= now:
            parser.error("--since must be earlier than --now")
        windows = [("fresh", since_at, "Since your last report")]
    elif args.first_run:
        first_days = int(cfg.get("first_run_days") or 2)
        if first_days < 1:
            parser.error("first_run_days must be at least 1")
        windows = [("first", first_days, f"Last {first_days} days")]
        if args.picture is None:
            args.picture = True
    elif args.days:
        if args.days < 1:
            parser.error("days must be at least 1")
        windows = [("custom", args.days, f"Last {args.days} days")]
    else:
        windows = [
            (key, days, label) for key, (label, days, _subtitle) in (
                (name, WINDOWS[name]) for name in cfg["windows"]
            )
        ]
    zone = owner_zone(cfg.get("timezone"))
    for key, span, label in windows:
        since = span if isinstance(span, datetime) else now - timedelta(days=span)
        activity = build_activity(
            data, since, now, cfg["top"], like_weight, reply_weight, mode, now,
            good_neighbours=neighbours)
        md_path = os.path.join(args.out, f"report_{key}.md")
        png_path = os.path.join(args.out, f"report_{key}.png")
        text, intent = thank_you_post(now, zone)
        thanks = {"text": text, "intent": intent, "link_label": "Post your thank-you"}
        draw_picture = args.picture is not False and not args.no_image
        picture_path = None
        if draw_picture:
            picture_path = os.path.join(args.out, f"x_neighbours_{key}.png")
            draw_circle(
                data, me, activity["ranked"], picture_path,
                rings=cfg["rings"], show_names=cfg["show_names"],
                subtitle=SUBTITLES["both"].get(key, f"Top neighbours, {label.lower()}"),
                theme=cfg["theme"])
        thanks_path = os.path.join(args.out, f"report_{key}_thanks.md")
        write_chat_report(
            activity, md_path, cfg["handle"], since, now, label,
            top=cfg["top"], items_per_user=int(cfg.get("items_per_user") or 3))
        write_thanks(thanks_path, thanks)
        if key == "week":
            with open(thanks_path, "a", encoding="utf-8") as fh:
                fh.write("\n" + WEEKLY_FEEDBACK + "\n")
        if cfg["per_post"] or cfg["per_day"]:
            with open(md_path, "a", encoding="utf-8") as fh:
                fh.write("\n" + extra_sections(
                    data, since, now, cfg["handle"], cfg["top"], like_weight, reply_weight,
                    cfg["per_post"], cfg["per_day"]) + "\n")
        if args.report_card and not args.no_image:
            render_report(
                activity, png_path, cfg["handle"], since, now, label,
                top=cfg["top"], thanks=thanks, picture_path=picture_path)
        output[key] = {
            "replies": activity["totals"]["replies"],
            "quotes": activity["totals"]["quotes"],
            "likes": activity["totals"]["likes"],
            "reposts": activity["totals"]["reposts"],
            "catch_up": ["@" + person["username"] for person in activity["catch_up"]],
            "since": since.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "until": now.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "report_md": md_path,
            "thanks_md": thanks_path,
            "thank_you": thanks,
            "messages": [
                {"part": "sections_1_to_3", "text_file": md_path, "images": []},
                {
                    "part": "section_4",
                    "text_file": thanks_path,
                    "text": thanks["text"],
                    "link_label": "Post your thank-you",
                    "intent": thanks["intent"],
                    "images": [picture_path] if picture_path else [],
                },
            ],
        }
        if cfg.get("state"):
            import report_state
            report_state.record(
                cfg["state"], at=now, since=since, until=now,
                replies=activity["totals"]["replies"],
                quotes=activity["totals"]["quotes"],
                likes=activity["totals"]["likes"],
                reposts=activity["totals"]["reposts"],
                override=cfg.get("fresh_hours"))
        if key == "week":
            output[key]["feedback_line"] = WEEKLY_FEEDBACK
        else:
            suggestions = suggest_good_neighbours(
                activity, neighbours, top=cfg["top"])
            if suggestions:
                output[key]["suggest_good_neighbours"] = suggestions
                output[key]["add_question"] = {
                    "label": "⭐ Add",
                    "prompt": "Add to good neighbours?",
                    "options": [person["label"] for person in suggestions],
                    "free_text": "Or name anyone else",
                }
        if args.report_card and not args.no_image:
            output[key]["report_png"] = png_path
        if picture_path:
            output[key]["picture"] = picture_path
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
