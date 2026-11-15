"""Exercise MCP over real stdio and real HydraDB in a fresh scope."""
import asyncio,os,sys,unittest,uuid
from pathlib import Path
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from hydrawitness.engine import Witness,Registry
ROOT=Path(__file__).resolve().parent.parent

def unpack(r):
    if r.isError: raise AssertionError(r.content)
    return r.structuredContent

class ProtocolTest(unittest.TestCase):
 def test_stdio_tools(self):
    scope='mcp-test-'+uuid.uuid4().hex
    w=Witness(scope,Registry(ROOT/'datasets/controlled'))
    w.seed_claim('checkout-deployment',['demo/qa','demo/security-summary'])
    async def run():
        params=StdioServerParameters(command=sys.executable,args=['-m','hydrawitness.mcp_server'],env={**os.environ,'HYDRAWITNESS_SCOPE':scope},cwd=ROOT)
        async with stdio_client(params) as (read,write):
            async with ClientSession(read,write) as session:
                await session.initialize()
                tools=await session.list_tools(); self.assertEqual({t.name for t in tools.tools},{'verify_evidence','trace_sources','assess_and_improve'})
                a=unpack(await session.call_tool('verify_evidence',{'claim_id':'checkout-deployment'})); self.assertEqual(a['assessment']['verdict'],'REVIEW_REQUIRED')
                t=unpack(await session.call_tool('trace_sources',{'claim_id':'checkout-deployment'}));self.assertTrue(t['provenance']['paths'])
                bad=await session.call_tool('assess_and_improve',{'claim_id':'checkout-deployment','max_iterations':6});self.assertTrue(bad.isError)
                b=unpack(await session.call_tool('assess_and_improve',{'claim_id':'checkout-deployment'}));self.assertEqual(b['improvement']['after']['verdict'],'BLOCK');self.assertGreater(b['improvement']['edges_added'],0)
                c=unpack(await session.call_tool('verify_evidence',{'claim_id':'checkout-deployment'}));self.assertEqual(c['assessment']['verdict'],'BLOCK')
    asyncio.run(run())
