# {{title}}: LAUNCH

Repo: `stonedhawk/{{repo_name}}`
Target user: {{target_user}}

<!-- Nothing here is posted automatically. Rahul publishes every post himself (SPEC 4, 12). -->

## Ship checklist

Ship means all of these are true (SPEC 12):

- [ ] Audit gate passed: `05_Audit/{{slug}}/AUDIT.md` shows every applicable check as pass
- [ ] Repo public
- [ ] About line set (200 characters or less): {{about_line}}
- [ ] Topics set: {{topics}}
- [ ] Website field set to the GitHub Pages URL, if there is a demo page
- [ ] Portfolio card PR merged in `stonedhawk/rahul-m-shah-portfolio`, `content/tools/`, with `inspiredBy` crediting {{source_pattern}}
- [ ] LinkedIn post drafted with the `my-writing-style` skill
- [ ] Backlog row: `status = shipped`, `repo_url` filled in, `shipped_on` as YYYY-MM-DD (`scripts/track.py` reads it)

## Channels

Distribution from scoring: {{distribution}}

<!-- One row per channel, most important first. Only channels where the target users already gather. Name the exact place (a subreddit, a Slack or Discord community and its channel, a newsletter), not "social media". Check each channel's self-promotion rules and note them. -->

| Channel | Why these users are there | Rules on self-promotion | Post |
|---|---|---|---|
| LinkedIn, Rahul's profile | | | Draft 1 |
| | | | |

## Timing

<!-- Day 0 is the day the repo goes public. Give a day and a local time for each post, spaced so Rahul can answer replies. Avoid weekends for professional channels. -->

| When | What |
|---|---|
| Day 0 | |

## Post drafts

<!-- One draft per channel. Lead with the user's problem, not the tool. Show the demo GIF. Link the repo. State only what the README states: the post is held to audit check 1 too. No em or en dashes. The LinkedIn draft is written with the my-writing-style skill and goes to 06_Shipped/{{slug}}/linkedin-post.md. -->

### Draft 1: LinkedIn

## Measured at 7 and 30 days

The weekly idea-radar task runs `python scripts/track.py` against the backlog sheet and records stars on day 7 and day 30 after `shipped_on`, in `06_Shipped/{{slug}}/results.md` and the `stars_7d` and `stars_30d` columns.

| Measure | Day 7 | Day 30 | Recorded by |
|---|---|---|---|
| GitHub stars | | | weekly task |
| LinkedIn post impressions | | | Rahul, by hand |
| LinkedIn reactions and comments | | | Rahul, by hand |
| Inbound messages about the tool | | | Rahul, by hand |
| Repo traffic: unique visitors and clones | | | Rahul, from GitHub Insights |

Target: 25 stars within 30 days (SPEC 14).
