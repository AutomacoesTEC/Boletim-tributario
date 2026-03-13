"""
page_builder.py — Gerador da página web interativa do Boletim DOU

Gera um HTML estático com:
  - Seções colapsáveis (clique para expandir/recolher)
  - Busca em tempo real (a partir de 3 caracteres)
  - Destaque dos termos buscados
  - Design responsivo e profissional
  - Contadores dinâmicos por seção
"""

import html as html_mod
import json
import logging
from datetime import datetime
from typing import Optional

import config

logger = logging.getLogger(__name__)

DIAS = [
    "Segunda-feira", "Terça-feira", "Quarta-feira",
    "Quinta-feira", "Sexta-feira", "Sábado", "Domingo",
]
MESES = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
]


def _esc(text: str) -> str:
    return html_mod.escape(text) if text else ""


class PageBuilder:
    """Gera a página HTML interativa do boletim."""

    def build(self, dados: dict) -> Optional[str]:
        if not dados.get("secoes") or dados.get("total_publicacoes", 0) == 0:
            return None

        data_regular = dados["data_regular"]
        data_extra = dados.get("data_extra")
        total = dados["total_publicacoes"]

        try:
            dt = datetime.strptime(data_regular, "%d/%m/%Y")
            data_ext = f"{DIAS[dt.weekday()]}, {dt.day} de {MESES[dt.month - 1]} de {dt.year}"
        except Exception:
            data_ext = data_regular

        secoes_html = self._build_secoes(dados["secoes"])
        resumo_html = self._build_resumo(dados["secoes"])
        extra_banner = ""
        if data_extra and any("Extra" in k for k in dados["secoes"]):
            extra_banner = f"""
            <div class="extra-banner">
                <span>⚡</span> Inclui Edições Extras de {_esc(data_extra)}
            </div>"""

        return self._template(
            data_ext=data_ext,
            data_regular=data_regular,
            total=total,
            resumo=resumo_html,
            extra_banner=extra_banner,
            secoes=secoes_html,
        )

    def _build_resumo(self, secoes: dict) -> str:
        items = []
        for nome, orgaos in secoes.items():
            cnt = sum(len(p) for p in orgaos.values())
            is_extra = "Extra" in nome
            dot_class = "dot-extra" if is_extra else "dot-regular"
            items.append(
                f'<div class="resumo-item">'
                f'<span class="resumo-dot {dot_class}"></span>'
                f'<span class="resumo-nome">{_esc(nome)}</span>'
                f'<span class="resumo-count">{cnt}</span>'
                f'</div>'
            )
        return "\n".join(items)

    def _build_secoes(self, secoes: dict) -> str:
        parts = []
        idx = 0
        for nome_secao, orgaos in secoes.items():
            parts.append(self._build_secao(nome_secao, orgaos, idx))
            idx += 1
        return "\n".join(parts)

    def _build_secao(self, nome: str, orgaos: dict, idx: int) -> str:
        is_extra = "Extra" in nome
        cls = "secao-extra" if is_extra else "secao-regular"
        total_secao = sum(len(p) for p in orgaos.values())

        orgaos_html = "\n".join(
            self._build_orgao(n, pubs) for n, pubs in orgaos.items()
        )

        return f"""
        <div class="secao {cls}" data-secao="{_esc(nome)}">
            <div class="secao-header" onclick="toggleSecao(this)" role="button" tabindex="0">
                <div class="secao-titulo-wrap">
                    <span class="secao-chevron">▸</span>
                    <h2 class="secao-titulo">{_esc(nome)}</h2>
                    <span class="secao-badge">{total_secao}</span>
                    <span class="secao-hint">clique para expandir</span>
                </div>
            </div>
            <div class="secao-conteudo collapsed">
                {orgaos_html}
            </div>
        </div>"""

    def _build_orgao(self, nome: str, pubs: list) -> str:
        pubs_html = "\n".join(self._build_pub(p) for p in pubs)
        return f"""
        <div class="orgao" data-orgao="{_esc(nome)}">
            <div class="orgao-header" onclick="toggleOrgao(this)" role="button" tabindex="0">
                <span class="orgao-chevron">▸</span>
                <span class="orgao-nome">{_esc(nome)}</span>
                <span class="orgao-count">{len(pubs)}</span>
            </div>
            <div class="orgao-pubs orgao-collapsed">
                {pubs_html}
            </div>
        </div>"""

    def _build_pub(self, pub: dict) -> str:
        titulo = _esc(pub.get("titulo", "Sem título"))
        ementa = _esc(pub.get("ementa", "")[:500])
        tipo = _esc(pub.get("tipo_ato", ""))
        sub = _esc(pub.get("sub_orgao", ""))
        url = _esc(pub.get("url", ""))

        tipo_html = f'<span class="pub-tipo">{tipo}</span>' if tipo else ""
        sub_html = f'<span class="pub-sub">↳ {sub}</span>' if sub else ""
        ementa_html = f'<p class="pub-ementa">{ementa}</p>' if ementa else ""
        link_html = f'<a href="{url}" target="_blank" rel="noopener" class="pub-link">Ler íntegra →</a>' if url else ""

        return f"""
        <div class="pub" data-search="{titulo.lower()} {ementa.lower()} {tipo.lower()} {sub.lower()}">
            {tipo_html}
            {sub_html}
            <a href="{url}" target="_blank" rel="noopener" class="pub-titulo">{titulo}</a>
            {ementa_html}
            {link_html}
        </div>"""

    def _template(self, **kw) -> str:
        return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>Boletim DOU — {_esc(kw['data_regular'])}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Source+Serif+4:wght@400;600;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --navy: #0F172A;
  --blue: #1E3A5F;
  --blue-light: #F0F7FF;
  --red: #B91C1C;
  --red-light: #FEF2F2;
  --gray-50: #F8FAFC;
  --gray-100: #F1F5F9;
  --gray-200: #E2E8F0;
  --gray-400: #94A3B8;
  --gray-500: #64748B;
  --gray-700: #334155;
  --gray-900: #0F172A;
  --font-serif: 'Source Serif 4', Georgia, serif;
  --font-sans: 'Inter', -apple-system, system-ui, sans-serif;
  --max-w: 860px;
}}

