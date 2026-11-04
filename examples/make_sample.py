#!/usr/bin/env python3
"""Write a fictional X Neighbours dataset under examples/sample/.

Every handle, post, and avatar is made up. Nothing here is a real X account.
The timestamps are frozen. Render them with --now 2026-11-04T18:00:00Z.
"""
import colorsys
import json
import os
import shutil

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "examples", "sample")
ME = "900001"
NOW = "2026-11-04T18:00:00Z"
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

# week_likes includes day_likes. week_replies includes day_replies.
# relation: mutual, follows-you, you-follow, neither.
PEOPLE = [
    ("nova_lane", "910001", "Nova Lane", "mutual", 3, 5, 2, 4, "Draws paper maps of imaginary streets.", 1840, 920),
    ("amber_kiln", "910002", "Amber Kiln", "mutual", 2, 4, 1, 3, "Fires small cups and keeps the cracked ones.", 640, 410),
    ("pixel_otter", "910003", "Pixel Otter", "follows-you", 4, 8, 0, 1, "Builds tiny games about weather.", 12800, 2300),
    ("quiet_comet", "910004", "Quiet Comet", "you-follow", 1, 2, 1, 2, "Night-sky notes from a rooftop desk.", 980, 1500),
    ("moss_radio", "910005", "Moss Radio", "neither", 2, 5, 0, 1, "A one-room station for long songs.", 430, 260),
    ("cedar_loop", "910006", "Cedar Loop", "neither", 0, 1, 1, 2, "Walks the same trail and writes it down.", 210, 880),
    ("drift_paper", "910007", "Drift Paper", "follows-you", 2, 4, 1, 1, "Folds boats out of old schedules.", 1560, 640),
    ("velvet_axis", "910008", "Velvet Axis", "mutual", 1, 3, 0, 1, "Designs posters for plays that do not exist.", 3200, 1100),
    ("tin_harbor", "910009", "Tin Harbor", "you-follow", 0, 3, 0, 1, "Collects harbour bells and their recordings.", 740, 390),
    ("glass_meadow", "910010", "Glass Meadow", "you-follow", 1, 2, 0, 1, "Photographs greenhouses in winter.", 510, 720),
    ("paper_kite", "910011", "Paper Kite", "follows-you", 1, 2, 0, 1, "Flies kites when the forecast is boring.", 260, 190),
    ("low_orbit", "910012", "Low Orbit", "neither", 2, 4, 0, 0, "Keeps a log of satellites anyone can see.", 8900, 3400),
    ("north_spoon", "910013", "North Spoon", "follows-you", 1, 3, 0, 0, "Recipes that start with whatever is left.", 150, 80),
    ("echo_marsh", "910014", "Echo Marsh", "mutual", 0, 2, 0, 0, "Records frogs and answers them.", 670, 540),
    ("kiln_static", "910015", "Kiln Static", "neither", 1, 2, 0, 0, "Short songs made from pottery sounds.", 90, 40),
    ("blue_ladle", "910016", "Blue Ladle", "you-follow", 0, 1, 0, 0, "Soup on Sundays, notes on Mondays.", 300, 210),
    ("harbor_mint", "910017", "Harbor Mint", "follows-you", 0, 1, 0, 0, "Grows herbs in tins on a windowsill.", 120, 70),
    ("copper_sail", "910018", "Copper Sail", "neither", 0, 1, 0, 0, "Mends small boats and longer stories.", 2100, 980),
    ("odd_thermos", "910019", "Odd Thermos", "you-follow", 0, 1, 0, 0, "Tea reviews nobody asked for.", 75, 360),
    ("plum_vector", "910020", "Plum Vector", "mutual", 0, 1, 0, 0, "Draws arrows until the page looks finished.", 540, 610),
    ("sand_ledger", "910021", "Sand Ledger", "neither", 0, 1, 0, 0, "Counts waves and does not publish the total.", 48, 22),
    ("marble_ink", "910022", "Marble Ink", "follows-you", 0, 1, 0, 0, "Lettering practice on scrap stone.", 410, 255),
    ("frost_pantry", "910023", "Frost Pantry", "you-follow", 0, 1, 0, 0, "What kept in a cold kitchen this week.", 188, 140),
    ("linen_radar", "910024", "Linen Radar", "neither", 0, 1, 0, 0, "Watches laundry like it might signal.", 96, 64),
    ("pebble_choir", "910025", "Pebble Choir", "mutual", 0, 1, 0, 0, "A club for people who collect smooth stones.", 1320, 470),
    ("kite_window", "910026", "Kite Window", "follows-you", 0, 1, 0, 0, "Office window, paper kite, long meeting.", 230, 175),
    ("rust_library", "910027", "Rust Library", "neither", 0, 1, 0, 0, "Shelves of manuals for machines long gone.", 860, 1900),
    ("calm_voltage", "910028", "Calm Voltage", "you-follow", 0, 1, 0, 0, "Quiet notes on batteries and bicycles.", 305, 280),
    ("paper_orchard", "910029", "Paper Orchard", "neither", 0, 1, 0, 0, "Prints fruit labels for trees not planted.", 142, 98),
    ("bright_parcel", "910030", "Bright Parcel", "follows-you", 0, 1, 0, 0, "Sends friends boxes of odd stationery.", 5100, 760),
]

