"""
Bot de Escala de Limpeza - Telegram
Gerencia a escala rotativa de limpeza para uma equipe de 8 pessoas.
"""

import json
import logging
import os
import threading
import time
from datetime import datetime, time as dtime

import telebot
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Configuração inicial
# ---------------------------------------------------------------------------
load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

if not TOKEN or not CHAT_ID:
    raise EnvironmentError(
        "TELEGRAM_TOKEN e CHAT_ID devem estar definidos no arquivo .env"
    )

bot = telebot.TeleBot(TOKEN, parse_mode="Markdown")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
CONFIG_FILE = "config.json"
HORA_ENVIO = dtime(13, 0)  # 13:00

COLABORADORES: list[str] = [
    "Julia",
    "Raissa",
    "Gabriel",
    "David",
    "João",
    "Ilana",
    "Dionata",
    "Jean",
    "Renata",
    "Ivan"
]

# Emojis para deixar as mensagens mais simpáticas
EMOJI_LIMPEZA = "🧹"
EMOJI_CALENDARIO = "📅"
EMOJI_LISTA = "📋"
EMOJI_PULAR = "⏭️"
EMOJI_OK = "✅"

# ---------------------------------------------------------------------------
# Persistência (config.json)
# ---------------------------------------------------------------------------

def carregar_config() -> dict:
    """Carrega o estado persistido do arquivo config.json."""
    config = {"indice_atual": 0, "colaboradores": COLABORADORES.copy()}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                dados = json.load(f)
            config.update(dados)
            # Migração: garante que a lista exista no config salvo
            if "colaboradores" not in dados:
                config["colaboradores"] = COLABORADORES.copy()
                salvar_config(config)
        except (json.JSONDecodeError, IOError) as e:
            logger.error("Erro ao ler config.json: %s. Recriando...", e)
    return config


def salvar_config(config: dict) -> None:
    """Salva o estado atual no arquivo config.json."""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except IOError as e:
        logger.error("Erro ao salvar config.json: %s", e)


# ---------------------------------------------------------------------------
# Helpers de escala
# ---------------------------------------------------------------------------

def _obter_par(colaboradores: list, idx: int) -> list:
    """Retorna a dupla (1 ou 2 nomes) a partir do índice dado."""
    total = len(colaboradores)
    idx_norm = idx % total
    par = [colaboradores[idx_norm]]
    if idx_norm + 1 < total:
        par.append(colaboradores[idx_norm + 1])
    return par


def obter_responsavel_atual() -> list:
    """Retorna a dupla atual da escala."""
    config = carregar_config()
    return _obter_par(config["colaboradores"], config["indice_atual"])


def avancar_escala() -> list:
    """Avança o índice da escala em 2 (dupla) e salva."""
    config = carregar_config()
    colaboradores = config["colaboradores"]
    config["indice_atual"] = (config["indice_atual"] + 2) % len(colaboradores)
    salvar_config(config)
    return _obter_par(colaboradores, config["indice_atual"])


def obter_proximo() -> list:
    """Retorna a próxima dupla sem avançar o índice."""
    config = carregar_config()
    colaboradores = config["colaboradores"]
    proximo_idx = (config["indice_atual"] + 2) % len(colaboradores)
    return _obter_par(colaboradores, proximo_idx)


def montar_mensagem_diaria() -> str:
    """Monta a mensagem de notificação diária para a dupla."""
    dupla = obter_responsavel_atual()
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    proxima = obter_proximo()
    nomes_hoje = "\n".join(f"👤 *{n}*" for n in dupla)
    proxima_str = " + ".join(proxima)
    label = "responsáveis" if len(dupla) > 1 else "responsável"
    return (
        f"{EMOJI_LIMPEZA} *Escala de Limpeza — {data_hoje}* {EMOJI_LIMPEZA}\n\n"
        f"Olá, equipe! Os {label} pela limpeza *hoje* são:\n\n"
        f"{nomes_hoje}\n\n"
        f"Próxima dupla: _{proxima_str}_\n\n"
        f"Bom trabalho! {EMOJI_OK}"
    )


# ---------------------------------------------------------------------------
# Envio da mensagem diária
# ---------------------------------------------------------------------------

def enviar_mensagem_diaria() -> None:
    """Envia a mensagem de escala e avança o índice."""
    try:
        msg = montar_mensagem_diaria()
        bot.send_message(CHAT_ID, msg)
        logger.info("Mensagem diária enviada para o chat %s.", CHAT_ID)
        avancar_escala()
    except telebot.apihelper.ApiException as e:
        logger.error("Erro na API do Telegram ao enviar mensagem: %s", e)
    except Exception as e:
        logger.error("Erro inesperado ao enviar mensagem diária: %s", e)


# ---------------------------------------------------------------------------
# Scheduler (loop em thread separada)
# ---------------------------------------------------------------------------

def e_dia_util() -> bool:
    """Retorna True se hoje for segunda a sexta-feira."""
    return datetime.now().weekday() < 4  # 0=Seg, 3=Qui


def scheduler_loop() -> None:
    """Loop de agendamento que verifica o horário e dispara a mensagem."""
    logger.info("Scheduler iniciado. Mensagem será enviada às %s.", HORA_ENVIO)
    enviado_hoje = False

    while True:
        agora = datetime.now()
        hora_atual = agora.time().replace(second=0, microsecond=0)

        # Reseta o flag a meia-noite
        if agora.hour == 0 and agora.minute == 0:
            enviado_hoje = False

        if hora_atual == HORA_ENVIO and not enviado_hoje:
            if e_dia_util():
                logger.info("Hora do envio! Disparando mensagem diária...")
                enviar_mensagem_diaria()
            else:
                logger.info("Fim de semana detectado. Mensagem não enviada.")
            enviado_hoje = True

        time.sleep(30)  # Verifica a cada 30 segundos


