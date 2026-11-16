"""Record the real, freshly seeded HydraWitness walkthrough. No mocked API responses."""
import os
from pathlib import Path
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[2];out=root/'demo/walkthrough'
url=os.environ.get('HYDRAWITNESS_DEMO_URL','http://127.0.0.1:10000/')
with sync_playwright() as p:
 browser=p.chromium.launch(headless=True,executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')
 context=browser.new_context(viewport={'width':1440,'height':900},record_video_dir=str(out),record_video_size={'width':1440,'height':900},reduced_motion='reduce')
 page=context.new_page();page.goto(url,wait_until='domcontentloaded');page.wait_for_function("document.querySelector('#verdictText').textContent==='REVIEW REQUIRED'",timeout=30000)
 page.wait_for_timeout(2500);page.locator('#startTour').click();page.wait_for_timeout(4500)
 page.locator('#tourNext').click();page.wait_for_timeout(4500)
 page.locator('#tourNext').click();page.wait_for_timeout(4500)
 page.locator('#tourNext').click();page.wait_for_function("document.querySelector('#tourTitle').textContent==='Follow the evidence.'",timeout=30000);page.wait_for_timeout(6500)
 page.locator('#tourNext').click();page.wait_for_timeout(6500)
 page.locator('#tourNext').click();page.wait_for_timeout(3500)
 page.locator('#tourNext').click();page.wait_for_timeout(2500)
 path=page.video.path();context.close();browser.close();target=out/'site.webm';Path(path).replace(target);print(target)
