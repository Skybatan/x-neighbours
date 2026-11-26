#!/usr/bin/env python3
"""Render an X Neighbours report as a Grok Bot Page.

The page uses the same words, order, and links as the chat report.
`templates/report.canvas.tsx` is the module. This script fills its
placeholder with the report object. The bot passes that source to
WriteCanvas. It does not write the page by hand.

A section with nothing to show is left out. The short sentences the
chat report uses for an empty stretch stay, without a heading.
"""
import argparse
import copy
import json
import os
import re

import x_neighbours as xn

ROOT = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(ROOT, "templates", "report.canvas.tsx")
PLACEHOLDER = "/*__REPORT_JSON__*/ null as unknown as Report"

NO_FLOWERS = "No replies, likes, or reposts in this stretch."
NO_CATCH = "No one to catch up with in this stretch."
CATCH_HINT = "Add people to your good neighbours list to keep up with them here."
CAUGHT_UP = "You're all caught up with your good neighbours 🎉"
NO_ORIGINALS = "No recent original posts from your good neighbours."
NO_REPLIES = "No replies or quote posts in this stretch."
NONE_WAITING = "No replies waiting on you."
NO_THANKS = "No neighbours to thank in this stretch."

_URL = re.compile(r"https://\S+")


def part(text, href=None):
    return {"text": text or "", "href": href or None}


def profile_url(person):
    username = person.get("username") or ""
    if not username:
        return None
    return f"https://x.com/{username}"


def quoted(text):
    return f"“{text}”"


def age_suffix(created_at):
    if not created_at:
        return ""
    return " · " + xn.ago(xn.ts(created_at), xn.utc_now())


def count_phrase(row):
    counts = []
    if row.get("replies"):
        counts.append(xn.counted(row["replies"], "reply", "replies"))
    if row.get("likes"):
        counts.append(xn.counted(row["likes"], "like", "likes"))
    if row.get("reposts"):
        counts.append(xn.counted(row["reposts"], "repost", "reposts"))
    if not counts:
        counts.append("showed up")
    return " · ".join(counts)


def flower_item(row):
    parts = [part(row["name"], profile_url(row))]
    marks = xn.person_marks(row)
    if marks:
        parts.append(part(marks))
    return {"lines": [{"parts": parts}, {"parts": [part(count_phrase(row))]}]}


def catch_item(person):
    latest = person.get("latest") or {}
    text = xn.snippet(latest.get("text")) or "Post"
    url = (person.get("latest_url") or "").strip()
    preview = part(quoted(text), url or None)
    when = age_suffix(latest.get("created_at"))
    parts = [preview]
    if when:
        parts.append(part(when))
    name = [part(person["name"])]
    marks = xn.person_marks(person)
    if marks:
        name.append(part(marks))
    return {"lines": [{"parts": name}, {"parts": parts}]}


def greeting_item(row):
    kind = "Quote" if row.get("kind") == "quote" else "Reply"
    status = xn.greeting_status(row)
    marks = xn.person_marks(row)
    name = [part(row["name"], profile_url(row)), part(f"{marks} · {kind} · {status}")]
    text = row.get("text") or "Post"
    url = (row.get("url") or "").strip()
    preview = [part(quoted(text), url or None)]
    when = age_suffix(row.get("created_at"))
    if when:
        preview.append(part(when))
    lines = [{"parts": name}, {"parts": preview}]
    if row.get("on_text"):
        lines.append({"parts": [part(f"on {quoted(row['on_text'])}")]})
    return {"lines": lines}


def section_block(heading, items, preface=None, footers=None):
    kept = [footer for footer in (footers or []) if footer]
    if not items and not preface and not kept:
        return None
    return {
        "kind": "section",
        "heading": heading,
        "preface": preface or None,
        "items": items,
        "footers": kept,
    }


def note_block(text):
    if not text:
        return None
    return {"kind": "note", "text": text}


def thanks_block(thanks, picture=None):
    if not thanks:
        return {
            "kind": "thanks",
            "text": NO_THANKS,
            "linkLabel": None,
            "href": None,
            "note": None,
            "extra": None,
            "picture": None,
        }
    return {
        "kind": "thanks",
        "text": thanks["text"],
        "linkLabel": thanks.get("link_label") or "Post your thank-you",
        "href": thanks.get("intent") or None,
        "note": thanks.get("note") or xn.THANK_YOU_NOTE,
        "extra": None,
        "picture": clean_picture(picture),
    }


def headline_for(title, summary, waiting):
    text = f"{title} · {summary}"
    waiting = int(waiting or 0)
    if waiting:
        text += " · " + xn.counted(waiting, "reply to answer", "replies to answer")
    return text