EXTRAS = [
    ("grok", "910099", "Grok", "neither", "A bot account the sample excludes."),
    ("old_signal", "910091", "Old Signal", "neither", "Only liked a post from outside the week."),
    ("late_echo", "910092", "Late Echo", "neither", "Replied before the week began."),
    ("side_mention", "910093", "Side Mention", "neither", "Mentioned the sample account without replying to it."),
    ("still_porch", "910031", "Still Porch", "mutual", "Follows both ways and did not engage this week."),
    ("idle_creek", "910032", "Idle Creek", "follows-you", "Follows the sample account and stayed quiet."),
    ("kept_lantern", "910033", "Kept Lantern", "you-follow", "The sample account follows them. No likes or replies."),
]

DAY_POSTS = [
    ("8001", "2026-11-04T08:00:00Z", "Sketched a paper neighbourhood and a ring of chairs."),
    ("8002", "2026-11-04T11:30:00Z", "The kettle won the argument. The drawing can wait."),
    ("8003", "2026-11-04T15:10:00Z", "Left a blank circle in the middle of the map on purpose."),
    ("8004", "2026-11-03T20:00:00Z", "Tonight's margin notes are mostly arrows."),
]
WEEK_POSTS = [
    ("8005", "2026-11-02T13:00:00Z", "Tried a sunset palette on a midnight sketch."),
    ("8006", "2026-11-01T09:40:00Z", "Three rings, then stop. The fourth ring is for later."),
    ("8007", "2026-10-30T18:20:00Z", "Named the streets after kitchen objects."),
    ("8008", "2026-10-29T07:15:00Z", "A week of small replies is a good week."),
]
OLD_POST = ("8009", "2026-10-20T12:00:00Z", "This post is older than the sample week and should not count.")

SHAPES = ("circle", "diamond", "square", "ring")


def rgb(hue, sat, val):
    r, g, b = colorsys.hsv_to_rgb(hue % 1.0, sat, val)
    return tuple(int(channel * 255) for channel in (r, g, b))


def avatar(path, letter, hue, shape):
    image = Image.new("RGB", (400, 400), rgb(hue, 0.35, 0.28))
    draw = ImageDraw.Draw(image)
    ink = rgb(hue, 0.45, 0.82)
    accent = rgb(hue + 0.08, 0.55, 0.95)
    if shape == "circle":
        draw.ellipse((78, 78, 322, 322), fill=ink)
        draw.ellipse((148, 148, 252, 252), fill=accent)
    elif shape == "diamond":
        draw.polygon([(200, 48), (352, 200), (200, 352), (48, 200)], fill=ink)
        draw.polygon([(200, 120), (280, 200), (200, 280), (120, 200)], fill=accent)
    elif shape == "square":
        draw.rounded_rectangle((84, 84, 316, 316), radius=48, fill=ink)
        draw.rounded_rectangle((150, 150, 250, 250), radius=24, fill=accent)
    else:
        draw.ellipse((70, 70, 330, 330), outline=ink, width=36)
        draw.ellipse((150, 150, 250, 250), fill=accent)
    face = ImageFont.truetype(FONT, 120)
    width = draw.textlength(letter, font=face)
    draw.text(((400 - width) / 2, 250), letter, font=face, fill=(255, 255, 255))
    image.save(path, optimize=True)


