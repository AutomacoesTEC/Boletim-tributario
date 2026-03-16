# 📋 Boletim DOU Tributário

Informativo automatizado do Diário Oficial da União para profissionais jurídicos tributários.

Coleta diariamente as publicações das **Seções 1, 2 e 3** do DOU, filtra pelos órgãos relevantes, e envia um boletim profissional por e-mail — de segunda a sexta, às 07:00 (Brasília).

## O que o sistema faz

- **Edições regulares** (Seções 1, 2, 3): publicações do **dia atual** (~06:00)
- **Edições extras** (A, B, C, D...): publicações do **dia útil anterior**
- **Filtro por órgão**: Atos dos 3 Poderes, Presidência, Min. Fazenda, Entidades de Fiscalização
- **Feriados nacionais**: não envia (calendário 2025 + 2026 pré-configurado)
- **E-mail profissional**: HTML responsivo para Outlook/Gmail/Apple Mail
- **Gestão de assinantes**: CLI completa
- **Agendamento**: GitHub Actions (cron seg-sex 07:00 BRT) — sem servidor, sem custo

## Estrutura

```
dou-newsletter/
├── .github/workflows/newsletter.yml   # Cron seg-sex 07:00 BRT
├── config.py                          # Órgãos, feriados, SMTP
├── dou_fetcher.py                     # Coleta da API do DOU
├── email_builder.py                   # Gerador do HTML
├── email_sender.py                    # Envio via Gmail SMTP
├── subscriber_manager.py              # CRUD de assinantes
├── main.py                            # Orquestrador
├── manage.py                          # CLI de gestão
├── subscribers.json                   # Lista de e-mails
└── requirements.txt
```

## Setup Rápido

### 1. Instalar

```bash
git clone https://github.com/SEU-USUARIO/dou-newsletter.git
cd dou-newsletter
pip install -r requirements.txt
```

### 2. Configurar Gmail

1. Ative **Verificação em 2 etapas** na conta Google
2. Acesse: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
3. Crie senha para **"Outro"** → **"Boletim DOU"**

```bash
export GMAIL_USER="seu-email@gmail.com"
export GMAIL_APP_PASSWORD="abcd efgh ijkl mnop"
```

### 3. Testar

```bash
python manage.py test-smtp                   # Testar conexão
python manage.py add seu@email.com "Nome"    # Cadastrar
python manage.py preview                     # Gerar preview.html
python manage.py send-test seu@email.com     # Enviar teste
```

### 4. GitHub Actions

1. Push para o GitHub
2. **Settings → Secrets → Actions** → adicione `GMAIL_USER` e `GMAIL_APP_PASSWORD`
3. Pronto! Envia automaticamente seg-sex às 07:00 BRT

## CLI Completa

```bash
# Assinantes
python manage.py add email@ex.com "Nome"
python manage.py remove email@ex.com
python manage.py list
python manage.py import emails.txt

# Execução
python main.py                    # Normal (verifica dia útil)
python main.py --force            # Forçar em qualquer dia
python main.py --preview          # Gerar HTML sem enviar
python main.py --test email@x.com # Enviar só para um e-mail
```

## Lógica de datas

| Tipo | Data buscada | Quando publica |
|------|-------------|----------------|
| Edição regular (Seções 1, 2, 3) | **Hoje** | ~06:00 BRT |
| Edição Extra (A, B, C...) | **Dia útil anterior** | Qualquer momento |

O boletim das 07:00 sempre inclui todas as regulares do dia + todas as extras do dia anterior.

## Personalização

Edite `config.py` para alterar órgãos monitorados (`ORGAOS_FILTRO`), seções (`SECOES_REGULARES`), ou feriados.

## Licença

Uso livre. Os dados do DOU são públicos (Lei 12.527/2011).

