#!/usr/bin/env python3
"""Browser smoke test for the player and the page's recovery paths.  NOT part of pytest (needs Playwright + a running instance).

    RECLMR_E2E_URL=http://127.0.0.1:8991 RECLMR_PIN=... python scripts/e2e_smoke.py

Run it against a THROWAWAY instance (own port, `RECLMR_SESSIONS_FILE=/tmp/x.json`), never the one you listen to: every login adds a
session, and an earlier round of testing filled the live session table that way. Non-GET /api calls are swallowed, so nothing is written.
"""
import os, sys
from playwright.sync_api import sync_playwright

BASE = os.environ.get('RECLMR_E2E_URL', 'http://127.0.0.1:8991').rstrip('/')
PIN = os.environ['RECLMR_PIN']
fails = []


def check(name, ok, info=''):
    print(('PASS ' if ok else 'FAIL ') + name + (('  ' + str(info)) if info and not ok else ''))
    if not ok:
        fails.append(name)


def fresh(b, state=None):
    c = b.new_context(viewport={'width': 1400, 'height': 900}, storage_state=state, service_workers='block')   # a service worker would answer from its cache and hide the aborted requests
    c.add_init_script("try{localStorage.setItem('reclmr_onboarded','1')}catch(e){}")
    return c


with sync_playwright() as p:
    b = p.chromium.launch()
    # one login for the whole run
    c0 = fresh(b); pg0 = c0.new_page(); pg0.goto(BASE + '/'); pg0.wait_for_timeout(1500)
    st = pg0.evaluate("async(pin)=>{const r=await fetch('/api/auth/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({pin})});return r.status}", PIN)
    check('login', st == 200, st)
    cookies = c0.cookies(); c0.close()

    # 1. a tab with the cookie but no sessionStorage (new tab / restarted browser): the first POST must not be a 403
    c = fresh(b); c.add_cookies(cookies); pg = c.new_page()
    pg.goto(BASE + '/'); pg.wait_for_timeout(300)
    code = pg.evaluate("async()=>{sessionStorage.clear();const r=await fetch('/api/telemetry/app-usage',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({app_id:'e2e',action:'open'})});return r.status}")
    check('first POST in a tab with no CSRF token is not refused', code == 200, code)
    c.close()

    # 2. the session disappears under a running page: the passcode screen appears
    c = fresh(b); c.add_cookies(cookies); pg = c.new_page(); pg.goto(BASE + '/'); pg.wait_for_timeout(2500)
    pg.route('**/api/system', lambda r: r.fulfill(status=401, content_type='application/json', body='{"error":"Authentication required"}'))
    pg.evaluate("()=>{fetch('/api/system')}"); pg.wait_for_timeout(600)
    shown = pg.evaluate("()=>getComputedStyle(document.getElementById('login-screen')).display")
    check('a 401 on an API call brings up the passcode screen', shown != 'none', shown)
    c.close()

    # 3. two scripts that keep failing must not reload the page forever
    c = fresh(b); c.add_cookies(cookies); pg = c.new_page()
    navs = []; pg.on('framenavigated', lambda f: navs.append(1) if f == pg.main_frame else None)
    pg.route('**/modules/music.js*', lambda r: r.abort()); pg.route('**/modules/gallery.js*', lambda r: r.abort())
    pg.goto(BASE + '/'); pg.wait_for_timeout(5000); n1 = len(navs); pg.wait_for_timeout(4000)
    check('failing scripts stop reloading and show the recovery screen', len(navs) == n1 and n1 <= 5 and pg.locator('#reclmr-crash-overlay').count() == 1, (n1, len(navs)))
    check('the recovery screen links to the reset page', pg.locator('#reclmr-crash-overlay a[href="/kill-cache"]').count() == 1)
    c.close()

    # 4. queue panel: 60 up-next rows, "Show more" adds more
    c = fresh(b); c.add_cookies(cookies); pg = c.new_page()
    errs = []; pg.on('pageerror', lambda e: errs.append(str(e)))
    pg.route('**/api/**', lambda r: r.abort() if r.request.method != 'GET' else r.continue_())
    pg.goto(BASE + '/'); pg.wait_for_timeout(2500)
    pg.evaluate("()=>openApp('music')"); pg.wait_for_function("() => window.mz && mz.loaded", timeout=20000)
    pg.evaluate("()=>mzSetTheme('spotify')")
    n = pg.evaluate("""()=>{ var t = Array.from(mz.albums.values()).reduce(function (a, al) { return a.concat(al.tracks); }, []); mz.queue = t.slice(0, 200); mz.qi = 0; mz.prefs.qp = true; mzSp.qpSync();
      return {have: mz.queue.length, rows: document.querySelectorAll('#sp-qp-list .sp-qp-row').length}; }""")
    check('queue panel lists the song playing plus 60', n['have'] < 70 or n['rows'] == 61, n)
    if n['have'] > 70:
        pg.click('#sp-qp-list .sp-qp-more'); pg.wait_for_timeout(200)
        check('"Show more" adds 60', pg.locator('#sp-qp-list .sp-qp-row').count() == 121)
    # 5. badge follows what the server says it sent
    h = pg.evaluate("""()=>{ var t = mz.queue[0]; mz.served = {f: t.f, h: 'original'}; mzSp.npQualRefresh(); var a = document.getElementById('wm-qual').textContent;
      mz.served = {f: t.f, h: 'mp3-128'}; mzSp.npQualRefresh(); return [a, document.getElementById('wm-qual').textContent]; }""")
    check('badge says MP3 only when the server sent a converted copy', 'from' in h[1] and 'from' not in h[0], h)
    # 6. the modern skin at a few widths, no page errors
    pg.evaluate("()=>mzSetTheme('modern')")
    for w in (800, 1000, 1400):
        pg.set_viewport_size({'width': w, 'height': 900}); pg.wait_for_timeout(300)
        over = pg.evaluate("()=>document.documentElement.scrollWidth > innerWidth")
        check('modern skin has no horizontal overflow at %dpx' % w, not over)
        pg.screenshot(path='/tmp/modern_%d.png' % w)
    check('no page errors', not errs, errs[:3])
    c.close(); b.close()

sys.exit(1 if fails else 0)