# ---------------------------------------------------------------------------
# Handlers dos comandos do bot
# ---------------------------------------------------------------------------

@bot.message_handler(commands=["start", "ajuda"])
def cmd_start(message: telebot.types.Message) -> None:
    """Exibe mensagem de boas-vindas e lista de comandos."""
    texto = (
        f"{EMOJI_LIMPEZA} *Bot de Escala de Limpeza* {EMOJI_LIMPEZA}\n\n"
        "Comandos disponíveis:\n\n"
        f"`/hoje` — Quem é o responsável hoje\n"
        f"`/escala` — Lista completa da equipe\n"
        f"`/pular` — Pular a vez atual _(admin)_\n"
        f"`/ajuda` — Exibe esta mensagem"
    )
    bot.reply_to(message, texto)


@bot.message_handler(commands=["hoje"])
def cmd_hoje(message: telebot.types.Message) -> None:
    """Informa quem são os responsáveis atuais (dupla)."""
    dupla = obter_responsavel_atual()
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    nomes = "\n".join(f"👤 *{n}*" for n in dupla)
    label = "Responsáveis" if len(dupla) > 1 else "Responsável"
    texto = (
        f"{EMOJI_CALENDARIO} *{label} hoje ({data_hoje}):*\n\n"
        f"{nomes}"
    )
    bot.reply_to(message, texto)


@bot.message_handler(commands=["escala"])
def cmd_escala(message: telebot.types.Message) -> None:
    """Exibe a lista completa de duplas e destaca a atual."""
    config = carregar_config()
    idx_atual = config["indice_atual"]
    colaboradores = config["colaboradores"]
    total = len(colaboradores)
    proxima = obter_proximo()
    proxima_str = " + ".join(proxima)

    linhas = [f"{EMOJI_LISTA} *Escala de Limpeza — Duplas*\n"]
    dupla_num = 1
    i = 0
    while i < total:
        par = _obter_par(colaboradores, i)
        par_str = " + ".join(par)
        if i == idx_atual:
            linhas.append(f"▶️ *Dupla {dupla_num}: {par_str}* ← atual")
        else:
            linhas.append(f"   Dupla {dupla_num}: {par_str}")
        i += len(par)
        dupla_num += 1

    linhas.append(f"\n⏭️ Próxima dupla: _{proxima_str}_")
    bot.reply_to(message, "\n".join(linhas))


@bot.message_handler(commands=["pular"])
def cmd_pular(message: telebot.types.Message) -> None:
    """Pula a vez da dupla atual, reinserindo-a logo após a próxima dupla."""
    config = carregar_config()
    colaboradores = config["colaboradores"]
    idx = config["indice_atual"]

    par_pulado = _obter_par(colaboradores, idx)
    tamanho = len(par_pulado)

    # Remove a dupla da posição atual
    for _ in range(tamanho):
        if idx < len(colaboradores):
            colaboradores.pop(idx)

    novo_total = len(colaboradores)
    novo_idx = idx % novo_total

    # Reinsere logo após a próxima dupla (2 posições à frente)
    pos_insercao = novo_idx + 2
    if pos_insercao > novo_total:
        pos_insercao = min(2, novo_total)
    for i, nome in enumerate(par_pulado):
        colaboradores.insert(pos_insercao + i, nome)

    config["indice_atual"] = novo_idx
    config["colaboradores"] = colaboradores
    salvar_config(config)

    proxima_dupla = _obter_par(colaboradores, novo_idx)
    depois_dupla = _obter_par(colaboradores, (novo_idx + 2) % len(colaboradores))
    pulado_str = " + ".join(par_pulado)
    proxima_str = " + ".join(proxima_dupla)
    depois_str = " + ".join(depois_dupla)

    texto = (
        f"{EMOJI_PULAR} *Dupla transferida!*\n\n"
        f"_{pulado_str}_ foram movidos(as) para o próximo dia.\n\n"
        f"📅 *Hoje:* {proxima_str}\n"
        f"📅 *Amanhã:* {depois_str}"
    )
    bot.reply_to(message, texto)
    logger.info(
        "Comando /pular por %s. Dupla %s transferida. Hoje: %s.",
        message.from_user.username or message.from_user.first_name,
        pulado_str,
        proxima_str,
    )


# ---------------------------------------------------------------------------
# Ponto de entrada
# ---------------------------------------------------------------------------

def main() -> None:
    logger.info("Iniciando Bot de Escala de Limpeza...")

    # Inicia o scheduler em thread daemon
    thread_scheduler = threading.Thread(target=scheduler_loop, daemon=True)
    thread_scheduler.start()

    # Inicia o polling do bot com tratamento de exceções
    logger.info("Bot em execução. Aguardando comandos...")
    while True:
        try:
            bot.infinity_polling(timeout=30, long_polling_timeout=30)
        except telebot.apihelper.ApiException as e:
            logger.error("Erro na API do Telegram: %s. Reconectando em 15s...", e)
            time.sleep(15)
        except Exception as e:
            logger.error("Erro inesperado no polling: %s. Reconectando em 15s...", e)
            time.sleep(15)


if __name__ == "__main__":
    main()
