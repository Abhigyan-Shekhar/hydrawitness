"""Seed separate claims that share a controlled evidence chain in a named scope."""
import os
from pathlib import Path
from .engine import Witness,Registry

CHECKOUT_SUBJECT = {'kind': 'git_commit', 'value': 'fca3fba3c16359e6a89a77d0333a2e25a4d1ad9f'}
DEPLOYMENT_CLAIM = 'checkout-deployment'
SECURITY_CLAIM = 'checkout-security'

def seed_checkout(w):
    w.seed_claim(DEPLOYMENT_CLAIM, ['demo/qa', 'demo/security-summary', 'demo/engineering', 'demo/release'],
                 subject=CHECKOUT_SUBJECT)
    w.seed_claim(SECURITY_CLAIM, ['demo/security-summary'], subject=CHECKOUT_SUBJECT)

def main():
 scope=os.environ.get('HYDRAWITNESS_SCOPE','hydrawitness-codex-demo')
 w=Witness(scope,Registry(Path(__file__).resolve().parent.parent/'datasets/controlled'))
 seed_checkout(w)
 print('Seeded synthetic claims in scope',scope,'using',w.queries,'HydraDB queries')
if __name__=='__main__': main()
