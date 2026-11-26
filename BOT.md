# X Neighbours — bot runbook

X Neighbours does four things:

1. **Report.** A Page for each report. The house-framed picture sits inside that Page. The chat message is a short headline and the Page link.
2. **Good neighbours.** A separate Page, titled `Good neighbours`, with the latest posts to catch up with and the full list. The add selector stays in the chat.
3. **Neighbours picture.** They can ask anytime (“make my neighbours picture”). The same picture also appears inside each report Page.
4. **Community.** A Page of recommended accounts from the global list. Joining and sharing stay in the chat.

The welcome tour is the first Page. Its first chat message greets the owner by their X display name, or by @handle when they have no name. The Page opens with that greeting. The message that carries the Page link is a short line and does not greet them again. Read [skills/x-neighbours/FIRST_RUN.md](skills/x-neighbours/FIRST_RUN.md) and follow it. The getting-started skill points there too. Do not read the full runbook first. You run the welcome tour yourself.

Later reports, the Good neighbours Page, the picture, and the Community Page follow [skills/x-neighbours/SKILL.md](skills/x-neighbours/SKILL.md).

This file only points there. It stays so an already installed bot, and any existing link to `BOT.md`, still reaches the runbook. If the repo is not on disk yet, clone it or `git pull --ff-only`, then read `skills/x-neighbours/FIRST_RUN.md` for the welcome tour, or `skills/x-neighbours/SKILL.md` after that.
