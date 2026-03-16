"""
dou_fetcher.py — Coleta de publicações do Diário Oficial da União

ESTRATÉGIA TRIPLA (seções regulares):
  1ª: /leiturajornal?org=X — busca por órgão, como o site oficial faz.
      Garante completude: a API sem filtro de órgão trunca o jsonArray.
  2ª: /leiturajornal (JSON completo da seção) → filtra localmente (fallback)
  3ª: /consulta/-/buscar/dou (busca paginada por órgão) → fallback final

CAMADA 1 — RETRY AGRESSIVO:
  Cada seção regular é tentada até SECTION_RETRIES vezes.
  Na última tentativa, força o fallback direto (busca paginada).

CAMADA 2 — VALIDAÇÃO DE CONTAGEM:
  O jsonArray retorna TODAS as publicações (não só dos nossos 6 órgãos).
  Se o total bruto de uma seção regular é 0 num dia útil, é bug da API,
  não ausência real. O retry é forçado.
"""

import json
import logging
import re
import time
from datetime import date, timedelta
from typing import Optional

import requests
from bs4 import BeautifulSoup

import config

logger = logging.getLogger(__name__)

SECTION_RETRIES = 5
SECTION_RETRY_DELAY = 3.0


# ─────────────────────────────────────────────────────────────
#  UTILITÁRIOS DE DATA
# ─────────────────────────────────────────────────────────────

def eh_dia_util(d: date) -> bool:
    return d.weekday() < 5 and d not in config.FERIADOS

def dia_util_anterior(d: date) -> date:
    ant = d - timedelta(days=1)
    while not eh_dia_util(ant):
        ant -= timedelta(days=1)
    return ant

def hoje_eh_dia_de_envio() -> bool:
    return eh_dia_util(date.today())


# ─────────────────────────────────────────────────────────────
#  FETCHER
# ─────────────────────────────────────────────────────────────

