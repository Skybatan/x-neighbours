#!/usr/bin/env python3
"""X Neighbours: rank who liked and replied to an account, tag relationships,
suggest follow-backs, and draw a shareable picture.

Settings come from config.json. CLI flags override it. The script does not call X.
It reads raw JSON saved from X tool calls (see README.md) in the data folder:

  posts_*.json        get_users_posts pages (expansions=author_id)
  mentions_*.json     get_users_mentions pages (expansions=author_id)
  likes_<postid>.json get_posts_liking_users, one post per file stem
                      (likes_<postid>_p2.json is merged into the same post)
  followers_*.json    get_users_me_followers pages
  following_*.json    get_users_me_following pages

Usage:
  python3 x_neighbours.py --handle your_handle --user-id your_user_id
                      [--data data] [--out .] [--now 2026-11-04T18:00:00Z]
                      [--rings 3] [--top 10]
                      [--report likes|replies|both] [--per-post] [--per-day]
"""
import argparse
import glob
import json
import math
import os
import re
import sys
import urllib.request
from collections import Counter
from datetime import datetime, timedelta, timezone


def load(pattern):
    out = []
    for f in sorted(glob.glob(pattern)):
        with open(f, encoding="utf-8") as fh:
            try:
                out.append((f, json.load(fh)))
            except json.JSONDecodeError as exc:
                raise SystemExit(f"{f} is not JSON ({exc})") from exc
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


def like_count(post):
    return (post.get("public_metrics") or {}).get("like_count", 0) or 0


def impression_count(post):
    metrics = post.get("public_metrics") or {}
    value = metrics.get("impression_count")
    if value is None:
        return None
    return int(value)


def fmt_int(n):
    return f"{int(n):,}"


def impression_rows(data, since, until=None):
    rows = []
    for pid, post in data.posts.items():
        if not data._in_window(post.get("created_at"), since, until):
            continue
        count = impression_count(post)
        if count is None:
            continue
        rows.append((count, ts(post["created_at"]), pid, post))
    rows.sort(key=lambda row: (row[0], row[1]), reverse=True)
    return rows


def impression_change(total, previous):
    delta = total - previous
    if previous:
        percent = round(100 * delta / previous)
        if delta > 0:
            return f"up {fmt_int(delta)} ({percent}%)"
        if delta < 0:
            return f"down {fmt_int(-delta)} ({abs(percent)}%)"
        return "unchanged"
    if delta > 0:
        return f"up {fmt_int(delta)}"
    if delta < 0:
        return f"down {fmt_int(-delta)}"
    return "unchanged"


def impression_summary(data, since, days, handle):
    current = impression_rows(data, since)
    if not current:
        return None
    total = sum(count for count, *_rest in current)
    previous_rows = impression_rows(data, since - timedelta(days=days), since)
    payload = {
        "total": total,
        "top": [{
            "impressions": count,
            "text": snippet(post.get("text")),
            "url": f"https://x.com/{handle}/status/{pid}",
        } for count, _when, pid, post in current[:3]],
    }
    if previous_rows:
        previous = sum(count for count, *_rest in previous_rows)
        payload["previous"] = previous
        payload["change"] = total - previous
    return payload


def append_impressions(lines, data, since, days, handle):
    payload = impression_summary(data, since, days, handle)
    if not payload:
        lines += ["## Impressions", "",
                  "Impression counts were not in the saved posts.", ""]
        return None
    period = "24 hours" if days == 1 else "7 days"
    if "previous" in payload:
        movement = impression_change(payload["total"], payload["previous"])
        summary = f"{fmt_int(payload['total'])} impressions, {movement} from the previous {period}."
    else:
        summary = f"{fmt_int(payload['total'])} impressions."
    lines += ["## Impressions", "", summary, "", "Top posts by impressions:", ""]
    for post in payload["top"]:
        title = post["text"] or "Post"
        lines.append(f"- {fmt_int(post['impressions'])} — {title} — {post['url']}")
    lines.append("")
    return payload


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


def append_per_day(lines, data, since, until, top, like_weight, reply_weight, report):
    lines += ["## Per day", ""]
    for day, day_start, day_end in each_utc_day(since, until):
        likes, replies = data.window(day_start, day_end)
        use_likes, use_replies = active_counts(likes, replies, report)
        ranked = score(use_likes, use_replies, like_weight, reply_weight)
        lines += [f"### {day.isoformat()} UTC", ""]
        if not use_likes and not use_replies:
            lines += ["No likes or replies.", ""]
            continue
        if report != "replies":
            append_table(lines, "Likers", likes, "likes", ranked, data, top, level=4)
        if report != "likes":
            append_table(lines, "Repliers", replies, "replies", ranked, data, top, level=4)