def user_obj(username, uid, name, description, followers, posts, hue, shape):
    return {
        "id": uid,
        "name": name,
        "username": username,
        "description": description,
        "profile_image_url": f"avatars/{uid}.png",
        "public_metrics": {"followers_count": followers, "tweet_count": posts},
        "_hue": hue,
        "_shape": shape,
    }


def public_user(user):
    return {k: v for k, v in user.items() if not k.startswith("_")}


def dump(name, payload):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def assign(people, day_posts, week_posts):
    by_id = {person["id"]: person for person in people}
    day_likers = {pid: [] for pid, *_rest in day_posts}
    week_likers = {pid: [] for pid, *_rest in week_posts}
    day_ids = [pid for pid, *_rest in day_posts]
    week_ids = [pid for pid, *_rest in week_posts]
    for person in people:
        for bucket, ids, count in (
            (day_likers, day_ids, person["day_likes"]),
            (week_likers, week_ids, person["week_likes"] - person["day_likes"]),
        ):
            placed = 0
            for pid in ids:
                if placed >= count:
                    break
                if person["id"] not in bucket[pid]:
                    bucket[pid].append(person["id"])
                    placed += 1
            if placed < count:
                raise SystemExit(f"not enough posts to place likes for @{person['username']}")
    return by_id, day_likers, week_likers


