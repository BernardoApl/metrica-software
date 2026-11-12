// RQ117: modo quadro. Uma tela por seção, letra grande, navegação pelo teclado.
// Liga com a tecla P, com o botão "Modo quadro" ou abrindo index.html#quadro.
(() => {
  const SECOES = [
    ['cenario', 'Cenário'], ['dados', 'Os dados'], ['testes', 'Os testes'], ['erro-tipo-i', 'Erro tipo I'],
    ['poder', 'Poder'], ['resultados-reais', 'Dados reais'], ['conclusao', 'Conclusão'],
  ];
  // As 15 perguntas da apresentação oral e a seção que responde a cada uma.
  const PERGUNTAS = [
    ['Cenário, H0 e H1 em palavras simples', 'cenario'],
    ['O teste é unicaudal ou bicaudal? Por quê?', 'cenario'],
    ['Como os dados reais foram coletados e qual a forma deles', 'dados'],
    ['Como os dados reais definiram os parâmetros da simulação', 'dados'],
    ['O que cada teste compara de fato', 'testes'],
    ['G2: a distribuição sob H0 e onde fica a região de rejeição', 'testes'],
    ['O que o p-valor do exemplo significa, e o que não significa', 'testes'],
    ['Erro tipo I e tipo II no cenário: qual é mais grave', 'erro-tipo-i'],
    ['G3: algum teste se afastou de 5%? Liberal ou conservador?', 'erro-tipo-i'],
    ['G4: qual teste tem mais poder, e se isso muda com o efeito', 'poder'],
    ['Que violação foi simulada e por que afeta mais um teste', 'erro-tipo-i'],
    ['O que mudaria no G3 e no G4 com α = 0,01', 'poder'],
    ['A simulação confirmou o que o grupo esperava?', 'conclusao'],
    ['Nos dados reais, os testes concordam? O efeito importa na prática?', 'resultados-reais'],
    ['Recomendação, quando ela mudaria e a principal limitação', 'conclusao'],
  ];
  const raiz = document.documentElement;
  const movimento = matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth';
  const el = (tag, props = {}, filhos = []) => {
    const e = Object.assign(document.createElement(tag), props);
    e.append(...filhos);
    return e;
  };

  const botao = el('button', { type: 'button', className: 'quadro-botao', textContent: 'Modo quadro (P)' });
  const itens = SECOES.map(([id, nome], i) => el('a', { href: `#${id}`, textContent: `${i + 1} ${nome}` }));
  const btnPerguntas = el('button', { type: 'button', textContent: 'Perguntas (?)' });
  const btnSair = el('button', { type: 'button', textContent: 'Sair (Esc)' });
  const nav = el('nav', { className: 'quadro-nav', hidden: true }, [
    el('div', { className: 'quadro-nav-secoes' }, itens),
    el('div', { className: 'quadro-nav-acoes' }, [btnPerguntas, btnSair]),
  ]);
  nav.setAttribute('aria-label', 'Telas do modo quadro');

  const lista = el('ol', {}, PERGUNTAS.map(([texto, id]) => {
    const n = SECOES.findIndex(([s]) => s === id);
    const b = el('button', { type: 'button' }, [
      el('span', { className: 'quadro-p-texto', textContent: texto }),
      el('span', { className: 'quadro-p-secao', textContent: `${n + 1} ${SECOES[n][1]}` }),
    ]);
    b.addEventListener('click', () => { dialogo.close(); ir(n); });
    return el('li', {}, [b]);
  }));
  const fechar = el('button', { type: 'button', className: 'quadro-fechar', textContent: 'Fechar' });
  const dialogo = el('dialog', { className: 'quadro-perguntas' }, [
    el('h2', { textContent: 'As 15 perguntas e onde responder' }), lista, fechar,
  ]);
  fechar.addEventListener('click', () => dialogo.close());
  document.body.append(botao, nav, dialogo);

  const ligado = () => raiz.classList.contains('quadro');
  const atual = () => {
    let i = 0;
    SECOES.forEach(([id], k) => {
      if (document.getElementById(id).getBoundingClientRect().top <= innerHeight * 0.35) i = k;
    });
    return i;
  };
  // Durante a rolagem suave, a tela de referência é o destino, não a posição do meio do caminho:
  // apertar → duas vezes seguidas avança duas telas, sem pular nem travar.
  let destino = null;
  let fimRolagem;
  const base = () => destino ?? atual();
  const ir = (i) => {
    destino = Math.max(0, Math.min(SECOES.length - 1, i));
    const topo = document.getElementById(SECOES[destino][0]).getBoundingClientRect().top + scrollY;
    scrollTo({ top: topo, behavior: movimento });
  };
  const marcar = () => {
    const i = atual();
    itens.forEach((a, k) => (k === i ? a.setAttribute('aria-current', 'step') : a.removeAttribute('aria-current')));
  };
  const alternar = (ligar) => {
    const secao = atual();
    raiz.classList.toggle('quadro', ligar);
    nav.hidden = !ligar;
    botao.hidden = ligar;
    history.replaceState(null, '', ligar ? '#quadro' : location.pathname + location.search);
    ir(secao);
    marcar();
  };

  botao.addEventListener('click', () => alternar(true));
  btnSair.addEventListener('click', () => alternar(false));
  btnPerguntas.addEventListener('click', () => dialogo.showModal());
  itens.forEach((a, k) => a.addEventListener('click', (e) => { e.preventDefault(); ir(k); }));
  addEventListener('scroll', () => {
    clearTimeout(fimRolagem);
    fimRolagem = setTimeout(() => { destino = null; marcar(); }, 150);
  }, { passive: true });

  addEventListener('keydown', (e) => {
    if (e.ctrlKey || e.metaKey || e.altKey || dialogo.open) return;
    const tecla = e.key;
    if (tecla === 'p' || tecla === 'P') { e.preventDefault(); alternar(!ligado()); return; }
    if (!ligado()) return;
    const acoes = {
      ArrowRight: () => ir(base() + 1), PageDown: () => ir(base() + 1), ' ': () => ir(base() + 1),
      ArrowLeft: () => ir(base() - 1), PageUp: () => ir(base() - 1),
      Home: () => ir(0), End: () => ir(SECOES.length - 1),
      '?': () => dialogo.showModal(), Escape: () => alternar(false),
    };
    if (/^[1-7]$/.test(tecla)) acoes[tecla] = () => ir(Number(tecla) - 1);
    if (acoes[tecla] && !(tecla === ' ' && e.target.closest('button, a, summary'))) {
      e.preventDefault();
      acoes[tecla]();
    }
  });

  if (location.hash === '#quadro') alternar(true);
})();
