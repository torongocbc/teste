
import logging
import sqlite3
from telegram import (Update, InlineKeyboardMarkup, InlineKeyboardButton)
from telegram.ext import (ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes)

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Banco de dados SQLite
conn = sqlite3.connect("demandas.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS demandas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    descricao TEXT,
    message_id INTEGER,
    status TEXT
)''')
cursor.execute('''
CREATE TABLE IF NOT EXISTS propostas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    demanda_id INTEGER,
    user_id INTEGER,
    username TEXT,
    texto TEXT
)''')
conn.commit()

# Comando /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Bem-vindo! Envie sua demanda com o comando: /demandar <texto>")

# Criar nova demanda
async def demandar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    descricao = ' '.join(context.args)
    if not descricao:
        await update.message.reply_text("Use: /demandar <sua demanda>")
        return

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Fazer Proposta", callback_data=f"proposta_{update.message.message_id}")],
        [InlineKeyboardButton("❌ Cancelar", callback_data=f"cancelar_{update.message.message_id}")]
    ])
    msg = await update.message.reply_text(
        f"📝 *Nova Demanda de {user.first_name} (@{user.username}):*
{descricao}

💬 Propostas:",
        parse_mode="Markdown",
        reply_markup=keyboard
    )

    cursor.execute("INSERT INTO demandas (user_id, username, descricao, message_id, status) VALUES (?, ?, ?, ?, 'aberta')",
                   (user.id, user.username, descricao, msg.message_id))
    conn.commit()

# Lidar com cliques nos botões
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    data = query.data

    if data.startswith("proposta_"):
        demanda_msg_id = int(data.split("_")[1])
        context.user_data['fazendo_proposta'] = demanda_msg_id
        await query.message.reply_text(f"{user.first_name}, envie sua proposta para a demanda acima.")

    elif data.startswith("cancelar_"):
        demanda_msg_id = int(data.split("_")[1])
        cursor.execute("SELECT user_id FROM demandas WHERE message_id=?", (demanda_msg_id,))
        result = cursor.fetchone()
        if result and result[0] == user.id:
            cursor.execute("UPDATE demandas SET status='cancelada' WHERE message_id=?", (demanda_msg_id,))
            cursor.execute("DELETE FROM propostas WHERE demanda_id=(SELECT id FROM demandas WHERE message_id=?)", (demanda_msg_id,))
            conn.commit()
            await query.message.edit_text("❌ Esta demanda foi cancelada.")
        else:
            await query.message.reply_text("Apenas o criador da demanda pode cancelá-la.")

# Lidar com mensagens de proposta
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    if 'fazendo_proposta' not in context.user_data:
        return

    demanda_msg_id = context.user_data.pop('fazendo_proposta')
    cursor.execute("SELECT id FROM demandas WHERE message_id=? AND status='aberta'", (demanda_msg_id,))
    result = cursor.fetchone()
    if not result:
        await update.message.reply_text("Demanda não encontrada ou já encerrada.")
        return

    demanda_id = result[0]
    texto_proposta = update.message.text
    cursor.execute("INSERT INTO propostas (demanda_id, user_id, username, texto) VALUES (?, ?, ?, ?)",
                   (demanda_id, user.id, user.username, texto_proposta))
    conn.commit()

    propostas = cursor.execute("SELECT username, texto FROM propostas WHERE demanda_id=?", (demanda_id,)).fetchall()
    proposta_texto = "
".join([f"@{u}: {t}" for u, t in propostas])

    demanda = cursor.execute("SELECT descricao FROM demandas WHERE id=?", (demanda_id,)).fetchone()

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📩 Fazer Proposta", callback_data=f"proposta_{demanda_msg_id}")],
        [InlineKeyboardButton("❌ Cancelar", callback_data=f"cancelar_{demanda_msg_id}")]
    ])

    try:
        await context.bot.edit_message_text(
            chat_id=update.message.chat_id,
            message_id=demanda_msg_id,
            text=f"📝 *Demanda:* {demanda[0]}

💬 Propostas:
{proposta_texto}",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    except:
        pass

# Função principal
def main():
    app = ApplicationBuilder().token("SEU_TOKEN_AQUI").build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("demandar", demandar))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("Bot rodando...")
    app.run_polling()

if __name__ == '__main__':
    main()
