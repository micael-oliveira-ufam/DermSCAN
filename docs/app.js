// DermSCAN: inferência local com onnxruntime-web (WASM, 1 thread).
// O pré-processamento segue model/modelo_info.json. Qualquer alteração ali deve ser replicada aqui e no app Flutter.

const CFG = {
  modeloUrl: "model/vit_b16_int8.onnx",
  infoUrl: "model/modelo_info.json",
};

let sessao = null;
let info = null;

const el = (id) => document.getElementById(id);

// ---------------------------------------------------------------------------
// Reamostragem bilinear com antialias, no mesmo espírito do PIL (Image.resize, BILINEAR),
// usada pelo torchvision.Resize. Implementação em ponto flutuante:
//  - filtro triangular de suporte escalado quando há redução;
//  - pesos normalizados por linha/coluna;
//  - passe horizontal (float), depois vertical, e arredondamento final para 0..255.
// Diferença medida contra o PIL 13.0.0: no máximo 1 nível de cor (em ~13% dos pixels).
// Para o app Flutter, usar exatamente este algoritmo (ver README).
// ---------------------------------------------------------------------------

function filtroBilinear(x) {
  if (x < 0) x = -x;
  return x < 1 ? 1 - x : 0;
}

function coeficientesPIL(entrada, saida) {
  const escala = entrada / saida;
  const filtro = Math.max(escala, 1.0);
  const suporte = 1.0 * filtro;
  const limites = [];
  const pesos = [];
  for (let i = 0; i < saida; i++) {
    const centro = (i + 0.5) * escala;
    let xmin = Math.trunc(centro - suporte + 0.5);
    if (xmin < 0) xmin = 0;
    let xmax = Math.trunc(centro + suporte + 0.5);
    if (xmax > entrada) xmax = entrada;
    xmax -= xmin;
    const k = new Array(xmax);
    let soma = 0;
    for (let x = 0; x < xmax; x++) {
      const w = filtroBilinear((x + xmin - centro + 0.5) / filtro);
      k[x] = w;
      soma += w;
    }
    if (soma !== 0) for (let x = 0; x < xmax; x++) k[x] /= soma;
    limites.push([xmin, xmax]);
    pesos.push(k);
  }
  return { limites, pesos };
}

// src: Uint8Array RGB intercalado (sw x sh). Retorna Uint8Array RGB (dw x dh).
function reamostrarPIL(src, sw, sh, dw, dh) {
  const H = coeficientesPIL(sw, dw);
  const V = coeficientesPIL(sh, dh);

  // passe horizontal: sh linhas x dw colunas (float)
  const tmp = new Float32Array(sh * dw * 3);
  for (let y = 0; y < sh; y++) {
    const base = y * sw * 3;
    for (let x = 0; x < dw; x++) {
      const [xmin, n] = H.limites[x];
      const k = H.pesos[x];
      for (let c = 0; c < 3; c++) {
        let s = 0;
        for (let j = 0; j < n; j++) s += src[base + (xmin + j) * 3 + c] * k[j];
        tmp[(y * dw + x) * 3 + c] = s;
      }
    }
  }

  // passe vertical: dh linhas x dw colunas, depois arredondamento para 0..255
  const out = new Uint8Array(dh * dw * 3);
  for (let yy = 0; yy < dh; yy++) {
    const [ymin, n] = V.limites[yy];
    const k = V.pesos[yy];
    for (let x = 0; x < dw; x++) {
      for (let c = 0; c < 3; c++) {
        let s = 0;
        for (let j = 0; j < n; j++) s += tmp[((ymin + j) * dw + x) * 3 + c] * k[j];
        const v = Math.floor(s + 0.5);
        out[(yy * dw + x) * 3 + c] = v < 0 ? 0 : v > 255 ? 255 : v;
      }
    }
  }
  return out;
}

// Pré-processamento equivalente a: convert('RGB') -> Resize((224,224)) -> ToTensor() -> Normalize.
// ToTensor produz CHW em [0,1]; a normalização é aplicada canal a canal.
function preprocessar(imagem) {
  const S = info.entrada.tamanho;
  const w = imagem.naturalWidth;
  const h = imagem.naturalHeight;
  const canvas = document.createElement("canvas");
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext("2d", { willReadFrequently: true });
  ctx.drawImage(imagem, 0, 0, w, h); // tamanho nativo, sem reamostragem do navegador
  const rgba = ctx.getImageData(0, 0, w, h).data;
  const rgb = new Uint8Array(w * h * 3);
  for (let p = 0, q = 0; p < w * h; p++, q += 3) {
    rgb[q] = rgba[p * 4];
    rgb[q + 1] = rgba[p * 4 + 1];
    rgb[q + 2] = rgba[p * 4 + 2];
  }
  const r = reamostrarPIL(rgb, w, h, S, S);

  const medias = info.entrada.media;
  const desvios = info.entrada.desvio;
  const N = S * S;
  const tensor = new Float32Array(3 * N);
  for (let p = 0; p < N; p++) {
    for (let c = 0; c < 3; c++) {
      tensor[c * N + p] = (r[p * 3 + c] / 255 - medias[c]) / desvios[c];
    }
  }
  return new ort.Tensor("float32", tensor, [1, 3, S, S]);
}