def main():
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "avatars"))
    people = []
    for index, row in enumerate(PEOPLE):
        username, uid, name, relation, day_l, week_l, day_r, week_r, bio, followers, posts = row
        people.append({
            "id": uid,
            "username": username,
            "name": name,
            "relation": relation,
            "day_likes": day_l,
            "week_likes": week_l,
            "day_replies": day_r,
            "week_replies": week_r,
            "description": bio,
            "followers": followers,
            "posts": posts,
            "hue": (index * 0.137) % 1.0,
            "shape": SHAPES[index % len(SHAPES)],
        })
    grok = {
        "id": "910099", "username": "grok", "name": "Grok", "relation": "neither",
        "day_likes": 1, "week_likes": 3, "day_replies": 0, "week_replies": 1,
        "description": "Bot account included so the sample can show that exclude works.",
        "followers": 1, "posts": 1, "hue": 0.02, "shape": "square",
    }
    engaged = people + [grok]
    by_id, day_likers, week_likers = assign(engaged, DAY_POSTS, WEEK_POSTS)

    def profile(person):
        return user_obj(person["username"], person["id"], person["name"], person["description"],
                        person["followers"], person["posts"], person["hue"], person["shape"])

    profiles = {person["id"]: profile(person) for person in engaged}
    extras = []
    for index, (username, uid, name, relation, bio) in enumerate(EXTRAS):
        if uid in profiles:
            profiles[uid]["_relation"] = relation
            continue
        extras.append({
            "id": uid, "username": username, "name": name, "relation": relation,
            "description": bio, "followers": 12 + index, "posts": 3 + index,
            "hue": (0.5 + index * 0.11) % 1.0, "shape": SHAPES[(index + 1) % len(SHAPES)],
        })
        profiles[uid] = profile(extras[-1])
    me = user_obj(
        "samplecreator", ME, "Sample Creator",
        "Fictional account used only to demonstrate X Neighbours.",
        2400, 860, 0.58, "circle",
    )
    profiles[ME] = me

    def write_avatar(person):
        avatar(
            os.path.join(OUT, "avatars", f"{person['id']}.png"),
            person["username"][:1].upper(),
            person["_hue"],
            person["_shape"],
        )

    for person in profiles.values():
        write_avatar(person)

    def post_obj(pid, created, text, likers):
        return {
            "id": pid,
            "author_id": ME,
            "created_at": created,
            "text": text,
            "public_metrics": {"like_count": len(likers), "reply_count": 0, "repost_count": 0},
        }

    posts = [post_obj(pid, created, text, day_likers[pid]) for pid, created, text in DAY_POSTS]
    posts += [post_obj(pid, created, text, week_likers[pid]) for pid, created, text in WEEK_POSTS]
    old_id, old_created, old_text = OLD_POST
    old_likers = ["910091"]
    posts.append(post_obj(old_id, old_created, old_text, old_likers))
    note = "FICTIONAL SAMPLE. Made-up users and posts for the X Neighbours example. Not real X data."
    dump("posts_1.json", {
        "_comment": note,
        "data": posts,
        "includes": {"users": [public_user(me)]},
        "meta": {"result_count": len(posts)},
    })

    mentions = []
    mention_id = 7001
    for person in engaged:
        older = person["week_replies"] - person["day_replies"]
        for kind, count in (
            ("day", person["day_replies"]),
            ("week", older),
        ):
            for n in range(count):
                # Shift minutes so each reply has its own timestamp inside the window.
                hour = 12 if kind == "day" else 15
                minute = (mention_id + n) % 50
                created = f"2026-11-04T{hour:02d}:{minute:02d}:00Z" if kind == "day" else f"2026-11-01T{hour:02d}:{minute:02d}:00Z"
                target = DAY_POSTS[n % len(DAY_POSTS)][0] if kind == "day" else WEEK_POSTS[n % len(WEEK_POSTS)][0]
                mentions.append({
                    "id": str(mention_id),
                    "author_id": person["id"],
                    "created_at": created,
                    "text": f"Replying to the sample sketch ({kind} {n + 1}).",
                    "in_reply_to_user_id": ME,
                    "referenced_tweets": [{"type": "replied_to", "id": target}],
                    "conversation_id": target,
                })
                mention_id += 1
    mentions.append({
        "id": str(mention_id),
        "author_id": "910092",
        "created_at": "2026-10-20T13:00:00Z",
        "text": "A reply from before the sample week.",
        "in_reply_to_user_id": ME,
        "referenced_tweets": [{"type": "replied_to", "id": old_id}],
        "conversation_id": old_id,
    })
    mention_id += 1
    mentions.append({
        "id": str(mention_id),
        "author_id": "910093",
        "created_at": "2026-11-04T16:00:00Z",
        "text": "Mentioned @samplecreator while replying to someone else.",
        "in_reply_to_user_id": "910091",
        "referenced_tweets": [{"type": "replied_to", "id": "424242"}],
        "conversation_id": "424242",
    })
    mention_authors = []
    seen = set()
    for mention in mentions:
        uid = mention["author_id"]
        if uid not in seen:
            seen.add(uid)
            mention_authors.append(public_user(profiles[uid]))
    dump("mentions_1.json", {
        "_comment": note,
        "data": mentions,
        "includes": {"users": mention_authors},
        "meta": {"result_count": len(mentions)},
    })

    def like_file(pid, ids):
        dump(f"likes_{pid}.json", {
            "_comment": note,
            "data": [public_user(profiles[uid]) for uid in ids],
            "meta": {"result_count": len(ids)},
        })

    for pid, ids in {**day_likers, **week_likers}.items():
        like_file(pid, ids)
    like_file(old_id, old_likers)

    followers, following = [], []
    for person in list(engaged) + extras:
        pub = public_user(profiles[person["id"]])
        if person.get("relation") in ("mutual", "follows-you"):
            followers.append(pub)
        if person.get("relation") in ("mutual", "you-follow"):
            following.append(pub)
    # grok was given relation on the dict; extras already have relation.
    # engaged people except grok use PEOPLE relations stored on the dict.
    dump("followers_1.json", {"_comment": note, "data": followers, "meta": {"result_count": len(followers)}})
    dump("following_1.json", {"_comment": note, "data": following, "meta": {"result_count": len(following)}})
    print(f"wrote {OUT}")
    print(f"people={len(people)} mentions={len(mentions)} avatars={len(profiles)} "
          f"followers={len(followers)} following={len(following)} now={NOW}")


if __name__ == "__main__":
    main()
