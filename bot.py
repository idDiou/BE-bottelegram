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

def obter_responsavel_atual() -> str:
    """Retorna o nome do colaborador atual da escala."""
    config = carregar_config()
    colaboradores = config["colaboradores"]
    return colaboradores[config["indice_atual"]]


def avancar_escala() -> str:
    """Avança o índice da escala para o próximo colaborador e salva."""
    config = carregar_config()
    colaboradores = config["colaboradores"]
    config["indice_atual"] = (config["indice_atual"] + 1) % len(colaboradores)
    salvar_config(config)
    return colaboradores[config["indice_atual"]]


def obter_proximo() -> str:
    """Retorna o nome do próximo colaborador sem avançar o índice."""
    config = carregar_config()
    colaboradores = config["colaboradores"]
    proximo_idx = (config["indice_atual"] + 1) % len(colaboradores)
    return colaboradores[proximo_idx]


def montar_mensagem_diaria() -> str:
    """Monta a mensagem de notificação diária."""
    responsavel = obter_responsavel_atual()
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    proximo = obter_proximo()
    return (
        f"{EMOJI_LIMPEZA} *Escala de Limpeza — {data_hoje}* {EMOJI_LIMPEZA}\n\n"
        f"Olá, equipe! O responsável pela limpeza *hoje* é:\n\n"
        f"👤 *{responsavel}*\n\n"
        f"Próximo(a) na fila: _{proximo}_\n\n"
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
    """Informa quem é o responsável atual."""
    responsavel = obter_responsavel_atual()
    data_hoje = datetime.now().strftime("%d/%m/%Y")
    texto = (
        f"{EMOJI_CALENDARIO} *Responsável hoje ({data_hoje}):*\n\n"
        f"👤 *{responsavel}*"
    )
    bot.reply_to(message, texto)


@bot.message_handler(commands=["escala"])
def cmd_escala(message: telebot.types.Message) -> None:
    """Exibe a lista completa de colaboradores e destaca o atual."""
    config = carregar_config()
    idx_atual = config["indice_atual"]
    proximo = obter_proximo()

    colaboradores = config["colaboradores"]
    linhas = [f"{EMOJI_LISTA} *Escala de Limpeza — Equipe Completa*\n"]
    for i, nome in enumerate(colaboradores):
        if i == idx_atual:
            linhas.append(f"▶️ *{i + 1}. {nome}* ← atual")
        else:
            linhas.append(f"   {i + 1}. {nome}")

    linhas.append(f"\n⏭️ Próximo(a): _{proximo}_")
    bot.reply_to(message, "\n".join(linhas))


@bot.message_handler(commands=["pular"])
def cmd_pular(message: telebot.types.Message) -> None:
    """Pula a vez do colaborador atual, reinserindo-o na posição seguinte."""
    config = carregar_config()
    colaboradores = config["colaboradores"]
    idx = config["indice_atual"]

    pulado = colaboradores[idx]

    # Remove o colaborador pulado da posição atual
    colaboradores.pop(idx)
    novo_total = len(colaboradores)

    # Índice do próximo (quem assume agora pode ter mudado se idx era o último)
    novo_idx = idx % novo_total

    # Reinsere o colaborador pulado logo após o próximo (amanhã ele faz a limpeza)
    pos_insercao = novo_idx + 1
    if pos_insercao > novo_total:
        pos_insercao = 1  # Envolve no final da lista
    colaboradores.insert(pos_insercao, pulado)

    config["indice_atual"] = novo_idx
    config["colaboradores"] = colaboradores
    salvar_config(config)

    proximo = colaboradores[novo_idx]
    depois = colaboradores[(novo_idx + 1) % len(colaboradores)]

    texto = (
        f"{EMOJI_PULAR} *Vez transferida!*\n\n"
        f"_{pulado}_ foi movido(a) para o próximo dia.\n\n"
        f"📅 *Hoje:* {proximo}\n"
        f"📅 *Amanhã:* {depois}"
    )
    bot.reply_to(message, texto)
    logger.info(
        "Comando /pular por %s. %s transferido(a) para amanhã. Hoje: %s.",
        message.from_user.username or message.from_user.first_name,
        pulado,
        proximo,
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
