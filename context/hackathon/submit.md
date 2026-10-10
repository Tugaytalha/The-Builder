<!-- Source: https://www.freyavoice.ai/hackathon#submit — fetched 2026-10-10 -->

## Two phone agents, one commit and the builder's trace

1. On Sunday at 17:00 UTC we send two hidden briefs to every team. Each comes with its own tool API file.
2. Run your builder on each brief and keep everything it prints. You may run it more than once. Submit one phone agent per brief, with the trace of the run that made it. Do not edit a phone agent after the run.
3. Export each phone agent to a file with `freya.export_workflow` and commit the files. We load them into our own workspace, so what you export is what we score.
4. Before 20:00 UTC, send the form below to the address in your kit email.

```
$ python3 builder/build.py briefs/hidden-1.md briefs/hidden-1.openapi.json 2>&1 | tee traces/hidden-1.log
```

```
{
  "team": "your-team-name",
  "repo": "https://github.com/you/your-builder",
  "commit": "9f2c1ab",
  "run_command": "python3 builder/build.py {brief_path} {tool_api_path}",
  "workflows": {
    "hidden-1": "submission/hidden-1.workflow.json",
    "hidden-2": "submission/hidden-2.workflow.json"
  },
  "traces": {
    "hidden-1": "traces/hidden-1.log",
    "hidden-2": "traces/hidden-2.log"
  }
}
```

### The builder's trace

A trace is the record of one builder run: what it read, what it decided and what it created. We ask for one per hidden brief. Commit the files to your repository.

| In the trace | Why |
| --- | --- |
| Start and end time of the run | Build time breaks ties between equal scores. |
| Every model call the builder made: which model, and what it was asked for in one line | Shows how the builder works, not only what it produced. |
| What it created on Freya: workflow id, agent id, number of steps and tools | Ties the phone agent you submit to this run. |
| Any test it ran on its own phone agent, with the result | A builder that checks its own work is the point of the exercise. |

Plain text is fine. There is no required format. Remove API keys before you commit.

If you built your builder with a coding agent such as Claude Code or Codex, you may also share those session logs. This is optional. The top three teams talk their approach through with us, and a log is the easiest way to show it.

### How we verify

We test the phone agents you submitted. For the top ten teams we also clone the repository at that commit, run the builder ourselves on the same briefs and compare with your trace. Every trace is also read by a reviewer agent that checks it against the submitted code and the phone agent it claims to have created. If our run scores clearly below yours, the entry is removed. We do this to catch phone agents that were edited by hand.

### Limits

| Limit | Value |
| --- | --- |
| Builder run time | 30 minutes per brief, including any test the builder runs on its own phone agent |
| Workflows per workspace | 200. Update one in place instead of creating a new one per run. |
| Models the builder may use | Any. You pay for your builder's own model calls. |
| Model the phone agent runs on | The Freya model set in `freya.py`. The same for every team. Do not change it. |
| Practice simulations | 1 running at a time per workspace |