* {{ margin:0; padding:0; box-sizing:border-box; }}

body {{
  font-family: var(--font-sans);
  background: var(--gray-100);
  color: var(--gray-900);
  line-height: 1.6;
}}

/* ═══ HEADER ═══ */
.header {{
  background: var(--navy);
  padding: 28px 24px 22px;
}}
.header-inner {{
  max-width: var(--max-w);
  margin: 0 auto;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}}
.header h1 {{
  font-family: var(--font-serif);
  font-size: 26px;
  font-weight: 700;
  color: #fff;
  letter-spacing: -0.3px;
}}
.header .subtitle {{
  font-size: 11px;
  color: var(--gray-400);
  letter-spacing: 1.5px;
  text-transform: uppercase;
  margin-top: 4px;
}}
.header .total-badge {{
  background: var(--blue);
  color: #E2E8F0;
  font-size: 13px;
  font-weight: 600;
  padding: 5px 14px;
  border-radius: 4px;
  white-space: nowrap;
}}

/* ═══ DATA BAR ═══ */
.data-bar {{
  background: #fff;
  border-bottom: 1px solid var(--gray-200);
  padding: 14px 24px;
}}
.data-bar-inner {{
  max-width: var(--max-w);
  margin: 0 auto;
}}
.data-bar h2 {{
  font-family: var(--font-serif);
  font-size: 16px;
  font-weight: 600;
  color: var(--gray-700);
}}
.data-bar .hora {{
  font-size: 11px;
  color: var(--gray-400);
  margin-top: 2px;
}}

/* ═══ CONTAINER ═══ */
.container {{
  max-width: var(--max-w);
  margin: 0 auto;
  padding: 20px 24px 60px;
}}

/* ═══ BUSCA ═══ */
.search-wrap {{
  position: relative;
  margin-bottom: 20px;
}}
.search-wrap input {{
  width: 100%;
  padding: 12px 16px 12px 42px;
  border: 2px solid var(--gray-200);
  border-radius: 8px;
  font-size: 14px;
  font-family: var(--font-sans);
  background: #fff;
  transition: border-color 0.2s;
  outline: none;
}}
.search-wrap input:focus {{
  border-color: var(--blue);
}}
.search-wrap input::placeholder {{
  color: var(--gray-400);
}}
.search-wrap .search-icon {{
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--gray-400);
  font-size: 16px;
  pointer-events: none;
}}
.search-info {{
  font-size: 12px;
  color: var(--gray-500);
  margin: -12px 0 16px;
  display: none;
}}
.search-info.visible {{ display: block; }}

