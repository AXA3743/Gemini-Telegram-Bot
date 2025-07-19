import io
import time
import traceback
import sys
from PIL import Image
from telebot.types import Message
from md2tgmd import escape
from telebot import TeleBot
from config import conf, generation_config
from google import genai

gemini_draw_dict = {}
gemini_chat_dict = {}
gemini_pro_chat_dict = {}
default_model_dict = {}

model_1 = conf["model_1"]
model_2 = conf["model_2"]
model_3 = conf["model_3"]
error_info = conf["error_info"]
before_generate_info = conf["before_generate_info"]
download_pic_notify = conf["download_pic_notify"]

search_tool = {'google_search': {}}

client = genai.Client(api_key=sys.argv[2])

# Prompt gaya toxic anak tongkrongan
STYLE_PROMPT = (
    "Jawablah seperti anak tongkrongan yang toxic, nyablak, dan sinis, tapi tetap informatif. "
    "Gunakan gaya bahasa gaul, kadang kasar dikit, penuh candaan, sarkas, dan jangan terlalu baku. "
    "Contoh gaya bicara:\n"
    "- 'Wkwk yaelah masa gitu aja kagak bisa?'\n"
    "- 'Gampang banget itu mah, asal lo mikir dikit.'\n"
    "- 'Buset dah, otak lo ngelag ya? Nih gue bantuin deh.'\n\n"
    "Pertanyaan user:\n"
)

async def gemini_stream(bot: TeleBot, message: Message, m: str, model_type: str):
    sent_message = None
    try:
        sent_message = await bot.reply_to(message, "🧠 Lagi mikir nih...")

        chat_dict = gemini_chat_dict if model_type == model_1 else gemini_pro_chat_dict

        if str(message.from_user.id) not in chat_dict:
            chat = client.aio.chats.create(model=model_type, config={'tools': [search_tool]})
            chat_dict[str(message.from_user.id)] = chat
        else:
            chat = chat_dict[str(message.from_user.id)]

        # Tambahkan gaya toxic ke prompt
        styled_prompt = STYLE_PROMPT + m
        response = await chat.send_message_stream(styled_prompt)

        full_response = ""
        last_update = time.time()
        update_interval = conf["streaming_update_interval"]

        async for chunk in response:
            if hasattr(chunk, 'text') and chunk.text:
                full_response += chunk.text
                current_time = time.time()
                if current_time - last_update >= update_interval:
                    try:
                        await bot.edit_message_text(
                            escape(full_response),
                            chat_id=sent_message.chat.id,
                            message_id=sent_message.message_id,
                            parse_mode="MarkdownV2"
                        )
                    except Exception as e:
                        if "parse markdown" in str(e).lower():
                            await bot.edit_message_text(
                                full_response,
                                chat_id=sent_message.chat.id,
                                message_id=sent_message.message_id
                            )
                        elif "message is not modified" not in str(e).lower():
                            print(f"Error updating message: {e}")
                    last_update = current_time

        try:
            await bot.edit_message_text(
                escape(full_response),
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id,
                parse_mode="MarkdownV2"
            )
        except Exception as e:
            try:
                if "parse markdown" in str(e).lower():
                    await bot.edit_message_text(
                        full_response,
                        chat_id=sent_message.chat.id,
                        message_id=sent_message.message_id
                    )
            except Exception:
                traceback.print_exc()

    except Exception as e:
        traceback.print_exc()
        if sent_message:
            await bot.edit_message_text(
                f"{error_info}\nError details: {str(e)}",
                chat_id=sent_message.chat.id,
                message_id=sent_message.message_id
            )
        else:
            await bot.reply_to(message, f"{error_info}\nError details: {str(e)}")


async def gemini_edit(bot: TeleBot, message: Message, m: str, photo_file: bytes):
    image = Image.open(io.BytesIO(photo_file))
    try:
        response = await client.aio.models.generate_content(
            model=model_3,
            contents=[STYLE_PROMPT + m, image],
            config=generation_config
        )
    except Exception as e:
        await bot.send_message(message.chat.id, e.str())
    for part in response.candidates[0].content.parts:
        if part.text is not None:
            await bot.send_message(message.chat.id, escape(part.text), parse_mode="MarkdownV2")
        elif part.inline_data is not None:
            photo = part.inline_data.data
            await bot.send_photo(message.chat.id, photo)

async def gemini_draw(bot: TeleBot, message: Message, m: str):
    chat_dict = gemini_draw_dict
    if str(message.from_user.id) not in chat_dict:
        chat = client.aio.chats.create(
            model=model_3,
            config=generation_config,
        )
        chat_dict[str(message.from_user.id)] = chat
    else:
        chat = chat_dict[str(message.from_user.id)]

    styled_prompt = STYLE_PROMPT + m
    response = await chat.send_message(styled_prompt)

    for part in response.candidates[0].content.parts:
        if part.text is not None:
            text = part.text
            while len(text) > 4000:
                await bot.send_message(message.chat.id, escape(text[:4000]), parse_mode="MarkdownV2")
                text = text[4000:]
            if text:
                await bot.send_message(message.chat.id, escape(text), parse_mode="MarkdownV2")
        elif part.inline_data is not None:
            photo = part.inline_data.data
            await bot.send_photo(message.chat.id, photo)
