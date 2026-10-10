<!-- Source: https://www.freyavoice.ai/hackathon#faq — fetched 2026-10-10 -->

## Questions we were asked

**I did not get the login mail.**
Look in your spam folder first. Mail to Outlook, Hotmail and some university addresses was filtered. If it is not there, reply to us and we send it again.

**Where is the kit?**
On the Data tab: "Download the kit". Unzip it and read `README.md` first.

**Where do I get a Freya API key?**
Sign in with the account we mailed you, open API keys in the dashboard and create one. Put it in `env.sh` as `FREYA_API_KEY`.

**My teammate has no account, or we have two workspaces.**
Work in one workspace. Its owner invites the teammate from [Workspace settings](https://staging-app.freyavoice.ai/workspace/settings). If your teammate has no account at all, reply to us with the address.

**A test call in the dashboard never passes identity.**
Your workspace has one practice customer for dashboard test calls. Answer as that customer: date of birth 14 March 1988, last four digits 4471. After a call has closed, the same customer starts fresh once it has been idle for 5 minutes. `run_cases.py` opens a fresh customer for every case, so it is not affected.

**How many workflows can a workspace hold?**
200. Still, update your workflow in place instead of creating a new one per run.

**Can my builder open practice customers of its own?**
No. The practice bank serves the 13 cases PUB-01 to PUB-13 only. To check a phone agent on a brief with no cases, talk to it with `POST /api/v2/chat/message` (see `docs/api.md`).

**Do the hidden briefs come with practice cases?**
No. Each comes with its tool API file only.

**Is the raw-material brief one file?**
Yes. Each hidden brief is one Markdown file, with its own tool API file next to it. `{brief_path}` is that one file.

**May I use code I wrote before the event?**
Yes. Nothing from the hidden briefs may be in your builder, and the phone agents must come out of your builder with no edits by hand.

**Is the score taken from the phone agent we submit, or from your rebuild?**
From the phone agents you export and submit. We rebuild only the top entries, to check that the submitted phone agent really came out of your builder. Model output varies from run to run, so we do not expect an identical workflow. We look at its structure and its score.

**My score dropped and I changed nothing.**
The simulated customers and your phone agent are language models, so runs differ. A run also suffers when the model is busy: `run_cases.py` prints the slowest agent turn per call. Run again, and use `--reps 3` before you trust a number.

**Something else?**
Reply to the login mail. It reaches us.