def replies_for_post(data, pid, since, until):
    counts = Counter()
    for mention in data.mentions:
        author = mention.get("author_id")
        if not kept_user(data, author):
            continue
        if not data._in_window(mention.get("created_at"), since, until):
            continue
        refs = [ref.get("id") for ref in mention.get("referenced_tweets") or []
                if ref.get("type") == "replied_to"]
        if pid in refs:
            counts[author] += 1
    return counts


def append_per_post(lines, data, since, until, handle, report):
    lines += ["## Per post", ""]
    posts = []
    for pid, post in data.posts.items():
        if data._in_window(post.get("created_at"), since, until):
            posts.append((ts(post["created_at"]), pid, post))
    posts.sort(reverse=True)
    tied = Counter()
    for mention in data.mentions:
        author = mention.get("author_id")
        if not kept_user(data, author):
            continue
        if not data._in_window(mention.get("created_at"), since, until):
            continue
        refs = [ref.get("id") for ref in mention.get("referenced_tweets") or []
                if ref.get("type") == "replied_to" and ref.get("id") in data.posts]
        if refs:
            continue
        if mention.get("in_reply_to_user_id") == data.me:
            tied[author] += 1
    if not posts:
        lines += ["No posts in this window.", ""]
    for when, pid, post in posts:
        lines += [f"### {when.strftime('%Y-%m-%d %H:%M UTC')}", ""]
        text = snippet(post.get("text"))
        if text:
            lines += [text, ""]
        lines += [f"https://x.com/{handle}/status/{pid}", ""]
        if report != "replies":
            likers = [uid for uid in data.likes.get(pid, []) if kept_user(data, uid)]
            names = ", ".join(display_name(data, uid) for uid in likers) or "none"
            lines.append(f"Likes ({len(likers)}): {names}")
        if report != "likes":
            repliers = replies_for_post(data, pid, since, until)
            ordered = [display_name(data, uid) for uid, _count in repliers.most_common()]
            names = ", ".join(ordered) or "none"
            total = sum(repliers.values())
            lines.append(f"Replies ({total}): {names}")
        lines.append("")
    if report != "likes" and tied:
        names = ", ".join(f"{display_name(data, uid)} ({count})"
                          for uid, count in tied.most_common())
        lines += ["Replies in this window that are not tied to one of these posts: " + names, ""]


