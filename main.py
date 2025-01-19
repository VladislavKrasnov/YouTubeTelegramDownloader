import os
import json
import re
import asyncio
from aiogram import Bot, Dispatcher, Router
from aiogram.types import Message, FSInputFile
from aiogram.filters import Command
from data.config import TOKEN, AUDIO_DIR, DATA_FILE
import yt_dlp
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


os.makedirs(AUDIO_DIR, exist_ok=True)


if not os.path.exists(DATA_FILE) or os.path.getsize(DATA_FILE) == 0:
    with open(DATA_FILE, 'w', encoding='utf-8') as file:
        json.dump({}, file)
    downloads = {}
else:
    with open(DATA_FILE, 'r', encoding='utf-8') as file:
        downloads = json.load(file)

bot = Bot(token=TOKEN)
dp = Dispatcher()
router = Router()

def extract_video_id(url: str) -> str:
    match = re.search(r'(?:v=|/shorts/|youtu\.be/)([\w-]+)', url)
    return match.group(1) if match else None

def download_audio(video_id: str) -> str:
    url = f'https://www.youtube.com/watch?v={video_id}'
    file_path = os.path.join(AUDIO_DIR, f"{video_id}.mp3")
    
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio[abr<=32]',
        'outtmpl': file_path,
        'noplaylist': True,
        'postprocessors': [],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get('title', video_id)
        author = info.get('uploader', 'Unknown')

    return file_path, title, author

def get_video_info(video_id: str) -> dict:
    url = f'https://www.youtube.com/watch?v={video_id}'
    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio[ext=mp3]/bestaudio[abr<=32]',
        'noplaylist': True,
        'quiet': True,
        'extract_flat': True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        return info

@router.message(Command("start"))
async def start_command(message: Message):
    await message.reply("Привет! Я бот для скачивания аудио из YouTube. Просто отправь мне ссылку на видео, и я сделаю остальное!")

@router.message()
async def handle_message(message: Message):
    if not message.text or "http" not in message.text:
        return
    
    try:
        url = message.text.split('?')[0]
        video_id = extract_video_id(url)

        if not video_id:
            await message.reply("Не удалось извлечь ID видео. Убедитесь, что ссылка корректна.")
            return

        download_message = await message.reply("📦 Видео скачивается. Ожидайте...")

        if video_id in downloads:
            file_id = downloads[video_id]['file_id']
            title = downloads[video_id]['title']
            author = downloads[video_id]['author']
            await bot.send_audio(chat_id=message.chat.id, audio=file_id, title=title, performer=author)
        else:
            info = get_video_info(video_id)
            file_size = info.get('filesize', 0)

            if file_size > 50 * 1024 * 1024:
                await download_message.delete()
                await message.reply("📦 Ошибка. Размер аудио больше ограничения.")
                return

            audio_path, title, author = download_audio(video_id)
            audio_file = FSInputFile(audio_path)
            file_size = os.path.getsize(audio_path)

            if file_size > 50 * 1024 * 1024:
                await download_message.delete()
                await message.reply("📦 Ошибка. Размер аудио больше ограничения.")
                os.remove(audio_path)
            else:
                sent_message = await bot.send_audio(chat_id=message.chat.id, audio=audio_file, title=title, performer=author)
                
                downloads[video_id] = {
                    'url': url,
                    'file_id': sent_message.audio.file_id,
                    'title': title,
                    'author': author
                }
                with open(DATA_FILE, 'w', encoding='utf-8') as file:
                    json.dump(downloads, file, ensure_ascii=False, indent=4)

                os.remove(audio_path)

        await download_message.delete()

    except Exception as e:
        logging.error(f"Ошибка: {e}")
        await download_message.delete()
        await message.reply("⚠️ Произошла ошибка при обработке. Попробуйте ещё раз.")

async def main():
    try:
        dp.include_router(router)
        await dp.start_polling(bot)
    except Exception as e:
        logging.error(f"Ошибка запуска бота: {e}")
        await main()

if __name__ == '__main__':
    asyncio.run(main())