function softmax(logits, temperatura) {
  const z = logits.map((v) => v / temperatura);
  const m = Math.max(...z);
  const e = z.map((v) => Math.exp(v - m));
  const soma = e.reduce((a, b) => a + b, 0);
  return e.map((v) => v / soma);
}

// Ponto de entrada também usado pelos testes de paridade.
async function classificarImagem(imagem) {
  const x = preprocessar(imagem);
  const t0 = performance.now();
  const saida = await sessao.run({ [sessao.inputNames[0]]: x });
  const ms = performance.now() - t0;
  const logits = Array.from(saida[sessao.outputNames[0]].data);
  const probs = softmax(logits, info.calibracao.temperatura);
  return { logits, probs, ms };
}

async function carregarModelo() {
  try {
    info = await (await fetch(CFG.infoUrl)).json();
    ort.env.wasm.numThreads = 1; // GitHub Pages não envia COOP/COEP, logo sem SharedArrayBuffer
    // URL absoluta: o loader importa estes arquivos como módulos, e "vendor/" puro não resolve.
    ort.env.wasm.wasmPaths = new URL("vendor/", document.baseURI).href;
    sessao = await ort.InferenceSession.create(CFG.modeloUrl, {
      executionProviders: ["wasm"],
      graphOptimizationLevel: "all",
    });
    el("status").textContent = "Modelo carregado. Selecione uma imagem.";
    el("arquivo").disabled = false;
    window.classificarImagem = classificarImagem; // exposto para testes
    window.reamostrarPIL = reamostrarPIL;
    window.modeloPronto = true;
  } catch (erro) {
    el("status").textContent = "Falha ao carregar o modelo: " + erro.message;
    window.modeloPronto = false;
  }
}

function mostrarResultado(res) {
  const nomes = info.nomes_exibicao;
  const ordem = res.probs
    .map((p, i) => ({ classe: info.classes[i], p }))
    .sort((a, b) => b.p - a.p);
  const topo = ordem[0];
  const limiar = info.limiar_inconclusivo;

  const principal = el("principal");
  if (topo.p < limiar) {
    principal.textContent =
      `Resultado inconclusivo: a maior probabilidade é ${nomes[topo.classe]} (${(topo.p * 100).toFixed(1)}%), abaixo do limiar de ${(limiar * 100).toFixed(0)}%.`;
  } else {
    principal.textContent =
      `Classe mais provável: ${nomes[topo.classe]} (${(topo.p * 100).toFixed(1)}%).`;
  }

  const lista = el("ranking");
  lista.innerHTML = "";
  for (const { classe, p } of ordem) {
    const li = document.createElement("li");
    li.innerHTML =
      `<span class="nome"></span>` +
      `<div class="barra"><div class="preench" style="width:${(p * 100).toFixed(1)}%"></div></div>` +
      `<span class="valor"></span>`;
    li.querySelector(".nome").textContent = nomes[classe];
    li.querySelector(".valor").textContent = `${(p * 100).toFixed(1)}%`;
    lista.appendChild(li);
  }

  el("detalhe").textContent =
    `Tempo de inferência: ${res.ms.toFixed(0)} ms. Probabilidades com temperatura ${info.calibracao.temperatura.toFixed(3)} ` +
    `(calibrada na validação). Resultado indicativo, para pesquisa.`;
  el("bloco-resultado").hidden = false;
}

el("arquivo").addEventListener("change", async (evento) => {
  const arquivo = evento.target.files[0];
  if (!arquivo || !sessao) return;
  el("status").textContent = "Classificando…";
  const url = URL.createObjectURL(arquivo);
  const img = el("imagem");
  img.src = url;
  el("bloco-imagem").hidden = false;
  try {
    await img.decode();
    const res = await classificarImagem(img);
    mostrarResultado(res);
    el("status").textContent = "Concluído.";
  } catch (erro) {
    el("status").textContent = "Não foi possível classificar esta imagem: " + erro.message;
  } finally {
    URL.revokeObjectURL(url);
  }
});

carregarModelo();