/* ═══ RESUMO ═══ */
.resumo {{
  background: #fff;
  border-radius: 8px;
  padding: 16px 20px;
  margin-bottom: 16px;
  border: 1px solid var(--gray-200);
}}
.resumo-label {{
  font-size: 10px;
  font-weight: 700;
  color: var(--gray-400);
  text-transform: uppercase;
  letter-spacing: 1.5px;
  margin-bottom: 10px;
}}
.resumo-item {{
  display: flex;
  align-items: center;
  padding: 3px 0;
}}
.resumo-dot {{
  width: 7px; height: 7px;
  border-radius: 50%;
  margin-right: 10px;
  flex-shrink: 0;
}}
.dot-regular {{ background: var(--blue); }}
.dot-extra {{ background: var(--red); }}
.resumo-nome {{
  font-size: 13px;
  color: var(--gray-700);
  flex: 1;
}}
.resumo-count {{
  font-size: 13px;
  font-weight: 700;
  color: var(--gray-900);
}}

/* ═══ EXTRA BANNER ═══ */
.extra-banner {{
  background: var(--red-light);
  border-left: 3px solid var(--red);
  padding: 10px 16px;
  margin-bottom: 20px;
  border-radius: 0 6px 6px 0;
  font-size: 12px;
  font-weight: 600;
  color: #991B1B;
}}

