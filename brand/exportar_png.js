// Rasteriza os SVGs da marca em PNG (ícones, splash, favicon, imagem social, folha de identidade).
// Uso:  node exportar_png.js <pasta-brand>
// Requer: playwright com Chromium instalado.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');

const B = path.resolve(process.argv[2] || '.');
const SVG = (n) => fs.readFileSync(path.join(B, 'svg', n), 'utf8');
const PAL = JSON.parse(fs.readFileSync(path.join(B, 'paleta.json'), 'utf8'));
// Fonte embutida em base64: o Chromium bloqueia file:// a partir de páginas about:blank.
const FONTE = (w) => 'data:font/ttf;base64,' + fs.readFileSync(path.join(B, 'fontes', `Sora_${w}.ttf`)).toString('base64');
const OUT = path.join(B, 'png');
fs.mkdirSync(OUT, { recursive: true });

const simb = (nome, tam) => SVG(nome).replace('<svg ', `<svg width="${tam}" height="${tam}" `);
const logo = (nome, larg) => SVG(nome).replace('<svg ', `<svg width="${larg}" `);

const FONTES_CSS = `
@font-face{font-family:Sora;font-weight:400;src:url(${FONTE('400Regular')})}
@font-face{font-family:Sora;font-weight:600;src:url(${FONTE('600SemiBold')})}
@font-face{font-family:Sora;font-weight:700;src:url(${FONTE('700Bold')})}
@font-face{font-family:Sora;font-weight:800;src:url(${FONTE('800ExtraBold')})}`;

const base = (w, h, bg, corpo, extra = '') => `<!doctype html><html><head><meta charset="utf-8"><style>
${FONTES_CSS}
html,body{margin:0;padding:0;width:${w}px;height:${h}px;background:${bg};font-family:Sora,sans-serif;overflow:hidden}
.c{width:${w}px;height:${h}px;display:flex;align-items:center;justify-content:center}
${extra}</style></head><body>${corpo}</body></html>`;

const jobs = [
  // ícones do app
  ['icone-1024.png', 1024, 1024, false,
    base(1024, 1024, PAL.tinta, `<div class="c">${simb('simbolo-escuro.svg', 680)}</div>`)],
  ['icone-foreground-1024.png', 1024, 1024, true,
    base(1024, 1024, 'transparent', `<div class="c">${simb('simbolo-escuro.svg', 717)}</div>`)],
  ['icone-monocromatico-1024.png', 1024, 1024, true,
    base(1024, 1024, 'transparent', `<div class="c">${simb('simbolo-mono-branco.svg', 717)}</div>`)],
  // splash nativa
  ['splash-simbolo-640.png', 640, 640, true,
    base(640, 640, 'transparent', `<div class="c">${simb('simbolo-escuro.svg', 640)}</div>`)],
  ['splash-android12-960.png', 960, 960, true,
    base(960, 960, 'transparent', `<div class="c">${simb('simbolo-escuro.svg', 480)}</div>`)],
  // web
  ['favicon-32.png', 32, 32, true, base(32, 32, 'transparent', `<div class="c">${SVG('favicon.svg').replace('<svg ', '<svg width="32" height="32" ')}</div>`)],
  ['apple-touch-icon-180.png', 180, 180, false,
    base(180, 180, PAL.tinta, `<div class="c">${simb('simbolo-escuro.svg', 128)}</div>`)],
  ['icone-192.png', 192, 192, true, base(192, 192, 'transparent', `<div class="c">${SVG('favicon.svg').replace('<svg ', '<svg width="192" height="192" ')}</div>`)],
  ['icone-512.png', 512, 512, true, base(512, 512, 'transparent', `<div class="c">${SVG('favicon.svg').replace('<svg ', '<svg width="512" height="512" ')}</div>`)],
  ['icone-maskable-512.png', 512, 512, false,
    base(512, 512, PAL.tinta, `<div class="c">${simb('simbolo-escuro.svg', 300)}</div>`)],
  // logotipos
  ['logotipo-claro.png', 1280, 240, true, base(1280, 240, 'transparent', `<div class="c">${logo('logotipo-claro.svg', 1280)}</div>`)],
  ['logotipo-escuro.png', 1280, 240, true, base(1280, 240, 'transparent', `<div class="c">${logo('logotipo-escuro.svg', 1280)}</div>`)],
  // imagem social
  ['og-image-1200x630.png', 1200, 630, false,
    base(1200, 630, PAL.tinta, `
      <div style="position:absolute;inset:0;background:radial-gradient(900px 600px at 85% 20%, ${PAL.floresta} 0%, ${PAL.tinta} 70%)"></div>
      <div style="position:absolute;left:80px;top:150px">${logo('logotipo-escuro.svg', 640)}</div>
      <div style="position:absolute;left:80px;top:330px;width:620px;color:${PAL.areia};font-size:40px;font-weight:600;line-height:1.25">
        Triagem visual de lesões cutâneas, direto no navegador.</div>
      <div style="position:absolute;left:80px;top:500px;color:${PAL.agua_clara};font-size:24px;font-weight:400">
        Ferramenta de apoio à pesquisa · não é diagnóstico</div>
      <div style="position:absolute;right:70px;top:110px">${simb('simbolo-escuro.svg', 360)}</div>`)],
];