def build_page_model(activity, since, now, label, show=None, window="day", intro=None, thanks=None):
    """Page model for one report. Wording matches `write_chat_report`."""
    if show is None:
        show = xn.CHAT_SHOW
    title = xn.period_line(window, since, now, label)
    summary = xn.count_line(activity["totals"])
    people = activity["threads"] + activity["interactions"] + activity["catch_up"]
    legend_bits = []
    if any(person.get("stranger") for person in people):
        legend_bits.append("👤? = you don't follow them yet")
    if activity.get("has_good_neighbours"):
        legend_bits.append("⭐ = good neighbour")
    legend = " · ".join(legend_bits) if legend_bits else None

    blocks = []
    flowers = activity["interactions"]
    if not flowers:
        blocks.append(note_block(NO_FLOWERS))
    else:
        items = [flower_item(row) for row in flowers[:show]]
        footers = []
        extra = len(flowers) - show
        if extra > 0:
            footers.append(f"+{extra} more in Flowers. Ask to see them.")
        blocks.append(section_block("💐 Flowers", items, footers=footers))

    catch = activity["catch_up"]
    if not catch:
        if activity.get("all_caught_up"):
            blocks.append(note_block(CAUGHT_UP))
        elif activity.get("catch_hint"):
            blocks.append(note_block(NO_CATCH))
            if window != "first":
                blocks.append(note_block(CATCH_HINT))
        else:
            blocks.append(note_block(NO_ORIGINALS))
    else:
        preface = None
        if activity.get("catch_hint") and window != "first":
            preface = CATCH_HINT
        items = [catch_item(person) for person in catch[:show]]
        footers = []
        extra = len(catch) - show
        if extra > 0:
            footers.append(f"+{extra} more in What's new. Ask to see them.")
        blocks.append(section_block("🏡 What's new", items, preface=preface, footers=footers))

    unanswered, answered = xn.greeting_rows(activity["threads"])
    if not unanswered and not answered:
        blocks.append(note_block(NO_REPLIES))
    else:
        preface = NONE_WAITING if not unanswered else None
        items = [greeting_item(row) for row in unanswered[:show]]
        footers = []
        extra = len(unanswered) - show
        if extra > 0:
            footers.append(f"+{extra} more replies. Ask to see them.")
        if answered:
            footers.append(f"{len(answered)} already answered. Ask to see them.")
        blocks.append(section_block("👋 Replies", items, preface=preface, footers=footers))

    blocks.append(thanks_block(thanks))
    blocks = [block for block in blocks if block]
    return {
        "title": title,
        "summary": summary,
        "legend": legend,
        "intro": intro or None,
        "headline": headline_for(title, summary, len(unanswered)),
        "blocks": blocks,
    }


def blocks_from_extra_markdown(text):
    """Per-day and per-post markdown, as page sections, ahead of the thank-you."""
    blocks = []
    heading = None
    preface = []
    items = []

    def flush():
        nonlocal heading, preface, items
        if heading is None:
            return
        block_items = [{"lines": [{"parts": parts}]} for parts in items]
        preface_text = " ".join(preface) if preface else None
        block = section_block(heading, block_items, preface=preface_text)
        if block:
            blocks.append(block)
        heading = None
        preface = []
        items = []

    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("### "):
            flush()
            heading = line[4:].strip()
            continue
        if heading is None:
            continue
        if line.startswith("- "):
            body = line[2:].replace("**", "")
            match = _URL.search(body)
            if match:
                before = body[:match.start()]
                url = match.group(0)
                rest = body[match.end():]
                parts = []
                if before:
                    parts.append(part(before))
                parts.append(part(url, url))
                if rest:
                    parts.append(part(rest))
                items.append(parts)
            else:
                items.append([part(body)])
        else:
            preface.append(line.replace("**", ""))
    flush()
    return blocks


def insert_before_thanks(blocks, extra):
    if not extra:
        return list(blocks)
    head, tail = [], []
    seen = False
    for block in blocks:
        if not seen and block.get("kind") == "thanks":
            seen = True
        if seen:
            tail.append(block)
        else:
            head.append(block)
    return head + list(extra) + tail


def clean_picture(value):
    """A Page image is an uploaded `asset:` name. A web address is not fetched."""
    text = str(value or "").strip()
    if text.startswith("asset:"):
        return text
    return None


def apply_overrides(model, thank_intent=None, thanks_extra=None, picture_asset_name=None):
    model = copy.deepcopy(model)
    picture = clean_picture(picture_asset_name) if picture_asset_name else None
    for block in model.get("blocks") or []:
        if block.get("kind") != "thanks":
            continue
        if thank_intent:
            block["href"] = thank_intent
            if not block.get("linkLabel"):
                block["linkLabel"] = "Post your thank-you"
        if thanks_extra:
            block["extra"] = thanks_extra
        if picture_asset_name:
            block["picture"] = picture
    return model


