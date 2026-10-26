import os, sys, json, time
sys.path.insert(0, os.getcwd()); sys.path.insert(0, os.path.join(os.getcwd(), "tools"))
os.environ.pop("ANTHROPIC_API_KEY", None)          # prova: nessuna chiave a pagamento
import free_llm
out = ["models: " + str(free_llm.models())]
t = time.time(); r = free_llm.generate("Reply with exactly: OK free", max_tokens=20); out.append("errors after ping: " + json.dumps(free_llm.LAST_ERRORS[:6])); out.append(f"ping: {r!r} {time.time()-t:.1f}s")
import gen_analysis_pages as G
import ew_server as E
d = E._ta_compute("CL=F", 2, interval="1h", period="60d", htf_rule="4h")
t = time.time(); ai = G.ai_commentary("WTI Crude Oil", d); out.append(f"analysis ({time.time()-t:.1f}s): " + json.dumps(ai, ensure_ascii=False)[:1500])
import desk_read as D
facts = ["WTI Crude Oil: price +3.82%, total open interest -776 contracts, volume 1.3x 20-day average: short covering",
         "Gold: price -1.29%, total open interest -2.9k contracts, volume 1.4x 20-day average: long liquidation"]
t = time.time(); txt, why = D.ai_read("flow", facts); out.append(f"desk ({time.time()-t:.1f}s): {txt!r} / {why}")
out.append("errors: " + json.dumps(free_llm.LAST_ERRORS[:12]))
os.makedirs("seo_out", exist_ok=True); open("seo_out/llm_test.txt", "w").write("\n".join(out)); print("\n".join(out))
