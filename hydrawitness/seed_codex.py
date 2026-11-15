"""Seed separate claims that share a controlled evidence chain in a named scope."""
import os
from pathlib import Path
from .engine import Witness,Registry

def main():
 scope=os.environ.get('HYDRAWITNESS_SCOPE','hydrawitness-codex-demo')
 w=Witness(scope,Registry(Path(__file__).resolve().parent.parent/'datasets/controlled'))
 for claim in ('checkout-deployment','checkout-security'):
  w.seed_claim(claim,['demo/qa','demo/security-summary','demo/engineering','demo/release'])
 print('Seeded synthetic claims in scope',scope,'using',w.queries,'HydraDB queries')
if __name__=='__main__': main()
