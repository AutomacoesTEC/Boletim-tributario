"""
Configurações do Boletim DOU
"""
import os
from datetime import date

# ═══════════════════════════════════════════════════════════
# E-MAIL (Gmail SMTP)
# ═══════════════════════════════════════════════════════════
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SMTP_USER = os.environ.get("GMAIL_USER", "")
SMTP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

SENDER_NAME = "Boletim DOU Tributário"
SENDER_EMAIL = SMTP_USER
UNSUBSCRIBE_EMAIL = SMTP_USER

# ═══════════════════════════════════════════════════════════
# GITHUB PAGES (site do boletim)
# Ajuste a URL abaixo para o seu repositório
# Formato: https://<usuario>.github.io/<repositorio>/
# ═══════════════════════════════════════════════════════════
GITHUB_PAGES_URL = os.environ.get(
    "PAGES_URL",
    "https://naytributario.github.io/Boletim-tributario/"
)

# ═══════════════════════════════════════════════════════════
# SEÇÕES REGULARES (data = HOJE)
# Chave = param "secao" para /leiturajornal
# ═══════════════════════════════════════════════════════════
SECOES_REGULARES = {
    "dou1": "Seção 1",
    "dou2": "Seção 2",
    "dou3": "Seção 3",
}

# Sufixos de Edição Extra a verificar (data = DIA ÚTIL ANTERIOR)
# Ex: "dou1" + "e" => "dou1e", "dou1" + "a" => "dou1a"
EXTRA_SUFIXOS = ["e", "a", "b", "c", "d", "f", "g", "h", "i", "j"]


# Nomes legíveis para edições extras
def nome_extra(base_nome: str, sufixo: str) -> str:
    if sufixo == "e":
        return f"{base_nome} — Edição Extra"
    return f"{base_nome} — Ed. Extra {sufixo.upper()}"


# ═══════════════════════════════════════════════════════════
# ÓRGÃOS PRINCIPAIS A FILTRAR
# Nomes conforme aparecem no campo "artCategory" da API
# ═══════════════════════════════════════════════════════════
ORGAOS_FILTRO = [
    "Atos do Poder Judiciário",
    "Atos do Poder Legislativo",
    "Atos do Poder Executivo",
    "Presidência da República",
    "Ministério da Fazenda",
    "Entidades de Fiscalização do Exercício das Profissões Liberais",
]

# ═══════════════════════════════════════════════════════════
# FERIADOS NACIONAIS (atualizar anualmente)
# ═══════════════════════════════════════════════════════════
FERIADOS = [
    # 2025
    date(2025, 1, 1),   # Confraternização Universal
    date(2025, 3, 3),   # Carnaval
    date(2025, 3, 4),   # Carnaval
    date(2025, 4, 18),  # Sexta-feira Santa
    date(2025, 4, 21),  # Tiradentes
    date(2025, 5, 1),   # Dia do Trabalho
    date(2025, 6, 19),  # Corpus Christi
    date(2025, 9, 7),   # Independência
    date(2025, 10, 12), # N. Sra. Aparecida
    date(2025, 11, 2),  # Finados
    date(2025, 11, 15), # Proclamação da República
    date(2025, 11, 20), # Consciência Negra
    date(2025, 12, 25), # Natal
    # 2026
    date(2026, 1, 1),   # Confraternização Universal
    date(2026, 2, 16),  # Carnaval
    date(2026, 2, 17),  # Carnaval
    date(2026, 4, 3),   # Sexta-feira Santa
    date(2026, 4, 21),  # Tiradentes
    date(2026, 5, 1),   # Dia do Trabalho
    date(2026, 6, 4),   # Corpus Christi
    date(2026, 9, 7),   # Independência
    date(2026, 10, 12), # N. Sra. Aparecida
    date(2026, 11, 2),  # Finados
    date(2026, 11, 15), # Proclamação da República
    date(2026, 11, 20), # Consciência Negra
    date(2026, 12, 25), # Natal
]

# ═══════════════════════════════════════════════════════════
# ENDPOINTS IMPRENSA NACIONAL
# ═══════════════════════════════════════════════════════════
# Primário: retorna JSON completo de uma seção/data
DOU_LEITURA_URL = "https://www.in.gov.br/leiturajornal"

# Fallback: busca paginada por órgão
DOU_BUSCA_URL = "https://www.in.gov.br/consulta/-/buscar/dou"

# Base para links individuais (concatenar com urlTitle)
DOU_ARTICLE_BASE = "https://www.in.gov.br/en/web/dou/-/"

# ═══════════════════════════════════════════════════════════
# REDE
# ═══════════════════════════════════════════════════════════
REQUEST_TIMEOUT = 30       # segundos
REQUEST_DELAY = 1.5        # entre requisições (não sobrecarregar)
MAX_RETRIES = 3            # tentativas por requisição
MAX_RESULTS_PER_PAGE = 200 # delta na busca paginada

# ═══════════════════════════════════════════════════════════
# CAMINHOS
# ═══════════════════════════════════════════════════════════
SUBSCRIBERS_FILE = os.path.join(os.path.dirname(__file__), "subscribers.json")
