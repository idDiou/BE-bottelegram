# Imagem base leve do Python
FROM python:3.12-slim

# Metadados
LABEL maintainer="BE+"
LABEL description="Bot de Escala de Limpeza - Telegram"

# Define o diretório de trabalho dentro do container
WORKDIR /app

# Copia e instala as dependências primeiro (cache do Docker)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia o restante dos arquivos do projeto
COPY . .

# Garante que o config.json exista antes de iniciar
RUN test -f config.json || echo '{"indice_atual": 0}' > config.json

# Variáveis de ambiente obrigatórias (fornecidas em runtime via --env-file ou -e)
ENV TELEGRAM_TOKEN=""
ENV CHAT_ID=""

# Comando de inicialização
CMD ["python", "-u", "bot.py"]
