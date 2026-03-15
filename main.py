"""
main.py — Orquestrador do Boletim DOU

Fluxo:
  1. Busca publicações do DOU (regulares + extras)
  2. Gera página web interativa → docs/index.html (GitHub Pages)
  3. Envia e-mail personalizado (com nome) + link para a página

Camada 3: Se resultado incompleto, sai com exit code 2 →
          o workflow detecta e reexecuta após 30 minutos.

Camada 4: Se após todas as tentativas ainda faltam seções,
          envia alerta para ALERT_EMAIL antes de enviar o boletim.

Uso:
  python main.py                  # Normal (verifica dia útil)
  python main.py --force          # Força em qualquer dia
  python main.py --preview        # Salva preview sem enviar
  python main.py --test EMAIL     # Envia só para um e-mail
  python main.py --retry          # Reexecução (não sai com code 2)
"""

import argparse
import logging
import os
import sys
from datetime import date

import config
from dou_fetcher import DOUFetcher, dia_util_anterior, hoje_eh_dia_de_envio
from email_builder import EmailBuilder
from email_sender import EmailSender
from page_builder import PageBuilder
from subscriber_manager import SubscriberManager

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("boletim_dou.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("BoletimDOU")

# E-mail que recebe alertas de falha (Camada 4)
ALERT_EMAIL = "tectributos.federal11@gmail.com"


def executar(force=False, preview=False, test_email="", is_retry=False):
    logger.info("=" * 55)
    logger.info("BOLETIM DOU — Início%s", " (REEXECUÇÃO)" if is_retry else "")
    logger.info("=" * 55)

    if not force and not hoje_eh_dia_de_envio():
        logger.info("Hoje não é dia útil. Saindo.")
        return 0

    hoje = date.today()
    ontem_util = dia_util_anterior(hoje)

    logger.info(f"Edições regulares: {hoje.strftime('%d/%m/%Y')} (HOJE)")
    logger.info(f"Edições extras:    {ontem_util.strftime('%d/%m/%Y')} (dia útil anterior)")

    # ═══ 1. BUSCAR PUBLICAÇÕES ═══
    fetcher = DOUFetcher()
    dados = fetcher.buscar_publicacoes_do_dia(
        data_regular=hoje,
        data_extra=ontem_util,
    )

    total = dados.get("total_publicacoes", 0)
    completo = dados.get("completo", True)
    faltantes = dados.get("secoes_faltantes", [])

    logger.info(f"\nTotal encontrado: {total} publicação(ões)")
    if faltantes:
        logger.warning(f"Seções faltantes: {', '.join(faltantes)}")

    if total == 0:
        logger.info("Nenhuma publicação dos órgãos monitorados.")
        if not completo and not is_retry:
            # Camada 3: sair com code 2 para o workflow tentar de novo
            logger.info("Saindo com code 2 — workflow deve reexecutar.")
            return 2
        logger.info("Boletim NÃO será enviado.")
        return 0

    # ═══ 2. GERAR PÁGINA WEB ═══
    page_builder = PageBuilder()
    page_html = page_builder.build(dados)

    if page_html:
        docs_dir = os.path.join(os.path.dirname(__file__), "docs")
        os.makedirs(docs_dir, exist_ok=True)
        page_path = os.path.join(docs_dir, "index.html")
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(page_html)
        logger.info(f"✓ Página web salva: {page_path}")

    # ═══ 3. PREVIEW MODE ═══
    if preview:
        email_builder = EmailBuilder()
        email_html = email_builder.build(dados, nome_destinatario="Diva")
        if email_html:
            preview_path = os.path.join(os.path.dirname(__file__), "preview_email.html")
            with open(preview_path, "w", encoding="utf-8") as f:
                f.write(email_html)
            logger.info(f"✓ Preview e-mail: {preview_path}")
        logger.info("Modo preview — e-mail NÃO enviado.")
        return 0

    # ═══ 4. CAMADA 4: ALERTA SE INCOMPLETO ═══
    if not completo and faltantes:
        logger.warning("Camada 4: Enviando alerta de boletim incompleto...")
        _enviar_alerta_incompleto(dados)

        if not is_retry:
            # Camada 3: primeira execução incompleta → pedir reexecução
            logger.info("Saindo com code 2 — workflow deve reexecutar em 30 minutos.")
            # Mas ANTES, gera a página (já feito acima) para não perder o que tem
            return 2

    # ═══ 5. PREPARAR DESTINATÁRIOS ═══
    sm = SubscriberManager()
    email_builder = EmailBuilder()
    assunto = email_builder.build_subject(dados)
    sender = EmailSender()

    if test_email:
        destinatarios = [{"email": test_email, "nome": ""}]
        logger.info(f"Modo teste: {test_email}")
    else:
        todos = sm.listar_todos()
        destinatarios = [
            {"email": s["email"], "nome": s.get("nome", "")}
            for s in todos
            if s.get("status") == "ativo"
        ]
        logger.info(f"Destinatários ativos: {len(destinatarios)}")

    if not destinatarios:
        logger.warning("Nenhum destinatário. Use: python manage.py add EMAIL")
        return 0

    # ═══ 6. ENVIAR E-MAILS PERSONALIZADOS ═══
    if not sender.validar_credenciais():
        logger.error("Credenciais inválidas. Abortando envio.")
        return 1

    enviados = 0
    falhas = 0

    for dest in destinatarios:
        email = dest["email"]
        nome = dest["nome"]

        html_email = email_builder.build(dados, nome_destinatario=nome)
        if not html_email:
            continue

        ok = sender._enviar_um(
            dest=email,
            assunto=assunto,
            html_body=html_email,
            texto_fallback=(
                f"Boletim DOU — {dados['data_regular']} — {total} atos. "
                f"Acesse: {config.GITHUB_PAGES_URL}"
            ),
        )
        if ok:
            enviados += 1
        else:
            falhas += 1

    logger.info(f"\nRESULTADO: {enviados} ok / {falhas} falha(s)")
    logger.info("=" * 55)
    return 0


def _enviar_alerta_incompleto(dados: dict):
    """Camada 4: envia alerta de boletim incompleto para e-mail de monitoramento."""
    try:
        sender = EmailSender()
        if not sender.validar_credenciais():
            logger.error("Camada 4: Não foi possível enviar alerta (credenciais inválidas)")
            return

        email_builder = EmailBuilder()
        alerta_html = email_builder.build_alerta_incompleto(dados)
        if not alerta_html:
            return

        faltantes = dados.get("secoes_faltantes", [])
        assunto = f"⚠ ALERTA — Boletim DOU incompleto — Faltam: {', '.join(faltantes)}"

        ok = sender._enviar_um(
            dest=ALERT_EMAIL,
            assunto=assunto,
            html_body=alerta_html,
            texto_fallback=(
                f"ALERTA: Boletim DOU de {dados.get('data_regular', '')} incompleto. "
                f"Seções faltantes: {', '.join(faltantes)}. "
                f"Reexecutar manualmente pelo GitHub Actions se necessário."
            ),
        )
        if ok:
            logger.info(f"Camada 4: ✓ Alerta enviado para {ALERT_EMAIL}")
        else:
            logger.error(f"Camada 4: ✗ Falha ao enviar alerta para {ALERT_EMAIL}")

    except Exception as e:
        # Alerta de falha não pode travar o envio do boletim
        logger.error(f"Camada 4: Erro ao enviar alerta: {e}")


def main():
    p = argparse.ArgumentParser(description="Boletim DOU")
    p.add_argument("--force", action="store_true")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--test", metavar="EMAIL", default="")
    p.add_argument("--retry", action="store_true", help="Reexecução (não pede nova reexecução)")
    a = p.parse_args()

    exit_code = executar(
        force=a.force,
        preview=a.preview,
        test_email=a.test,
        is_retry=a.retry,
    )
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