/* ═══ SEÇÕES ═══ */
.secao {{
  background: #fff;
  border-radius: 8px;
  margin-bottom: 12px;
  border: 1px solid var(--gray-200);
  overflow: hidden;
  transition: box-shadow 0.2s;
}}
.secao:hover {{
  box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}
.secao-header {{
  padding: 14px 20px;
  cursor: pointer;
  user-select: none;
  display: flex;
  align-items: center;
  transition: background 0.15s;
}}
.secao-header:hover {{
  background: var(--gray-50);
}}
.secao-regular .secao-header {{
  border-left: 4px solid var(--blue);
}}
.secao-extra .secao-header {{
  border-left: 4px solid var(--red);
}}
.secao-titulo-wrap {{
  display: flex;
  align-items: center;
  gap: 10px;
  width: 100%;
}}
.secao-chevron {{
  font-size: 14px;
  color: var(--gray-400);
  transition: transform 0.25s;
  flex-shrink: 0;
}}
.secao.open .secao-chevron {{
  transform: rotate(90deg);
}}
.secao-titulo {{
  font-family: var(--font-serif);
  font-size: 15px;
  font-weight: 700;
  color: var(--gray-900);
  flex: 1;
  letter-spacing: 0.3px;
}}
.secao-extra .secao-titulo {{ color: var(--red); }}
.secao-badge {{
  background: var(--gray-100);
  color: var(--gray-700);
  font-size: 12px;
  font-weight: 700;
  padding: 2px 10px;
  border-radius: 12px;
  flex-shrink: 0;
}}
.secao-hint {{
  font-size: 10px;
  color: var(--gray-400);
  font-style: italic;
  margin-left: 8px;
  transition: opacity 0.2s;
}}
.secao.open .secao-hint {{
  opacity: 0;
}}
.secao-conteudo {{
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.35s ease;
}}
.secao-conteudo.collapsed {{
  max-height: 0;
}}

/* ═══ ÓRGÃO (colapsável) ═══ */
.orgao {{
  padding: 0 20px;
}}
.orgao-header {{
  display: flex;
  align-items: center;
  padding: 10px 0 6px;
  border-bottom: 1px solid var(--gray-200);
  cursor: pointer;
  user-select: none;
  transition: background 0.15s;
  border-radius: 4px;
  padding: 8px 6px;
  margin: 0 -6px;
}}
.orgao-header:hover {{
  background: var(--gray-50);
}}
.orgao-chevron {{
  font-size: 11px;
  color: var(--gray-400);
  transition: transform 0.25s;
  flex-shrink: 0;
  margin-right: 8px;
}}
.orgao.open .orgao-chevron {{
  transform: rotate(90deg);
}}
.orgao-nome {{
  font-family: var(--font-serif);
  font-size: 12px;
  color: var(--gray-500);
  font-style: italic;
  flex: 1;
}}
.orgao-count {{
  font-size: 11px;
  color: var(--gray-400);
  background: var(--gray-100);
  padding: 1px 8px;
  border-radius: 10px;
  font-weight: 600;
}}
.orgao-pubs {{
  max-height: 0;
  overflow: hidden;
  transition: max-height 0.3s ease;
}}
.orgao-pubs.orgao-collapsed {{
  max-height: 0;
}}

/* ═══ PUBLICAÇÃO ═══ */
.pub {{
  padding: 12px 0;
  border-bottom: 1px solid var(--gray-100);
}}
.pub:last-child {{ border-bottom: none; }}
.pub.hidden {{ display: none; }}
.pub-tipo {{
  display: inline-block;
  background: var(--gray-100);
  color: var(--gray-700);
  font-size: 10px;
  font-weight: 600;
  padding: 2px 7px;
  border-radius: 3px;
  text-transform: uppercase;
  letter-spacing: 0.4px;
  margin-bottom: 4px;
}}
.pub-sub {{
  display: block;
  font-size: 11px;
  color: var(--gray-400);
  font-style: italic;
  margin-bottom: 2px;
}}
.pub-titulo {{
  display: block;
  font-family: var(--font-serif);
  font-size: 14px;
  font-weight: 700;
  color: var(--gray-900);
  text-decoration: none;
  line-height: 1.35;
  margin-bottom: 4px;
  transition: color 0.15s;
}}
.pub-titulo:hover {{ color: var(--blue); }}
.pub-ementa {{
  font-size: 12.5px;
  color: var(--gray-500);
  line-height: 1.55;
  margin-bottom: 6px;
}}
.pub-link {{
  font-size: 11px;
  color: #2563EB;
  text-decoration: none;
  font-weight: 500;
  letter-spacing: 0.2px;
}}
.pub-link:hover {{ text-decoration: underline; }}

/* ═══ HIGHLIGHT BUSCA ═══ */
mark {{
  background: #FEF08A;
  color: inherit;
  padding: 0 1px;
  border-radius: 2px;
}}

/* ═══ FOOTER ═══ */
.footer {{
  text-align: center;
  padding: 24px;
  font-size: 11px;
  color: var(--gray-400);
  line-height: 1.7;
}}
.footer a {{ color: var(--gray-500); }}

/* ═══ RESPONSIVO ═══ */
@media (max-width: 640px) {{
  .header-inner {{ flex-direction: column; gap: 10px; }}
  .container {{ padding: 12px 12px 40px; }}
  .secao-header {{ padding: 12px 14px; }}
  .orgao {{ padding: 0 14px; }}
}}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
  <div class="header-inner">
    <div>
      <h1>BOLETIM DOU</h1>
      <div class="subtitle">Diário Oficial da União — Seções 1, 2 e 3</div>
    </div>
    <span class="total-badge">{kw['total']} atos</span>
  </div>
</div>

<!-- DATA -->
<div class="data-bar">
  <div class="data-bar-inner">
    <h2>{_esc(kw['data_ext'])}</h2>
    <div class="hora">Gerado às {datetime.now().strftime("%H:%M")} (Brasília)</div>
  </div>
</div>

<!-- CONTEÚDO -->
<div class="container">

  <!-- BUSCA -->
  <div class="search-wrap">
    <span class="search-icon">🔍</span>
    <input type="text" id="searchInput" placeholder="Buscar publicações (mínimo 3 caracteres)..." autocomplete="off">
  </div>
  <div class="search-info" id="searchInfo"></div>

  <!-- RESUMO -->
  <div class="resumo">
    <div class="resumo-label">Nesta edição</div>
    {kw['resumo']}
  </div>

  {kw['extra_banner']}

  <!-- SEÇÕES -->
  <div id="secoes">
    {kw['secoes']}
  </div>

</div>

<!-- FOOTER -->
<div class="footer">
  Fonte: <a href="https://www.in.gov.br/consulta" target="_blank">Imprensa Nacional</a><br>
  Órgãos: Poderes Executivo, Legislativo e Judiciário · Presidência da República · Min. da Fazenda · Entidades de Fiscalização
</div>

<script>
// ═══ COLAPSAR/EXPANDIR SEÇÕES ═══
function toggleSecao(header) {{
  const secao = header.closest('.secao');
  const conteudo = secao.querySelector('.secao-conteudo');
  const isOpen = secao.classList.contains('open');

  if (isOpen) {{
    conteudo.style.maxHeight = '0';
    secao.classList.remove('open');
  }} else {{
    conteudo.style.maxHeight = conteudo.scrollHeight + 'px';
    secao.classList.add('open');
  }}
}}

// ═══ COLAPSAR/EXPANDIR ÓRGÃOS ═══
function toggleOrgao(header) {{
  const orgao = header.closest('.orgao');
  const pubs = orgao.querySelector('.orgao-pubs');
  const isOpen = orgao.classList.contains('open');

  if (isOpen) {{
    pubs.style.maxHeight = '0';
    orgao.classList.remove('open');
  }} else {{
    pubs.style.maxHeight = pubs.scrollHeight + 'px';
    orgao.classList.add('open');
    // Recalcular max-height da seção pai (que agora tem mais conteúdo)
    const secaoConteudo = orgao.closest('.secao-conteudo');
    if (secaoConteudo) {{
      setTimeout(() => {{
        secaoConteudo.style.maxHeight = secaoConteudo.scrollHeight + 'px';
      }}, 50);
    }}
  }}
}}

// Seções começam FECHADAS — usuário clica para expandir

// ═══ BUSCA EM TEMPO REAL ═══
const searchInput = document.getElementById('searchInput');
const searchInfo = document.getElementById('searchInfo');

searchInput.addEventListener('input', function() {{
  const query = this.value.trim().toLowerCase();

  // Limpar highlights anteriores
  document.querySelectorAll('mark').forEach(m => {{
    m.replaceWith(m.textContent);
  }});

  if (query.length < 3) {{
    // Mostrar tudo, colapsar órgãos de volta
    document.querySelectorAll('.pub').forEach(p => p.classList.remove('hidden'));
    document.querySelectorAll('.orgao').forEach(o => {{
      o.style.display = '';
      o.classList.remove('open');
      const pubs = o.querySelector('.orgao-pubs');
      if (pubs) pubs.style.maxHeight = '0';
    }});
    document.querySelectorAll('.secao').forEach(s => s.style.display = '');
    searchInfo.classList.remove('visible');
    // Recalcular max-height das seções abertas
    document.querySelectorAll('.secao.open .secao-conteudo').forEach(c => {{
      c.style.maxHeight = c.scrollHeight + 'px';
    }});
    return;
  }}

  let totalVisible = 0;

  // Filtrar publicações
  document.querySelectorAll('.pub').forEach(pub => {{
    const text = pub.getAttribute('data-search') || '';
    if (text.includes(query)) {{
      pub.classList.remove('hidden');
      totalVisible++;
      // Highlight
      highlightText(pub, query);
    }} else {{
      pub.classList.add('hidden');
    }}
  }});

  // Esconder órgãos sem publicações visíveis, expandir os com resultados
  document.querySelectorAll('.orgao').forEach(orgao => {{
    const visiblePubs = orgao.querySelectorAll('.pub:not(.hidden)');
    if (visiblePubs.length === 0) {{
      orgao.style.display = 'none';
    }} else {{
      orgao.style.display = '';
      // Expandir órgão se tem resultados
      if (!orgao.classList.contains('open')) {{
        orgao.classList.add('open');
        const pubs = orgao.querySelector('.orgao-pubs');
        if (pubs) pubs.style.maxHeight = pubs.scrollHeight + 'px';
      }}
    }}
  }});

  // Esconder seções sem órgãos visíveis, expandir as com resultados
  document.querySelectorAll('.secao').forEach(secao => {{
    const visibleOrgaos = secao.querySelectorAll('.orgao:not([style*="display: none"])');
    secao.style.display = visibleOrgaos.length === 0 ? 'none' : '';
    // Expandir seções com resultados
    if (visibleOrgaos.length > 0 && !secao.classList.contains('open')) {{
      toggleSecao(secao.querySelector('.secao-header'));
    }}
    // Atualizar max-height
    const conteudo = secao.querySelector('.secao-conteudo');
    if (conteudo && secao.classList.contains('open')) {{
      setTimeout(() => {{ conteudo.style.maxHeight = conteudo.scrollHeight + 'px'; }}, 60);
    }}
  }});

  searchInfo.textContent = totalVisible + ' resultado(s) para "' + this.value.trim() + '"';
  searchInfo.classList.add('visible');
}});

function highlightText(container, query) {{
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) nodes.push(walker.currentNode);

  nodes.forEach(node => {{
    const text = node.textContent;
    const lower = text.toLowerCase();
    const idx = lower.indexOf(query);
    if (idx === -1) return;
    if (node.parentElement.tagName === 'MARK') return;
    if (node.parentElement.tagName === 'SCRIPT') return;
    if (node.parentElement.tagName === 'STYLE') return;

    const before = text.slice(0, idx);
    const match = text.slice(idx, idx + query.length);
    const after = text.slice(idx + query.length);

    const mark = document.createElement('mark');
    mark.textContent = match;

    const parent = node.parentNode;
    parent.insertBefore(document.createTextNode(before), node);
    parent.insertBefore(mark, node);
    node.textContent = after;
  }});
}}

// Atalho: Ctrl+K ou / para focar na busca
document.addEventListener('keydown', (e) => {{
  if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && document.activeElement.tagName !== 'INPUT')) {{
    e.preventDefault();
    searchInput.focus();
  }}
}});
</script>

</body>
</html>"""
