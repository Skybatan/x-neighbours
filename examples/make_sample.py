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
# Inside the previous day, so the day report can show a change. Also inside the current week.
PREVIOUS_DAY_POST = ("8010", "2026-11-03T10:00:00Z", "A quiet sketch from the day before this sample window.")
# Inside the previous week, outside the current one.
PREVIOUS_WEEK_POST = ("8011", "2026-10-25T16:00:00Z", "Last week's map, kept so the sample can show a change.")
IMPRESSIONS = {
    "8001": 4200,
    "8002": 1800,
    "8003": 9100,
    "8004": 2500,
    "8005": 6400,
    "8006": 3100,
    "8007": 15000,
    "8008": 2200,
    "8009": 800,
    "8010": 12000,
    "8011": 40000,
}

SHAPES = ("circle", "diamond", "square", "ring")
RELATIONS = ("neither", "follows-you", "you-follow", "mutual")
# Extra quiet neighbours. Three rings show the closest 42 (8 + 14 + 20).
# The 30 people above plus these 38 fillers, with @grok excluded.
FILLER_A = (
    "amber", "brass", "coral", "daisy", "ember", "flint", "grape", "hazel",
    "ivory", "jade", "kelp", "lemon", "maple", "nylon", "olive", "pearl",
    "quartz", "robin", "sage", "tulip", "umber", "violet", "willow", "yarrow",
    "zinc", "apricot", "birch", "clover", "dune", "elm", "fern", "gull",
    "heath", "iris", "juniper", "koi", "lark", "mink",
)
FILLER_B = (
    "anchor", "bridge", "candle", "drawer", "engine", "fountain", "garden", "hammock",
    "island", "journal", "kettle", "ladder", "mirror", "needle", "pocket", "ribbon",
    "saddle", "thimble", "umbrella", "valley", "yarn", "basket", "compass", "easel",
    "flute", "glove", "hinge", "inkwell", "jar", "key", "latch", "nest",
    "oak", "paddle", "quill", "reed", "spool", "trellis",
)


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
    cursor = {"day": 0, "week": 0}
    for person in people:
        for name, bucket, ids, count in (
            ("day", day_likers, day_ids, person["day_likes"]),
            ("week", week_likers, week_ids, person["week_likes"] - person["day_likes"]),
        ):
            placed = 0
            tried = 0
            while placed < count and tried < len(ids) * 2:
                pid = ids[cursor[name] % len(ids)]
                cursor[name] += 1
                tried += 1
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
    used = {person["username"] for person in people}
    for index, (left, right) in enumerate(zip(FILLER_A, FILLER_B)):
        username = f"{left}_{right}"
        if username in used:
            raise SystemExit(f"filler handle collides: {username}")
        people.append({
            "id": str(910200 + index),
            "username": username,
            "name": f"{left.title()} {right.title()}",
            "relation": RELATIONS[index % len(RELATIONS)],
            "day_likes": 0,
            "week_likes": 1,
            "day_replies": 0,
            "week_replies": 0,
            "description": "Fictional neighbour in the sample outer ring.",
            "followers": 40 + index * 3,
            "posts": 12 + index,
            "hue": (0.21 + index * 0.073) % 1.0,
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
            "public_metrics": {
                "like_count": len(likers),
                "reply_count": 0,
                "repost_count": 0,
            },
        }

    posts = [post_obj(pid, created, text, day_likers[pid]) for pid, created, text in DAY_POSTS]
    posts += [post_obj(pid, created, text, week_likers[pid]) for pid, created, text in WEEK_POSTS]
    old_id, old_created, old_text = OLD_POST
    old_likers = ["910091"]
    posts.append(post_obj(old_id, old_created, old_text, old_likers))
    for pid, created, text in (PREVIOUS_DAY_POST, PREVIOUS_WEEK_POST):
        posts.append(post_obj(pid, created, text, []))
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
                phrases = (
                    "The empty centre of the map is the part I keep thinking about.",
                    "Saving this sketch for the next one.",
                    "The ring of chairs made the whole page work.",
                    "This belongs on a kitchen wall.",
                    "I read the margin notes twice.",
                )
                mentions.append({
                    "id": str(mention_id),
                    "author_id": person["id"],
                    "created_at": created,
                    "text": phrases[mention_id % len(phrases)],
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

    quote_plan = [
        ("8001", "910003", "The chairs are doing all the work in this one.", "2026-11-04T16:10:00Z", "8201"),
        ("8005", "910005", "The sunset palette is the one I would print.", "2026-11-02T18:05:00Z", "8202"),
        ("8003", "910006", "Leaving the middle blank is the brave part.", "2026-11-04T15:40:00Z", "8203"),
    ]
    for on_id, author, text, created, qid in quote_plan:
        dump(f"quotes_{on_id}.json", {
            "_comment": note,
            "data": [{
                "id": qid,
                "author_id": author,
                "created_at": created,
                "text": text,
                "referenced_tweets": [{"type": "quoted", "id": on_id}],
                "conversation_id": on_id,
            }],
            "includes": {"users": [public_user(profiles[author])]},
            "meta": {"result_count": 1},
        })
    repost_plan = {
        "8001": ["910001", "910003", "910007"],
        "8002": ["910002", "910005"],
        "8007": ["910004", "910008", "910011", "910012"],
    }
    for pid, ids in repost_plan.items():
        dump(f"reposts_{pid}.json", {
            "_comment": note,
            "data": [public_user(profiles[uid]) for uid in ids],
            "meta": {"result_count": len(ids)},
        })
    latest_lines = {
        "910001": "A paper street with no cars, only chairs.",
        "910002": "The cracked cup is still the one I reach for.",
        "910003": "Tiny weather game, day 12: the clouds learned to queue.",
        "910004": "Rooftop notes from a clear night.",
        "910005": "Long song, short room, both recorded.",
        "910006": "Same trail, new sentence at the gate.",
        "910007": "Folded a timetable into a boat that actually floated.",
        "910008": "Poster for a play that still does not exist.",
        "910009": "Harbour bell, take three, less echo.",
        "910011": "The forecast was boring, so the kite went up.",
    }
    for uid, text in latest_lines.items():
        dump(f"latest_{uid}.json", {
            "_comment": note,
            "data": [
                {"id": "84" + uid[-3:], "author_id": uid, "created_at": "2026-11-04T17:40:00Z",
                 "text": "A reply that Catch up should skip.", "in_reply_to_user_id": "1",
                 "referenced_tweets": [{"type": "replied_to", "id": "1"}]},
                {"id": "85" + uid[-3:], "author_id": uid, "created_at": "2026-11-04T17:20:00Z",
                 "text": "RT @someone: not an original post",
                 "referenced_tweets": [{"type": "retweeted", "id": "2"}]},
                {"id": "83" + uid[-3:], "author_id": uid, "created_at": "2026-11-04T16:30:00Z", "text": text},
            ],
            "includes": {"users": [public_user(profiles[uid])]},
            "meta": {"result_count": 1},
        })
    answered = [mention for mention in mentions if mention["author_id"] in {"910001", "910002"}][:2]
    for mention in answered:
        posts.append({
            "id": "89" + mention["id"],
            "author_id": ME,
            "created_at": "2026-11-04T17:10:00Z",
            "text": "Thanks — this sample reply marks the note as answered.",
            "referenced_tweets": [{"type": "replied_to", "id": mention["id"]}],
            "public_metrics": {"like_count": 0, "reply_count": 0, "repost_count": 0},
        })
    dump("posts_1.json", {
        "_comment": note,
        "data": posts,
        "includes": {"users": [public_user(me)]},
        "meta": {"result_count": len(posts)},
    })
    print(f"wrote {OUT}")
    print(f"people={len(people)} mentions={len(mentions)} avatars={len(profiles)} "
          f"followers={len(followers)} following={len(following)} now={NOW}")


def write_few():
    """A five-neighbour slice so the first-run picture is full, not a sparse ring."""
    folder = os.path.join(ROOT, "examples", "few")
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(os.path.join(folder, "avatars"))
    note = "FICTIONAL SAMPLE. Five made-up neighbours for a short first run. Not real X data."
    me_id = "800001"
    people = [
        ("800101", "ada_brook", "Ada Brook", "mutual", "Kept the window light on."),
        ("800102", "ben_coast", "Ben Coast", "follows-you", "Walked the long way home."),
        ("800103", "cleo_dawn", "Cleo Dawn", "neither", "Wrote the morning down in pencil."),
        ("800104", "dax_elm", "Dax Elm", "you-follow", "Fixed the gate, then the kettle."),
        ("800105", "eri_fern", "Eri Fern", "follows-you", "Left a stone on the step."),
        ("800106", "fay_glen", "Fay Glen", "mutual", "Planted the last of the bulbs."),
    ]
    users = {}
    me = user_obj("fewcreator", me_id, "Few Creator",
                  "Fictional account for a short X Neighbours sample.",
                  120, 40, 0.55, "circle")
    users[me_id] = me
    for index, (uid, username, name, relation, latest) in enumerate(people):
        users[uid] = user_obj(username, uid, name, latest, 80 + index * 10, 20 + index,
                              (0.08 + index * 0.17) % 1, SHAPES[index % len(SHAPES)])
        users[uid]["_relation"] = relation
        users[uid]["_latest"] = latest
    for user in users.values():
        avatar(os.path.join(folder, "avatars", f"{user['id']}.png"),
               user["username"][:1].upper(), user["_hue"], user["_shape"])

    def save(name, payload):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, indent=2)
            fh.write("\n")

    posts = [
        {"id": "70001", "author_id": me_id, "created_at": "2026-11-04T09:00:00Z",
         "text": "Left a light on in the window.",
         "public_metrics": {"like_count": 3, "reply_count": 1, "repost_count": 1}},
        {"id": "70002", "author_id": me_id, "created_at": "2026-11-03T21:00:00Z",
         "text": "The street is quiet after rain.",
         "public_metrics": {"like_count": 3, "reply_count": 1, "repost_count": 0}},
        {"id": "89001", "author_id": me_id, "created_at": "2026-11-04T12:00:00Z",
         "text": "Glad the light helped.",
         "referenced_tweets": [{"type": "replied_to", "id": "71001"}],
         "public_metrics": {"like_count": 0, "reply_count": 0, "repost_count": 0}},
    ]
    save("posts_1.json", {"_comment": note, "data": posts,
                          "includes": {"users": [public_user(me)]}, "meta": {"result_count": len(posts)}})
    mentions = [
        {"id": "71001", "author_id": "800101", "created_at": "2026-11-04T10:00:00Z",
         "text": "I could see it from the corner.", "in_reply_to_user_id": me_id,
         "referenced_tweets": [{"type": "replied_to", "id": "70001"}], "conversation_id": "70001"},
        {"id": "71002", "author_id": "800103", "created_at": "2026-11-04T11:30:00Z",
         "text": "Rain on the page, in a good way.", "in_reply_to_user_id": me_id,
         "referenced_tweets": [{"type": "replied_to", "id": "70002"}], "conversation_id": "70002"},
    ]
    save("mentions_1.json", {
        "_comment": note, "data": mentions,
        "includes": {"users": [public_user(users["800101"]), public_user(users["800103"])]},
        "meta": {"result_count": len(mentions)},
    })
    save("likes_70001.json", {"_comment": note, "data": [public_user(users[uid]) for uid in ("800101", "800102", "800104")],
                              "meta": {"result_count": 3}})
    save("likes_70002.json", {"_comment": note, "data": [public_user(users[uid]) for uid in ("800103", "800105", "800106")],
                              "meta": {"result_count": 3}})
    save("reposts_70001.json", {"_comment": note, "data": [public_user(users["800102"])], "meta": {"result_count": 1}})
    save("quotes_70002.json", {
        "_comment": note,
        "data": [{
            "id": "72001", "author_id": "800105", "created_at": "2026-11-04T15:00:00Z",
            "text": "Quiet streets are the best kind.",
            "referenced_tweets": [{"type": "quoted", "id": "70002"}],
        }],
        "includes": {"users": [public_user(users["800105"])]},
        "meta": {"result_count": 1},
    })
    for uid, _username, _name, _relation, latest in people:
        original = {"id": "83" + uid[-3:], "author_id": uid, "created_at": "2026-11-04T16:00:00Z", "text": latest}
        posts = [original]
        # Ada's newest items are a reply and a plain repost. The quote is the latest original.
        if uid == "800101":
            posts = [
                {"id": "83101r", "author_id": uid, "created_at": "2026-11-04T17:30:00Z",
                 "text": "Just a reply, not for Catch up.", "in_reply_to_user_id": "800199",
                 "referenced_tweets": [{"type": "replied_to", "id": "999"}]},
                {"id": "83101t", "author_id": uid, "created_at": "2026-11-04T17:00:00Z",
                 "text": "RT @someone: a plain repost",
                 "referenced_tweets": [{"type": "retweeted", "id": "888"}]},
                {"id": "83101q", "author_id": uid, "created_at": "2026-11-04T16:40:00Z",
                 "text": "Quoting my own note about the window.",
                 "referenced_tweets": [{"type": "quoted", "id": "777"}]},
                original,
            ]
        # Ben only replied and reposted. Catch up should skip him for Fay.
        if uid == "800102":
            posts = [
                {"id": "83102r", "author_id": uid, "created_at": "2026-11-04T17:20:00Z",
                 "text": "Replying, not posting.", "in_reply_to_user_id": "800199",
                 "referenced_tweets": [{"type": "replied_to", "id": "998"}]},
            ]
        save(f"latest_{uid}.json", {
            "_comment": note,
            "data": posts,
            "includes": {"users": [public_user(users[uid])]},
            "meta": {"result_count": len(posts)},
        })
    followers, following = [], []
    for uid, _username, _name, relation, _latest in people:
        pub = public_user(users[uid])
        if relation in ("mutual", "follows-you"):
            followers.append(pub)
        if relation in ("mutual", "you-follow"):
            following.append(pub)
    save("followers_1.json", {"_comment": note, "data": followers, "meta": {"result_count": len(followers)}})
    save("following_1.json", {"_comment": note, "data": following, "meta": {"result_count": len(following)}})
    print(f"wrote {folder}")


if __name__ == "__main__":
    main()
    write_few()