def page_payload(model):
    """The object embedded in the canvas. Empty sections are left out."""
    blocks = []
    for block in model.get("blocks") or []:
        kind = block.get("kind")
        if kind == "note":
            if block.get("text"):
                blocks.append({"kind": "note", "text": block["text"]})
        elif kind == "section":
            items = block.get("items") or []
            preface = block.get("preface") or None
            footers = [footer for footer in (block.get("footers") or []) if footer]
            if not items and not preface and not footers:
                continue
            blocks.append({
                "kind": "section",
                "heading": block.get("heading") or "",
                "preface": preface,
                "items": items,
                "footers": footers,
            })
        elif kind == "thanks":
            picture = clean_picture(block.get("picture"))
            text = block.get("text") or ""
            href = block.get("href") or None
            extra = block.get("extra") or None
            if not text and not href and not extra and not picture:
                continue
            blocks.append({
                "kind": "thanks",
                "text": text,
                "linkLabel": block.get("linkLabel") or None,
                "href": href,
                "note": block.get("note") or None,
                "extra": extra,
                "picture": picture,
            })
    return {
        "title": model.get("title") or "",
        "summary": model.get("summary") or "",
        "legend": model.get("legend") or None,
        "intro": model.get("intro") or None,
        "blocks": blocks,
    }


def _plain_text(value):
    """Text for a Page: real characters, no ``\\u`` escapes.

    JSON still writes quotes and newlines as ``\\"`` and ``\\n``. Characters
    that JSON would spell as ``\\uXXXX`` (controls, DEL, the two Unicode line
    separators) become a space or a newline first, so the canvas source keeps
    the character itself.
    """
    if isinstance(value, str):
        chars = []
        for char in value:
            code = ord(char)
            if char in "\n\r\t":
                chars.append(char)
            elif code < 0x20 or code == 0x7F:
                chars.append(" ")
            elif code in (0x2028, 0x2029):
                chars.append("\n")
            else:
                chars.append(char)
        return "".join(chars)
    if isinstance(value, list):
        return [_plain_text(item) for item in value]
    if isinstance(value, dict):
        return {key: _plain_text(item) for key, item in value.items()}
    return value


def embed_json(value):
    """JSON for a TSX expression. Non-ASCII text is UTF-8, not ``\\u`` escapes."""
    return json.dumps(_plain_text(value), ensure_ascii=False, indent=2)


def render_report_canvas(model, template=None):
    if template is None:
        with open(TEMPLATE, encoding="utf-8") as fh:
            template = fh.read()
    if template.count(PLACEHOLDER) != 1:
        raise ValueError("report template must contain the data placeholder once")
    return template.replace(PLACEHOLDER, embed_json(page_payload(model)), 1)


def write_page(model, canvas_path, model_path=None):
    source = render_report_canvas(model)
    if not source.endswith("\n"):
        source += "\n"
    folder = os.path.dirname(canvas_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(canvas_path, "w", encoding="utf-8") as fh:
        fh.write(source)
    if model_path:
        model_folder = os.path.dirname(model_path)
        if model_folder:
            os.makedirs(model_folder, exist_ok=True)
        with open(model_path, "w", encoding="utf-8") as fh:
            json.dump(model, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    return source


def default_canvas_path(model_path):
    folder, name = os.path.split(model_path)
    if name.endswith("_page.json"):
        name = name[: -len("_page.json")] + ".canvas.tsx"
    else:
        name = name + ".canvas.tsx"
    return os.path.join(folder, name)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Fill the X Neighbours report Page from a saved page model."
    )
    parser.add_argument("--model", required=True, help="report_<window>_page.json")
    parser.add_argument("--out", help="canvas path (default: report_<window>.canvas.tsx)")
    parser.add_argument("--thank-intent", help="replace the thank-you link, for a picture-tag")
    parser.add_argument("--thanks-extra", help="line after the thank-you note, such as the picture-tag reminder")
    parser.add_argument("--picture-asset", help="asset: name of an uploaded picture; a web URL is ignored")
    args = parser.parse_args(argv)
    with open(args.model, encoding="utf-8") as fh:
        model = json.load(fh)
    model = apply_overrides(
        model,
        thank_intent=args.thank_intent,
        thanks_extra=args.thanks_extra,
        picture_asset_name=args.picture_asset,
    )
    out = args.out or default_canvas_path(args.model)
    write_page(model, out, args.model)
    print(json.dumps({"page_canvas": out, "page_model": args.model}, ensure_ascii=False))


if __name__ == "__main__":
    main()