def write_report(data, label, since, path, top, handle, like_weight=1, reply_weight=3,
                 report="both", per_post=False, per_day=False, until=None,
                 impressions=True, days=7):
    likes, replies = data.window(since)
    use_likes, use_replies = active_counts(likes, replies, report)
    ranked = score(use_likes, use_replies, like_weight, reply_weight)
    own_posts = sum(1 for post in data.posts.values()
                    if data._in_window(post.get("created_at"), since, None))
    lines = [
        f"# X Neighbours: @{handle}, {label}",
        "",
        f"Window: since {since.strftime('%Y-%m-%d %H:%M UTC')}. "
        f"Own posts in window: {own_posts}.",
        "",
    ]
    impression_payload = None
    if impressions:
        impression_payload = append_impressions(lines, data, since, days, handle)
    if report != "replies":
        append_table(lines, "Top likers", likes, "likes", ranked, data, top)
    if report != "likes":
        append_table(lines, "Top repliers", replies, "replies", ranked, data, top)
    suggestions = [(uid, count) for uid, count in ranked.most_common()
                   if uid not in data.following and uid in data.users][:5]
    if report == "likes":
        intro = "People who liked often but you don't follow:"
    elif report == "replies":
        intro = "People who replied often but you don't follow:"
    else:
        intro = "People who liked or replied often but you don't follow:"
    lines += ["## Follow-back suggestions", "", intro, ""]
    for uid, _count in suggestions:
        user = data.users[uid]
        lines.append(
            f"- {link(user)} (score {ranked[uid]}: {suggestion_detail(report, likes, replies, uid)}, "
            f"{data.relation(uid)}): {summary(user)}"
        )
    if not suggestions:
        lines.append("- none")
    lines.append("")
    if per_day and until is not None:
        append_per_day(lines, data, since, until, top, like_weight, reply_weight, report)
    if per_post:
        append_per_post(lines, data, since, until, handle, report)
    short = []
    for pid, _got, _want in data.likes_truncated:
        created = (data.posts.get(pid) or {}).get("created_at")
        if data._in_window(created, since, None):
            short.append(pid)
    missing = 0
    for pid, post in data.posts.items():
        if not data._in_window(post.get("created_at"), since, None):
            continue
        if like_count(post) > 0 and pid not in data.likes:
            missing += 1
    lines += [
        "## Notes",
        "",
        "- Likes come from each post's liker list, which can be a few short of the like count "
        "(deleted, suspended or protected likers).",
        f"- Posts whose liker list was shorter than the like count: {len(short)}.",
        "- Posts with likes whose liker list was not fetched: "
        f"{missing}.",
    ]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    return likes, replies, suggestions, ranked, impression_payload


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
    """Fractions of the canvas. Four rings leave a gap under each avatar for its name."""
    if rings >= 4:
        return {
            "cy": 0.545,
            "centre": 0.118,
            "per_ring": [8, 14, 20, 26],
            "radius": [0.150, 0.248, 0.340, 0.430],
            "size": [0.062, 0.048, 0.038, 0.031],
            # Wider pills on the inner rings, where neighbours are further apart.
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
    layout = ring_geometry(rings)
    cx, cy = canvas_size // 2, int(canvas_size * layout["cy"])
    per_ring = layout["per_ring"]
    radius = [canvas_size * r for r in layout["radius"]]
    avatar_size = [int(canvas_size * s) for s in layout["size"]]
    ranked = [uid for uid, _points in scores.most_common()
              if uid in data.users and uid != data.me]
    for orbit in radius:
        draw.ellipse((cx - orbit, cy - orbit, cx + orbit, cy + orbit),
                     outline=theme_colors["orbit"], width=2 * scale)
    name_font = [font(max(12, int(size * 0.17))) for size in avatar_size]
    index = 0
    for ring_index in range(rings):
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
            draw.ellipse((x - size / 2 - pad, y - size / 2 - pad, x + size / 2 + pad, y + size / 2 + pad),
                         fill=ring_color)
            avatar = fetch_avatar(data.users[uid], cache, size)
            canvas.alpha_composite(avatar, (int(x - size / 2), int(y - size / 2)))
            if show_names:
                label = "@" + data.users[uid].get("username", "")
                face = name_font[ring_index]
                wedge = 2 * radius[ring_index] * math.sin(math.pi / max(count, 1))
                limit = min(size * layout["name_width"][ring_index], wedge * 0.92)
                draw_label(draw, label, face, x, y + size / 2 + 4 * scale, limit,
                           theme_colors["label_bg"], theme_colors["label"], scale)
    centre = int(canvas_size * layout["centre"])
    for grow, alpha in ((26, 40), (16, 80), (8, 160)):
        draw.ellipse((cx - centre / 2 - grow * scale, cy - centre / 2 - grow * scale,
                      cx + centre / 2 + grow * scale, cy + centre / 2 + grow * scale),
                     fill=theme_colors["ring0"][:3] + (alpha,))
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
    "impressions": True,
    "show_names": True,
    "theme": "midnight",
    "windows": ["week"],
    "top": 10,
    "report": "both",
    "per_post": False,
    "per_day": False,
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


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    parser = argparse.ArgumentParser(
        description="Rank who liked and replied to an X account, and draw an X Neighbours image."
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
                        default=None, help="add a per-day breakdown")
    parser.add_argument("--impressions", dest="impressions", action=argparse.BooleanOptionalAction,
                        default=None, help="show impression totals from your own posts (default on)")
    parser.add_argument("--show-names", dest="show_names", action="store_true", default=None)
    parser.add_argument("--hide-names", dest="show_names", action="store_false")
    parser.add_argument("--no-image", action="store_true")
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
    cfg["impressions"] = as_bool(cfg.get("impressions", True))
    if cfg.get("report") not in REPORTS:
        parser.error("report must be likes, replies, or both")
    if not args.no_image:
        try:
            import PIL  # noqa: F401
        except ImportError:
            sys.exit("Pillow is required to draw the image. "
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
    me = {"id": me_id, "username": cfg["handle"]}
    stored = data.users.get(me_id, {})
    me.update({k: v for k, v in stored.items() if v not in (None, "")})
    output = {}
    report = cfg["report"]
    for key in cfg["windows"]:
        label, days, _subtitle = WINDOWS[key]
        since = now - timedelta(days=days)
        likes, replies, suggestions, ranked, impression_payload = write_report(
            data, label, since,
            os.path.join(args.out, f"report_{key}.md"),
            cfg["top"], cfg["handle"], like_weight, reply_weight,
            report=report, per_post=cfg["per_post"], per_day=cfg["per_day"], until=now,
            impressions=cfg["impressions"], days=days)
        if not args.no_image:
            draw_circle(
                data, me, ranked, os.path.join(args.out, f"x_neighbours_{key}.png"),
                rings=cfg["rings"], show_names=cfg["show_names"],
                subtitle=SUBTITLES[report][key], theme=cfg["theme"])

        def display(uid):
            return "@" + data.users.get(uid, {}).get("username", uid)

        output[key] = {
            "likes": [(display(uid), count) for uid, count in likes.most_common(5)],
            "replies": [(display(uid), count) for uid, count in replies.most_common(5)],
            "follow_back": [display(uid) for uid, _count in suggestions],
            "inner": [(display(uid), points) for uid, points in ranked.most_common(8)],
        }
        if impression_payload:
            output[key]["impressions"] = impression_payload
    print(json.dumps(output, ensure_ascii=False))


if __name__ == "__main__":
    main()
