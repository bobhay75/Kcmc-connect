'use strict';
// Browser-engine acceptance against the isolated build; never contacts a live app.
const assert = require('node:assert/strict');
const {spawn,execFileSync} = require('node:child_process');
const fs=require('node:fs'), os=require('node:os'), path=require('node:path'), net=require('node:net');
const {chromium,webkit,devices}=require('playwright');
const root=path.resolve(__dirname,'..');

async function main(){
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'kcmc-mobile-'));
  let server;
  try{
    const mount=path.join(tmp,'kcmc-connect-stage');
    const privateDir=path.join(tmp,'private');
    fs.mkdirSync(privateDir,{mode:0o700});
    execFileSync('python3',[path.join(root,'tools/basic-handoff/build.py'),mount],{stdio:'inherit'});
    const port=await new Promise((resolve,reject)=>{
      const s=net.createServer();
      s.on('error',reject);
      s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port));});
    });
    const origin='http://127.0.0.1:'+port;
    const base=origin+'/kcmc-connect-stage/';
    server=spawn('php',['-S','127.0.0.1:'+port,'-t',tmp],{env:{...process.env,KCMC_PRIVATE_DATA_DIR:privateDir},stdio:'ignore'});
    for(let attempt=0;;attempt++){
      try{assert.equal((await fetch(base)).status,200);break;}
      catch(e){if(attempt>=39)throw e;await new Promise(r=>setTimeout(r,100));}
    }
    for(const [engine,device] of [[chromium,'Pixel 7'],[webkit,'iPhone 13']]){
      const browser=await engine.launch();
      try{
        const context=await browser.newContext({...devices[device],serviceWorkers:'block'});
        await context.route('**/*',r=>new URL(r.request().url()).origin===origin?r.continue():r.abort());
        const page=await context.newPage();
        const errors=[];page.on('pageerror',e=>errors.push(String(e)));
        const home=await page.goto(base);
        assert.equal(home.status(),200);
        const manifestHref=await page.locator('link[rel="manifest"]').getAttribute('href');
        const manifest=await (await context.request.get(new URL(manifestHref,base).href)).json();
        assert.equal(new URL(manifest.start_url,base).href,base);
        assert.equal(new URL(manifest.scope,base).href,base);
        assert.equal(manifest.display,'standalone');
        const touchIcon=await page.locator('link[rel="apple-touch-icon"]').getAttribute('href');
        assert.equal((await context.request.get(new URL(touchIcon,base).href)).status(),200);
        for(const route of ['home','visit','watch','news','events','serve','partner']){
          await page.goto(base+'#'+route);
          await page.locator('[data-view="'+route+'"].active').waitFor({state:'visible'});
          assert.ok(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth+1),device+' overflow: '+route);
        }
        await page.goto(base+'#visit');
        const form=page.locator('form[data-kcmc-form="visit"]');
        await form.locator('[name=firstName]').fill('Synthetic');
        await form.locator('[name=lastName]').fill('Mobile');
        await form.locator('[name=email]').fill(engine.name()+'@example.test');
        await form.locator('[name=service]').selectOption({index:1});
        const saved=page.waitForResponse(r=>r.url()===base+'api/connection.php'&&r.request().method()==='POST');
        await form.locator('button[type=submit]').click();
        const result=await saved;
        assert.equal(result.status(),201,device+' visit submit');
        await page.locator('[data-visit-next-steps]').waitFor({state:'visible'});
        for(const route of ['bulletin.php','events.php','care.php','member/login.php']){
          assert.equal((await page.goto(base+route)).status(),200,device+' '+route);
        }
        assert.deepEqual(errors,[]);
        console.log('PASS: '+device+' emulation: manifest, icon, route layout, visit submission and public/staff entry pages');
      } finally {await browser.close();}
    }
  } finally{
    if(server){server.kill();if(server.exitCode===null)await new Promise(r=>server.once('exit',r));}
    fs.rmSync(tmp,{recursive:true,force:true});
  }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
