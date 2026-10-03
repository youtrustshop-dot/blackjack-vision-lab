"""Read public GitHub metadata; pin examined revisions without copying implementation."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import urllib.request
import urllib.error
from datetime import datetime, timezone

REPOS=["hhoppe/blackjack","kevin-lesenechal/freebj","mhluska/blackjack-simulator",
       "Neurobaby/MGPs-BJ-CA","AttackingOrDefending/Blackjack-Strategy-Simulator",
       "mmichie/cardsharp","roboflow/blackjack-basic-strategy",
       "martinabeleda/blackjack-tracker","mhluska/blackjack-discard-tray-photos",
       "datamllab/rlcard","he-jev/laya"]

def get(url):
    request=urllib.request.Request(url,headers={"User-Agent":"Blackjack-Vision-Lab-Reference-Audit",
                                               "Accept":"application/vnd.github+json"})
    with urllib.request.urlopen(request,timeout=25) as response:
        return json.load(response)

def inspect(repo):
    record={"repository":repo,"url":"https://github.com/"+repo,"code_copied":False,
            "production_dependency":False,"comparison_executed":False}
    try:
        metadata=get("https://api.github.com/repos/"+repo)
        branch=metadata["default_branch"]
        commit=get("https://api.github.com/repos/"+repo+"/commits/"+branch)
        licence=metadata.get("license")
        record.update(default_branch=branch,commit=commit["sha"],
                      commit_url=commit["html_url"],license=licence["spdx_id"] if licence else "UNDECLARED",
                      examined_at=datetime.now(timezone.utc).isoformat(),
                      status="metadata_examined",
                      note="Revision pinned; metadata inspection does not prove mathematical correctness.")
    except (urllib.error.URLError,KeyError,TimeoutError) as error:
        record.update(status="unavailable",error=str(error))
    return record

def main():
    output=Path(__file__).parents[1]/"references"/"manifest.json"
    records=[]
    with ThreadPoolExecutor(max_workers=4) as executor:
        for future in as_completed([executor.submit(inspect,r) for r in REPOS]):
            record=future.result();records.append(record);print(record["repository"],record["status"],record.get("license",""))
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({"schema_version":1,"references":sorted(records,key=lambda r:r["repository"])},indent=2),encoding="utf-8")

if __name__=="__main__":
    main()
