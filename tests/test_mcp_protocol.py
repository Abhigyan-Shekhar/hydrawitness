"""Exercise MCP over real stdio and real HydraDB in a fresh scope."""
from tests import integration_test
import asyncio,os,sys,unittest,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from hydrawitness.engine import GITHUB_ACTIONS_VERIFICATION, Witness, Registry
from hydrawitness.seed_codex import CHECKOUT_SUBJECT, seed_checkout
ROOT=Path(__file__).resolve().parent.parent

def unpack(r):
    if r.isError: raise AssertionError(r.content)
    return r.structuredContent

@integration_test
class ProtocolTest(unittest.TestCase):
 def test_stdio_tools(self):
    scope='mcp-test-'+uuid.uuid4().hex
    w=Witness(scope,Registry(ROOT/'datasets/controlled'))
    seed_checkout(w)
    workflow={'external_id':'github/1/pr/7/run/9/attempt/1','type':'ci',
              'subject':CHECKOUT_SUBJECT,'root_verified':False,'outcome':'passed',
              'observed_at':'2026-11-14T00:00:00Z','verification_method':GITHUB_ACTIONS_VERIFICATION}
    w.ingest_workflow_evidence('github-release',CHECKOUT_SUBJECT,[workflow])
    async def run():
        params=StdioServerParameters(command=sys.executable,args=['-m','hydrawitness.mcp_server'],env={**os.environ,'HYDRAWITNESS_SCOPE':scope},cwd=ROOT)
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                tools=await session.list_tools()
                by_name={tool.name:tool for tool in tools.tools}
                self.assertEqual(set(by_name),{'verify_evidence','trace_sources','assess_and_improve','scan_impact'})
                self.assertTrue(by_name['scan_impact'].annotations.readOnlyHint)
                a=unpack(await session.call_tool('verify_evidence',{'claim_id':'checkout-deployment'})); self.assertEqual(a['assessment']['verdict'],'REVIEW_REQUIRED')
                self.assertEqual(a['assessment']['subject'],CHECKOUT_SUBJECT)
                t=unpack(await session.call_tool('trace_sources',{'claim_id':'checkout-deployment'}));self.assertTrue(t['provenance']['paths'])
                bad=await session.call_tool('assess_and_improve',{'claim_id':'checkout-deployment','max_iterations':6});self.assertTrue(bad.isError)
                b=unpack(await session.call_tool('assess_and_improve',{'claim_id':'checkout-deployment'}));self.assertEqual(b['improvement']['after']['verdict'],'BLOCK');self.assertGreater(b['improvement']['edges_added'],0)
                c=unpack(await session.call_tool('verify_evidence',{'claim_id':'checkout-deployment'}));self.assertEqual(c['assessment']['verdict'],'BLOCK')
                impact=unpack(await session.call_tool('scan_impact',{'scan_id':'demo/scan'}))
                self.assertEqual(impact['subject'],CHECKOUT_SUBJECT)
                self.assertEqual([item['claim_id'] for item in impact['impacted_claims']],
                                 ['checkout-deployment','checkout-security'])
                for item in impact['impacted_claims']:
                    self.assertEqual(item['path'][-1],{'from':'demo/ci','to':'demo/scan','type':'REQUIRES'})
                imported=unpack(await session.call_tool('verify_evidence',{'claim_id':'github-release'}))
                self.assertEqual(imported['assessment']['verdict'],'REVIEW_REQUIRED')
                self.assertEqual(imported['assessment']['verified_roots'],[])
                self.assertEqual(imported['provenance']['workflow_evidence'],[workflow])
                source=unpack(await session.call_tool('trace_sources',{'source_id':workflow['external_id']}))
                self.assertEqual(source['provenance']['workflow_evidence'],[workflow])
    asyncio.run(run())
