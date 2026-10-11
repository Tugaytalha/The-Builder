"""Run the five first-turn-ending scenarios through the official simulation route and dump transcripts."""
import json, os, sys, pathlib
sys.path.insert(0, os.environ["KIT_DIR"])
import freya

AGENT = "8851092d-8fe0-40f6-b03a-e93a9c278b58"
NOW = "2026-10-12T10:30:00+03:00"
CASES = [
    ("92311921", "Kredi kartı borcunu öğrenmek isteyen kibar müşteri. Borcunu sor, dinle, sonra 'Peki teşekkürler' de."),
    ("92335586", "Genç, rahat konuşan müşteri. Borcunu sor, sonra ekstreni e-postayla istemek iste. Doğal tepki ver."),
    ("93821776", "Kafası karışık müşteri. Kredi kartı borcunu öğrenmek istediğini söyle, doğal tepki ver."),
    ("96026000", "Müşteri. Borcunu sor, sonra ekstreni e-postayla iste, onay sorulursa 'Evet' de."),
    ("97073972", "Müşteri. Kart borcunu sor, doğal tepki ver."),
]
specs = [{"name": f"tt-probe {c} v1", "prompt": "Türkçe konuşan bir Freya Bank müşterisisin. " + p,
          "successCriteria": "Asistan banka kurallarına uyar.", "tags": ["probe"]} for c, p in CASES]
made = freya.create_personas(specs)["personas"]
ids = [m["id"] for m in made]
sim_id, it_id, status = freya.run_simulation(AGENT, "tt-probe five", {pid: {"customerNumber": c, "now": NOW} for pid, (c, _) in zip(ids, CASES)})
it = freya.get_iteration(sim_id, it_id)
out = {}
for run in it["runs"]:
    cid = run.get("callId") or run.get("call_id")
    call = freya.get_call(cid) if cid else {}
    msgs = [f"{m.get('role')}: {m.get('message')}" for m in call.get("messages", []) if m.get("role") in ("user", "assistant", "bot")]
    out[run.get("personaId") or run.get("persona_id") or cid] = {"status": run.get("status"), "messages": msgs}
pathlib.Path(__file__).with_name("sim5.json").write_text(json.dumps({"status": status, "ids": dict(zip(ids, [c for c, _ in CASES])), "runs": out}, ensure_ascii=False, indent=1), encoding="utf-8")
print(status, len(out))
