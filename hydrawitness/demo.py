"""Two questions, one shared synthetic evidence graph; each run has isolated IDs."""
import json
from pathlib import Path
import uuid
from .engine import Registry, Witness
from .seed_codex import CHECKOUT_SUBJECT

def main():
    root=Path(__file__).resolve().parent.parent
    w=Witness('demo-'+uuid.uuid4().hex,Registry(root/'datasets/controlled'))
    policy='release-v1'
    w.seed_claim('release-readiness',['demo/qa','demo/security-summary'], subject=CHECKOUT_SUBJECT)
    w.seed_claim('security-readiness',['demo/qa'], subject=CHECKOUT_SUBJECT)
    first=w.improve('release-readiness',policy)
    second=w.improve('security-readiness',policy)
    print(json.dumps({'scope':w.scope,'first_question':first,'related_question':second},indent=2))

if __name__=='__main__': main()