// folha de identidade (documentação)
const swatch = (nome, hex, claro) => `<div style="width:170px;height:110px;background:${hex};border-radius:12px;
  color:${claro ? PAL.tinta : '#fff'};border:1px solid ${PAL.areia_escura};padding:12px;box-sizing:border-box;font-size:14px;display:flex;flex-direction:column;justify-content:flex-end">
  <b style="font-weight:700">${nome}</b><span style="font-weight:400">${hex}</span></div>`;
const folha = base(1600, 1100, PAL.areia, `
  <div style="padding:56px 64px;color:${PAL.tinta}">
    <div style="display:flex;gap:56px;align-items:center">
      <div style="background:${PAL.areia};border:1px solid ${PAL.areia_escura};border-radius:20px;padding:36px">${logo('logotipo-claro.svg', 640)}</div>
      <div style="background:${PAL.tinta};border-radius:20px;padding:36px">${logo('logotipo-escuro.svg', 640)}</div>
    </div>
    <div style="display:flex;gap:28px;margin-top:40px;align-items:center">
      <div style="background:${PAL.areia};border:1px solid ${PAL.areia_escura};border-radius:20px;padding:24px">${simb('simbolo-claro.svg', 200)}</div>
      <div style="background:${PAL.tinta};border-radius:20px;padding:24px">${simb('simbolo-escuro.svg', 200)}</div>
      <div style="background:${PAL.floresta};border-radius:20px;padding:24px">${simb('simbolo-mono-branco.svg', 200)}</div>
      <div style="width:200px;height:200px;border-radius:44px;background:${PAL.tinta};display:flex;align-items:center;justify-content:center">${simb('simbolo-escuro.svg', 150)}</div>
      <div style="font-size:15px;line-height:1.6;max-width:420px">
        <b style="font-size:20px">Construção</b><br>Colchetes de enquadramento (triagem visual), lente circular (campo dermatoscópico),
        mancha em coral (lesão) e linha de varredura (SCAN).</div>
    </div>
    <div style="display:flex;gap:14px;margin-top:40px;flex-wrap:wrap">
      ${swatch('tinta', PAL.tinta, false)}${swatch('floresta', PAL.floresta, false)}${swatch('água', PAL.agua, false)}
      ${swatch('água clara', PAL.agua_clara, true)}${swatch('areia', PAL.areia, true)}${swatch('areia escura', PAL.areia_escura, true)}
      ${swatch('coral', PAL.coral, true)}${swatch('âmbar', PAL.ambar, false)}
    </div>
    <div style="margin-top:36px;display:flex;gap:56px;align-items:baseline">
      <div style="font-size:64px;font-weight:800;line-height:1">Aa <span style="font-size:20px;font-weight:400">Sora ExtraBold</span></div>
      <div style="font-size:44px;font-weight:600;line-height:1">Aa <span style="font-size:20px;font-weight:400">Sora SemiBold</span></div>
      <div style="font-size:30px;font-weight:400;line-height:1">Texto corrido em Sora Regular. 0123456789</div>
    </div>
  </div>`);
jobs.push(['folha-de-identidade.png', 1600, 1100, false, folha]);

(async () => {
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  for (const [nome, w, h, transp, html] of jobs) {
    const page = await browser.newPage({ viewport: { width: w, height: h }, deviceScaleFactor: 1 });
    await page.setContent(html, { waitUntil: 'load' });
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: path.join(OUT, nome), omitBackground: transp, clip: { x: 0, y: 0, width: w, height: h } });
    await page.close();
    console.log('ok', nome, `${w}x${h}`);
  }
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
