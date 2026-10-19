"""Shared assertions for the owner-approved fixed-photo welcome homepage."""
def welcome_home(page, width, check):
    home = page.locator('[data-view="home"]')
    check(home.get_by_role('heading', name='Welcome Home', exact=True).is_visible(), 'approved welcome heading is visible')
    check(home.locator('.home-worship-strip').is_visible(), 'service times are visible in the navy opening view')
    check(all(t in home.locator('.home-worship-strip').inner_text() for t in ['8:00 AM', '9:15 AM', '10:30 AM']), 'all three approved service times survive')
    photo = home.locator('[data-authentic-building]')
    check(photo.count() == 1 and photo.is_visible(), 'one fixed original church photograph is visible')
    page.wait_for_function('img=>img.complete&&img.naturalWidth>0', arg=photo.element_handle())
    check(photo.evaluate('el=>el.naturalWidth===1536&&el.naturalHeight===1229'), 'original photograph dimensions are preserved')
    check(photo.get_attribute('src') == './assets/visuals/kcmc-building-original-20261018.jpg', 'homepage uses the unmodified original photograph')
    check(home.locator('[data-hero-gallery],[data-hero-controls]').count() == 0, 'fixed building is never replaced by automatic rotation')
    check(page.locator('body').evaluate("el=>getComputedStyle(el).backgroundColor==='rgb(13, 34, 53)'"), 'public background matches the app icon navy')
    for text in ['Plan Your Visit', 'Watch Online', 'Upcoming Events', 'Prayer Requests', 'Church Family']:
        check(home.get_by_role('link', name=text).count() == 1 and home.get_by_role('link', name=text).is_visible(), text+' is a visible usable link')
    links = home.locator('.welcome-quicklinks a')
    check(links.nth(0).get_attribute('href') == '#events' and links.nth(1).get_attribute('href') == 'care.php' and links.nth(2).get_attribute('href') == '#partner', 'quick links retain existing event, protected-care and connection destinations')
    check(page.evaluate('document.documentElement.scrollWidth<=innerWidth+1'), 'welcome layout fits '+str(width)+'px')
    if width <= 760:
        check(photo.evaluate("el=>getComputedStyle(el).objectFit==='contain'"), 'phone shows the complete original photograph')
        check(home.locator('.home-cover-card').bounding_box()['y'] >= photo.bounding_box()['y']+photo.bounding_box()['height']-1, 'phone buttons and heading never cover the church')
    for link in home.locator('.welcome-hero-actions a,.welcome-quicklinks a').all():
        box=link.bounding_box()
        check(box['height']>=44 and box['x']>=-1 and box['x']+box['width']<=width+1, 'welcome controls have usable touch targets without clipping')
    first=home.locator('.welcome-hero-actions a').first
    first.focus()
    check(first.evaluate('el=>parseFloat(getComputedStyle(el).outlineWidth)>=3'), 'welcome action has visible keyboard focus')
    page.evaluate("window.scrollTo({top:0,behavior:'instant'})")
