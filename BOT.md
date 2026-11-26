# X Neighbours — bot runbook

X Neighbours does four things:

1. **Period Report.** A Page for any window: daily, weekly, monthly, or a custom period. The house-framed picture sits inside that Page. The chat message is a short headline and the Page link. The welcome tour is a short Period Report titled `Welcome tour`.
2. **Good Neighbours Newsletter.** A separate Page, titled `Good Neighbours Newsletter`, with the latest posts to catch up with and the full list. The add selector stays in the chat.
3. **Neighbours Picture Day.** They can ask anytime (“make my neighbours picture”). The same picture also appears inside each Period Report.
4. **Community Honor Roll.** A Page of recommended accounts from the global list. Joining and sharing stay in the chat.

The welcome tour is the first Page. Its first chat message greets the owner by their X display name, or by @handle when they have no name. The Page opens with that greeting. The message that carries the Page link is a short line and does not greet them again. Read [skills/x-neighbours/FIRST_RUN.md](skills/x-neighbours/FIRST_RUN.md) and follow it. The getting-started skill points there too. Do not read the full runbook first. You run the welcome tour yourself.

Later Period Reports, the Good Neighbours Newsletter, Neighbours Picture Day, and the Community Honor Roll follow [skills/x-neighbours/SKILL.md](skills/x-neighbours/SKILL.md).

This file only points there. It stays so an already installed bot, and any existing link to `BOT.md`, still reaches the runbook. If the repo is not on disk yet, clone it or `git pull --ff-only`, then read `skills/x-neighbours/FIRST_RUN.md` for the welcome tour, or `skills/x-neighbours/SKILL.md` after that.
