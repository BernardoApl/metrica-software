// G2 (RQ106): distribuição da estatística sob H0, região de rejeição e área do p-valor.
// Dados gerados por codigo-fonte/analise/rq106_dados_g2.py em dados/g2.js (window.G2_DADOS).
(function () {
  'use strict';
  var DADOS = window.G2_DADOS;
  var raiz = document.getElementById('g2');
  if (!raiz) return;
  if (!DADOS) {
    raiz.querySelector('.g2-texto').textContent =
      'Dados do G2 ausentes. Rode: python codigo-fonte/analise/rq106_dados_g2.py';
    return;
  }

  var NS = 'http://www.w3.org/2000/svg';
  var L = 520, A = 290, M = { e: 56, d: 18, s: 18, i: 50 };
  var LP = L - M.e - M.d, AP = A - M.s - M.i;

  function num(x, casas) {
    return Number(x).toLocaleString('pt-BR', { maximumFractionDigits: casas === undefined ? 2 : casas }).replace('-', '−');
  }
  function pTexto(p) {
    if (p >= 1e-4) return num(p, 3);
    var e = p.toExponential(1).split('e');
    return e[0].replace('.', ',') + ' × 10^' + Number(e[1]);
  }
  function pHtml(p) {
    if (p >= 1e-4) return num(p, 3);
    var e = p.toExponential(1).split('e');
    return e[0].replace('.', ',') + ' × 10<sup>' + Number(e[1]).toString().replace('-', '−') + '</sup>';
  }
  function el(nome, attrs, pai) {
    var n = document.createElementNS(NS, nome);
    for (var k in attrs) n.setAttribute(k, attrs[k]);
    if (pai) pai.appendChild(n);
    return n;
  }
  function texto(pai, x, y, conteudo, attrs) {
    var t = el('text', Object.assign({ x: x, y: y }, attrs || {}), pai);
    t.textContent = conteudo;
    return t;
  }
  function escala(d0, d1, r0, r1) {
    return function (v) { return r0 + (v - d0) / (d1 - d0) * (r1 - r0); };
  }

  function eixos(svg, sx, sy, xTicks, yMax, rotX, rotY) {
    var g = el('g', { 'class': 'g2-eixo' }, svg);
    for (var i = 0; i <= 4; i++) {
      var v = yMax * i / 4, y = sy(v);
      el('line', { x1: M.e, x2: L - M.d, y1: y, y2: y, 'class': 'g2-grade' }, g);
      texto(g, M.e - 6, y + 4, num(v, v < .01 ? 4 : 2), { 'text-anchor': 'end' });
    }
    xTicks.forEach(function (v) {
      texto(g, sx(v), A - M.i + 18, num(v, 1), { 'text-anchor': 'middle' });
    });
    el('line', { x1: M.e, x2: L - M.d, y1: sy(0), y2: sy(0), 'class': 'g2-base' }, g);
    texto(g, M.e + LP / 2, A - 8, rotX, { 'text-anchor': 'middle', 'class': 'g2-rotulo' });
    texto(g, 14, M.s + AP / 2, rotY, { 'text-anchor': 'middle', 'class': 'g2-rotulo',
      transform: 'rotate(-90 14 ' + (M.s + AP / 2) + ')' });
  }

  function regiao(svg, sx, x0, x1) {
    var a = Math.max(M.e, Math.min(sx(x0), sx(x1))), b = Math.min(L - M.d, Math.max(sx(x0), sx(x1)));
    if (b > a) el('rect', { x: a, y: M.s, width: b - a, height: AP, 'class': 'g2-regiao' }, svg);
  }
  function critico(svg, x) {
    el('line', { x1: x, x2: x, y1: M.s, y2: M.s + AP, 'class': 'g2-critico' }, svg);
  }
  function observado(svg, sx, v, min, max, rotulo) {
    var x = sx(v), fora = v > max || v < min, ancora = 'middle';
    if (fora) { x = v > max ? L - M.d : M.e; ancora = v > max ? 'end' : 'start'; }
    el('line', { x1: x, x2: x, y1: M.s + 14, y2: M.s + AP, 'class': 'g2-obs' }, svg);
    if (x > L - M.d - 60) ancora = 'end';
    else if (x < M.e + 60) ancora = 'start';
    var dx = ancora === 'end' ? -4 : ancora === 'start' ? 4 : 0;
    texto(svg, x + dx, M.s + 10, fora ? (v > max ? rotulo + ' →' : '← ' + rotulo) : rotulo,
      { 'text-anchor': ancora, 'class': 'g2-obs-rotulo' });
  }

  function dica(svg, painel, pontos) {
    var tip = painel.querySelector('.g2-dica');
    var guia = el('line', { y1: M.s, y2: M.s + AP, 'class': 'g2-guia', visibility: 'hidden' }, svg);
    var alvo = el('rect', { x: M.e, y: M.s, width: LP, height: AP, fill: 'transparent' }, svg);
    function mover(ev) {
      var r = svg.getBoundingClientRect(), x = (ev.clientX - r.left) / r.width * L;
      var melhor = pontos[0], dist = Infinity;
      for (var i = 0; i < pontos.length; i++) {
        var d = Math.abs(pontos[i].px - x);
        if (d < dist) { dist = d; melhor = pontos[i]; }
      }
      guia.setAttribute('x1', melhor.px); guia.setAttribute('x2', melhor.px);
      guia.setAttribute('visibility', 'visible');
      tip.innerHTML = melhor.html;
      tip.hidden = false;
      var pr = painel.getBoundingClientRect();
      var esquerda = ev.clientX - pr.left + 12;
      if (esquerda + tip.offsetWidth > pr.width) esquerda = ev.clientX - pr.left - tip.offsetWidth - 12;
      tip.style.left = Math.max(0, esquerda) + 'px';
      tip.style.top = (ev.clientY - pr.top - 10) + 'px';
    }
    alvo.addEventListener('pointermove', mover);
    alvo.addEventListener('pointerleave', function () { tip.hidden = true; guia.setAttribute('visibility', 'hidden'); });
  }

  function desenharT(painel, t) {
    var svg = painel.querySelector('svg');
    svg.textContent = '';
    var yMax = Math.max.apply(null, t.densidade) * 1.12;
    var x0 = t.x[0], x1 = t.x[t.x.length - 1];
    var sx = escala(x0, x1, M.e, L - M.d), sy = escala(0, yMax, M.s + AP, M.s);
    eixos(svg, sx, sy, [-4, -2, 0, 2, 4], yMax, 'Estatística t (adimensional, ' + t.gl + ' gl)', 'Densidade');
    regiao(svg, sx, x0, -t.critico);
    regiao(svg, sx, t.critico, x1);
    var obs = Math.abs(t.observado);
    function area(filtro) {
      var pts = [];
      t.x.forEach(function (x, i) { if (filtro(x)) pts.push(sx(x) + ',' + sy(t.densidade[i])); });
      if (pts.length < 2) return;
      var p0 = pts[0].split(',')[0], p1 = pts[pts.length - 1].split(',')[0];
      el('polygon', { points: p0 + ',' + sy(0) + ' ' + pts.join(' ') + ' ' + p1 + ',' + sy(0), 'class': 'g2-p-area serie-t' }, svg);
    }
    area(function (x) { return x <= -obs; });
    area(function (x) { return x >= obs; });
    var d = t.x.map(function (x, i) { return (i ? 'L' : 'M') + sx(x).toFixed(1) + ',' + sy(t.densidade[i]).toFixed(1); }).join('');
    el('path', { d: d, 'class': 'g2-curva serie-t' }, svg);
    critico(svg, sx(-t.critico)); critico(svg, sx(t.critico));
    observado(svg, sx, t.observado, x0, x1, 't obs = ' + num(t.observado));
    var pontos = [];
    for (var i = 0; i < t.x.length; i += 2) {
      var x = t.x[i];
      pontos.push({ px: sx(x), html: '<strong>t = ' + num(x) + '</strong><br>densidade ' + num(t.densidade[i], 4) +
        (Math.abs(x) > t.critico ? '<br>na região de rejeição' : '') });
    }
    dica(svg, painel, pontos);
    svg.setAttribute('aria-label', 'Distribuição t com ' + t.gl + ' graus de liberdade. Região de rejeição |t| > ' +
      num(t.critico, 3) + '. t observado ' + num(t.observado) + ', p-valor ' + pTexto(t.p_valor) + '.');
  }

  function desenharW(painel, w) {
    var svg = painel.querySelector('svg');
    svg.textContent = '';
    var passo = w.valores.length > 1 ? w.valores[1] - w.valores[0] : 1;
    var yMax = Math.max.apply(null, w.probabilidade) * 1.12;
    var sx = escala(-passo / 2, w.total + passo / 2, M.e, L - M.d), sy = escala(0, yMax, M.s + AP, M.s);
    var ticks = [];
    for (var k = 0; k <= w.total; k += 100) ticks.push(k);
    eixos(svg, sx, sy, ticks, yMax, 'Estatística W+ (soma dos postos positivos)', 'Probabilidade');
    if (w.limite_inferior !== null) {
      regiao(svg, sx, -passo / 2, w.limite_inferior + passo / 2);
      regiao(svg, sx, w.limite_superior - passo / 2, w.total + passo / 2);
    }
    var baixo = Math.min(w.observado, w.espelho), alto = Math.max(w.observado, w.espelho);
    var larg = Math.max(.6, sx(passo) - sx(0));
    var base = el('g', { 'class': 'serie-w' }, svg), pontos = [];
    w.valores.forEach(function (v, i) {
      var y = sy(w.probabilidade[i]);
      var noP = v <= baixo + 1e-9 || v >= alto - 1e-9;
      el('rect', { x: sx(v) - larg / 2, y: y, width: larg, height: sy(0) - y, 'class': noP ? 'g2-p-area' : 'g2-barra' }, base);
      var rej = w.limite_inferior !== null && (v <= w.limite_inferior || v >= w.limite_superior);
      pontos.push({ px: sx(v), html: '<strong>W+ = ' + num(v, 1) + '</strong><br>P(W+ = ' + num(v, 1) + ') = ' +
        pHtml(w.probabilidade[i]) + (rej ? '<br>na região de rejeição' : '') });
    });
    if (w.limite_inferior !== null) {
      critico(svg, sx(w.limite_inferior + passo / 2)); critico(svg, sx(w.limite_superior - passo / 2));
    }
    observado(svg, sx, w.observado, 0, w.total, 'W+ obs = ' + num(w.observado, 1));
    dica(svg, painel, pontos);
    svg.setAttribute('aria-label', 'Distribuição exata de W+ sob H0, de 0 a ' + num(w.total, 1) +
      '. Região de rejeição W+ ≤ ' + num(w.limite_inferior, 1) + ' ou W+ ≥ ' + num(w.limite_superior, 1) +
      '. W+ observado ' + num(w.observado, 1) + ', p-valor ' + pTexto(w.p_valor) + '.');
  }

  function explicar(a) {
    var t = a.t, w = a.wilcoxon, alfa = num(DADOS.alfa);
    var frases = [
      'O <strong>t pareado</strong> compara a média das diferenças d = t<sub>sem</sub> − t<sub>com</sub>: sob H0 a estatística segue uma t de Student com ' +
        t.gl + ' gl e, como H1 é bilateral, a região de rejeição são as duas caudas, |t| &gt; ' + num(t.critico, 3) + '.',
      'O <strong>Wilcoxon pareado</strong> compara os postos de |d|: sob H0 cada diferença tem sinal + ou − com chance 1/2, W+ se concentra em torno de ' +
        num(w.total / 2, 1) + ' e rejeitamos se W+ ≤ ' + num(w.limite_inferior, 1) + ' ou W+ ≥ ' + num(w.limite_superior, 1) +
        ' (nível real ' + num(w.nivel_real * 100, 2) + '%, pois a distribuição é discreta).'
    ];
    var foraEixo = Math.abs(t.observado) > t.x[t.x.length - 1];
    if (!t.rejeita_h0 && !w.rejeita_h0) {
      frases.push('Nesta amostra, t = ' + num(t.observado) + ' e W+ = ' + num(w.observado, 1) + ' caem fora das regiões de rejeição. ' +
        'As áreas coloridas são os p-valores (' + pHtml(t.p_valor) + ' e ' + pHtml(w.p_valor) + '): a probabilidade de, <em>se H0 fosse verdadeira</em>, ' +
        'obter uma estatística tão ou mais distante do centro quanto a observada; ambos acima de α = ' + alfa + ', então não rejeitamos H0.');
    } else {
      frases.push('Nesta amostra, t = ' + num(t.observado) + (foraEixo ? ' fica muito além do eixo' : '') + ' e W+ = ' + num(w.observado, 1) +
        (w.observado >= w.total ? ' é o máximo possível (todas as diferenças positivas)' : '') +
        ': os p-valores (' + pHtml(t.p_valor) + ' e ' + pHtml(w.p_valor) + ') são áreas pequenas demais para aparecer no gráfico, ' +
        'e os dois testes rejeitam H0 a α = ' + alfa + '.');
    }
    frases.push('O p-valor não é a probabilidade de H0 ser verdadeira nem mede o tamanho do efeito.');
    return frases.join(' ');
  }

  function tabela(a) {
    var t = a.t, w = a.wilcoxon;
    function linha(nome, cls, stat, regiao, p, rej) {
      return '<tr><th scope="row"><span class="g2-ponto ' + cls + '" aria-hidden="true"></span>' + nome + '</th><td>' + stat +
        '</td><td>' + regiao + '</td><td>' + p + '</td><td>' + (rej ? 'rejeita H0' : 'não rejeita H0') + '</td></tr>';
    }
    return linha('t pareado', 'serie-t', 't = ' + num(t.observado, 3), '|t| &gt; ' + num(t.critico, 3), pHtml(t.p_valor), t.rejeita_h0) +
      linha('Wilcoxon pareado', 'serie-w', 'W+ = ' + num(w.observado, 1), 'W+ ≤ ' + num(w.limite_inferior, 1) + ' ou ≥ ' + num(w.limite_superior, 1),
        pHtml(w.p_valor) + '<br><small>' + w.metodo + '</small>', w.rejeita_h0);
  }

  function mostrar(chave) {
    var a = DADOS.amostras[chave];
    desenharT(raiz.querySelector('[data-teste="t"]'), a.t);
    desenharW(raiz.querySelector('[data-teste="w"]'), a.wilcoxon);
    raiz.querySelector('.g2-texto').innerHTML = explicar(a);
    raiz.querySelector('.g2-tabela tbody').innerHTML = tabela(a);
    raiz.querySelector('.g2-tabela caption').textContent = 'Resumo do G2 — ' + a.rotulo + ' (' + a.n_pares + ' pares)';
    raiz.querySelectorAll('.g2-opcoes button').forEach(function (b) {
      b.setAttribute('aria-pressed', String(b.dataset.amostra === chave));
    });
  }

  raiz.querySelectorAll('.g2-opcoes button').forEach(function (b) {
    b.addEventListener('click', function () { mostrar(b.dataset.amostra); });
  });
  mostrar('simulada_h0');
})();