class DOUFetcher:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "pt-BR,pt;q=0.9,en-US;q=0.8",
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    # ─── MÉTODO PRINCIPAL ─────────────────────────────────

    def buscar_publicacoes_do_dia(
        self, data_regular: date, data_extra: Optional[date] = None
    ) -> dict:
        resultado = {
            "data_regular": data_regular.strftime("%d/%m/%Y"),
            "data_extra": data_extra.strftime("%d/%m/%Y") if data_extra else None,
            "secoes": {},
            "total_publicacoes": 0,
            "completo": True,
            "secoes_faltantes": [],
        }

        # Edições regulares (Seção 1, 2, 3 — data de HOJE)
        for secao_id, nome_secao in config.SECOES_REGULARES.items():
            logger.info(f"▶ {nome_secao} — {data_regular.strftime('%d/%m/%Y')}")
            orgaos = self._buscar_secao_com_retry(
                secao_id, data_regular, nome_secao, eh_regular=True
            )
            if orgaos:
                resultado["secoes"][nome_secao] = orgaos
                n = sum(len(v) for v in orgaos.values())
                resultado["total_publicacoes"] += n
                logger.info(f"  ✓ {n} publicação(ões) relevante(s)")
            else:
                logger.warning(f"  ⚠ {nome_secao} retornou VAZIO após todas as tentativas")
                resultado["completo"] = False
                resultado["secoes_faltantes"].append(nome_secao)

        # Edições extras (data do DIA ÚTIL ANTERIOR)
        if data_extra:
            for base_id, base_nome in config.SECOES_REGULARES.items():
                for sufixo in config.EXTRA_SUFIXOS:
                    secao_extra_id = f"{base_id}{sufixo}"
                    nome_extra = config.nome_extra(base_nome, sufixo)
                    logger.info(f"▶ {nome_extra} — {data_extra.strftime('%d/%m/%Y')} (verificando...)")
                    orgaos = self._buscar_secao_com_retry(
                        secao_extra_id, data_extra, nome_extra, eh_regular=False
                    )
                    if orgaos:
                        resultado["secoes"][nome_extra] = orgaos
                        n = sum(len(v) for v in orgaos.values())
                        resultado["total_publicacoes"] += n
                        logger.info(f"  ✓ {n} publicação(ões) em edição extra!")

        self._log_completude(resultado)
        return resultado

    # ─── RETRY AGRESSIVO POR SEÇÃO ────────────────────────

    def _buscar_secao_com_retry(self, secao_id, data, nome_secao, eh_regular):
        max_t = SECTION_RETRIES if eh_regular else 1
        orgaos = {}

        for t in range(1, max_t + 1):
            if eh_regular and t == max_t:
                logger.info(f"  → Tentativa final: forçando fallback (busca paginada)...")
                orgaos = self._fetch_via_busca(secao_id, data)
            else:
                orgaos = self._buscar_secao(secao_id, data, eh_regular)

            if orgaos:
                if t > 1:
                    logger.info(f"  ✓ {nome_secao}: sucesso na tentativa {t}")
                return orgaos

            if eh_regular and t < max_t:
                delay = SECTION_RETRY_DELAY * t
                logger.warning(f"  ⚠ {nome_secao} vazio (tentativa {t}/{max_t}) — aguardando {delay:.0f}s...")
                time.sleep(delay)

        return orgaos

    def _log_completude(self, resultado):
        secoes_presentes = set(resultado.get("secoes", {}).keys())
        for nome_secao in config.SECOES_REGULARES.values():
            if nome_secao not in secoes_presentes:
                logger.warning(f"⚠ COMPLETUDE: {nome_secao} ausente no resultado final!")

        total = resultado.get("total_publicacoes", 0)
        if total == 0:
            logger.warning("⚠ COMPLETUDE: ZERO publicações. Verifique a API.")
        elif total < 10:
            logger.warning(f"⚠ COMPLETUDE: Apenas {total} publicações — volume suspeito.")

    # ─── BUSCA POR SEÇÃO ──────────────────────────────────

    def _buscar_secao(self, secao_id, data, eh_regular=False):
        # ── ESTRATÉGIA 1: busca por órgão (como o site oficial faz) ──
        # Só para seções regulares — extras são raras e não precisam disso.
        if eh_regular:
            orgaos = self._fetch_por_orgao(secao_id, data)
            if orgaos:
                total = sum(len(v) for v in orgaos.values())
                logger.info(f"    Estratégia por órgão: {total} pub(s) de {len(orgaos)} órgão(s)")
                return orgaos
            logger.info(f"    Busca por órgão insuficiente — tentando busca geral...")

        # ── ESTRATÉGIA 2: busca geral + filtro local (fallback) ──
        items = self._fetch_via_leiturajornal(secao_id, data)

        if items is None:
            logger.info(f"    Fallback: usando endpoint de busca...")
            return self._fetch_via_busca(secao_id, data)

        # ── CAMADA 2: VALIDAÇÃO DE CONTAGEM PRÉ-FILTRO ──
        if not items and eh_regular:
            logger.warning(f"    Camada 2: jsonArray vazio em seção regular — provável bug da API")
            return {}

        if not items:
            return {}

        total_bruto = len(items)
        logger.info(f"    Total bruto (todos os órgãos): {total_bruto} publicações")

        return self._filtrar_por_orgaos(items)

    # ─── ESTRATÉGIA 1A: /leiturajornal por órgão ─────────

    def _fetch_por_orgao(self, secao_id, data):
        """
        Busca publicações órgão a órgão via /leiturajornal?org=X.
        Replica a mesma estratégia que o site oficial do DOU usa.
        Retorna dict {orgao: [pubs]} ou {} se falhar.
        """
        data_str = data.strftime("%d-%m-%Y")
        orgaos_resultado = {}
        urls_vistas = set()
        falhas_consecutivas = 0

        for orgao in config.ORGAOS_FILTRO:
            items = self._fetch_leiturajornal_org(secao_id, data_str, orgao)

            # Se formato dou1 não funcionou, tenta do1
            if items is None:
                secao_alt = secao_id.replace("dou", "do")
                items = self._fetch_leiturajornal_org(secao_alt, data_str, orgao)

            if items is None:
                falhas_consecutivas += 1
                # 3 falhas seguidas = API com problema, aborta estratégia
                if falhas_consecutivas >= 3:
                    logger.warning(f"    3 falhas consecutivas na busca por órgão — abortando")
                    return {}
                continue

            falhas_consecutivas = 0

            pubs = []
            for item in items:
                pub = self._normalizar_item(item)
                if pub and pub["url"] not in urls_vistas:
                    urls_vistas.add(pub["url"])
                    pubs.append(pub)

            if pubs:
                orgaos_resultado[orgao] = pubs
                logger.info(f"    {orgao}: {len(pubs)} publicação(ões)")

            time.sleep(0.3)

        return orgaos_resultado

    def _fetch_leiturajornal_org(self, secao_id, data_str, orgao):
        """
        GET /leiturajornal?secao=X&data=Y&org=Z
        Retorna lista de itens ou None em caso de erro.
        """
        try:
            params = {
                "secao": secao_id,
                "data": data_str,
                "org": orgao,
            }
            resp = self.session.get(
                config.DOU_LEITURA_URL,
                params=params,
                timeout=config.REQUEST_TIMEOUT,
            )
            resp.raise_for_status()
            items = self._parse_leiturajornal(resp.text)
            # items pode ser [] (vazio legítimo) ou None (parse falhou)
            return items
        except requests.RequestException as e:
            logger.debug(f"    GET /leiturajornal?org={orgao} falhou: {e}")
            return None

    # ─── ESTRATÉGIA 1B: /leiturajornal geral ─────────────

    def _fetch_via_leiturajornal(self, secao_id, data):
        data_str = data.strftime("%d-%m-%Y")
        url = f"{config.DOU_LEITURA_URL}?secao={secao_id}&data={data_str}"

        for tentativa in range(1, config.MAX_RETRIES + 1):
            try:
                logger.debug(f"    GET {url} (tentativa {tentativa})")
                resp = self.session.get(url, timeout=config.REQUEST_TIMEOUT)
                resp.raise_for_status()

                items = self._parse_leiturajornal(resp.text)
                if items is not None:
                    return items

                if "nenhum resultado" in resp.text.lower() or len(resp.text) < 2000:
                    return []

                logger.warning(f"    Não encontrou jsonArray na resposta")
                if tentativa < config.MAX_RETRIES:
                    time.sleep(config.REQUEST_DELAY * tentativa)
                    continue
                return None

            except requests.RequestException as e:
                logger.warning(f"    Tentativa {tentativa} falhou: {e}")
                if tentativa < config.MAX_RETRIES:
                    time.sleep(config.REQUEST_DELAY * tentativa)

        return None

    def _parse_leiturajornal(self, html):
        soup = BeautifulSoup(html, "html.parser")

        script = soup.find("script", {"id": "params"})
        if script and script.string:
            try:
                data = json.loads(script.string)
                json_array = data.get("jsonArray", [])
                if isinstance(json_array, list):
                    items = json_array
                elif isinstance(json_array, str):
                    items = json.loads(json_array)
                else:
                    items = []
                if isinstance(items, list):
                    logger.debug(f"    jsonArray: {len(items)} itens totais")
                    return items
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.warning(f"    Erro ao parsear script#params: {e}")

        for tag in soup.find_all("script", {"type": "application/json"}):
            if not tag.string:
                continue
            try:
                data = json.loads(tag.string)
                if isinstance(data, dict) and "jsonArray" in data:
                    json_array = data["jsonArray"]
                    if isinstance(json_array, list):
                        items = json_array
                    elif isinstance(json_array, str):
                        items = json.loads(json_array)
                    else:
                        continue
                    if isinstance(items, list):
                        return items
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

        match = re.search(r'"jsonArray"\s*:\s*"(\[.*?\])"\s*[,}]', html, re.DOTALL)
        if match:
            try:
                raw = match.group(1).replace('\\"', '"').replace("\\/", "/").replace("\\n", " ")
                items = json.loads(raw)
                if isinstance(items, list):
                    return items
            except json.JSONDecodeError:
                pass

        return None

    # ─── ESTRATÉGIA 2: /consulta/-/buscar/dou ──────────────

    def _fetch_via_busca(self, secao_id, data):
        busca_secao = secao_id.replace("dou", "do")
        data_str = data.strftime("%d-%m-%Y")
        orgaos_resultado = {}

        for orgao in config.ORGAOS_FILTRO:
            pubs = self._busca_paginada(busca_secao, data_str, orgao)
            if pubs:
                orgaos_resultado[orgao] = pubs

        return orgaos_resultado

    def _busca_paginada(self, secao, data_str, orgao):
        todas = []
        start = 0

        while True:
            try:
                params = {
                    "q": "*",
                    "s": secao,
                    "exactDate": data_str,
                    "orgPrin": orgao,
                    "delta": config.MAX_RESULTS_PER_PAGE,
                    "start": start,
                }
                resp = self.session.get(config.DOU_BUSCA_URL, params=params, timeout=config.REQUEST_TIMEOUT)
                resp.raise_for_status()

                items, total = self._parse_busca_html(resp.text)
                if not items:
                    break

                for item in items:
                    pub = self._normalizar_item(item)
                    if pub:
                        todas.append(pub)

                start += config.MAX_RESULTS_PER_PAGE
                if start >= total or len(items) < config.MAX_RESULTS_PER_PAGE:
                    break

                time.sleep(config.REQUEST_DELAY)

            except Exception as e:
                logger.warning(f"    Erro busca {orgao}: {e}")
                break

        return todas

    def _parse_busca_html(self, html):
        soup = BeautifulSoup(html, "html.parser")

        for tag in soup.find_all("script", {"type": "application/json"}):
            if not tag.string:
                continue
            try:
                data = json.loads(tag.string)
                if isinstance(data, dict) and "jsonArray" in data:
                    json_array = data["jsonArray"]
                    if isinstance(json_array, list):
                        items = json_array
                    elif isinstance(json_array, str):
                        items = json.loads(json_array)
                    else:
                        continue
                    total = data.get("total", len(items))
                    return items, total
            except (json.JSONDecodeError, TypeError, ValueError):
                continue

        return [], 0

    # ─── FILTRO E NORMALIZAÇÃO ────────────────────────────

    def _filtrar_por_orgaos(self, items):
        orgaos_filtro_lower = {o.lower(): o for o in config.ORGAOS_FILTRO}
        resultado = {}

        for item in items:
            art_category = (item.get("artCategory") or "").strip()
            orgao_match = None
            cat_lower = art_category.lower()

            if cat_lower in orgaos_filtro_lower:
                orgao_match = orgaos_filtro_lower[cat_lower]
            else:
                hierarchy = (item.get("hierarchyStr") or "").strip()
                for filtro_lower, filtro_original in orgaos_filtro_lower.items():
                    if filtro_lower in hierarchy.lower():
                        orgao_match = filtro_original
                        break

            if not orgao_match:
                continue

            pub = self._normalizar_item(item)
            if pub:
                resultado.setdefault(orgao_match, []).append(pub)

        return resultado

    def _normalizar_item(self, item):
        try:
            url_title = (item.get("urlTitle") or "").strip()
            if not url_title:
                return None

            url = f"{config.DOU_ARTICLE_BASE}{url_title}"

            hierarchy_list = item.get("hierarchyList") or []
            sub_orgao = ""
            if isinstance(hierarchy_list, list) and len(hierarchy_list) > 1:
                sub_orgao = hierarchy_list[-1].strip()
            elif isinstance(hierarchy_list, str):
                parts = hierarchy_list.split(" > ")
                if len(parts) > 1:
                    sub_orgao = parts[-1].strip()

            ementa = (item.get("content") or item.get("abstract") or "").strip()

            return {
                "titulo": (item.get("title") or "Sem título").strip(),
                "ementa": ementa,
                "tipo_ato": (item.get("artType") or item.get("pubName") or "").strip(),
                "orgao": (item.get("artCategory") or "").strip(),
                "sub_orgao": sub_orgao,
                "url": url,
                "pagina": str(item.get("numberPage") or ""),
                "edicao": str(item.get("editionNumber") or ""),
                "data_pub": (item.get("pubDate") or "").strip(),
            }
        except Exception as e:
            logger.warning(f"    Erro normalização: {e}")
            return None
