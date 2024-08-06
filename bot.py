import discord
from discord.ext import commands
from discord import FFmpegPCMAudio, File, app_commands
import os
import random
from dotenv import load_dotenv
import yt_dlp
import asyncio
from util import join_channel
# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class MusicBot(commands.Bot):
    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix, intents=intents)
        self.connected_since = {}  # Dictionary to track connection time by guild ID
        self.queue = []
        self.firstInQueue = True

bot = MusicBot(command_prefix='/', intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    await bot.tree.sync()
    # await tree.sync(guild=discord.Object(id=346798764435963904))

@bot.hybrid_command(name='legend', help='Responds with a legendary music YouTube link.')
async def legend(ctx):
    response = 'https://youtu.be/cvav25BQ9Ec?si=98AxA8lc4EvhRLKI&t=20'
    await ctx.send(response)


@bot.hybrid_command(name='halifoto', help='Posts a random photo.')
async def halipic(ctx):
    directory_path = 'images'  # Adjust this to your directory path
    image_files = os.listdir(directory_path)
    random_image_file = random.choice(image_files)
    file_path = os.path.join(directory_path, random_image_file)
    await ctx.send(file=File(file_path))

@bot.hybrid_command(name='katil', help='Bot joins the voice channel')
async def join(ctx):
    await ctx.send("Joining the voice channel...")
    await join_channel(ctx, bot, bot.queue)

@bot.hybrid_command(name='ayril', help='Bot leaves the voice channel')
async def leave(ctx):
    if ctx.voice_client:
        await ctx.send("Leaving the voice channel...")
        bot.queue.clear()
        if ctx.guild.id in bot.connected_since:
            del bot.connected_since[ctx.guild.id]  # Clear the tracked time
        await ctx.voice_client.disconnect()
    else:
        await ctx.send("I'm not in a voice channel.")

@bot.hybrid_command(name='oynat', help='Searches and plays music from YouTube.')
async def play(ctx, *, search: str):
    voice_client = await join_channel(ctx, bot, bot.queue)
    if voice_client is None:
        return

    ydl_opts = {
        'format': 'bestaudio',
        'default_search': 'ytsearch',
        'noplaylist': True,
        'quiet': True
    }

    await ctx.send(f"Searching for '{search}' on YouTube...")

    author = ctx.author

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{search}", download=False)['entries'][0]
        title = info['title']
        url = info['webpage_url']

    bot.queue.append((author.name, title, url))  # Store title and URL as a tuple
    if not voice_client.is_playing():
        await play_next(ctx)
    else:
        await ctx.send(f"Added to queue: {title} - {url}")
        bot.firstInQueue = False

async def play_next(ctx):
    if len(bot.queue) > 0:
        _, _, song_url = bot.queue.pop(0)
        await play_song(ctx, song_url)
    elif not ctx.voice_client:
        await ctx.send("Queue is empty, add more songs!")

async def play_song(ctx, song):
    ydl_opts = {
        'format': 'bestaudio',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '192',
        }],
        'quiet': False
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(song, download=False)
        url = info['url']

    source = FFmpegPCMAudio(url, before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', options='-vn -sn -dn -ignore_unknown')
    ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
    
    if bot.firstInQueue:
        await ctx.send(f"Now playing: {info.get('title', 'Unknown title')}\n {info.get('webpage_url', 'Unknown URL')}")
    else:
        await ctx.send(f"Now playing: {info.get('title', 'Unknown title')}")

@bot.hybrid_command(name='durdur', help='Pauses the currently playing audio.')
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()
        await ctx.send("Playback paused.")
    else:
        await ctx.send("No audio is currently playing.")

@bot.hybrid_command(name='devam', help='Resumes the paused audio.')
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()
        await ctx.send("Playback resumed.")
    else:
        await ctx.send("No audio is paused.")

@bot.hybrid_command(name='atla', help='Skips the currently playing song.')
async def skip(ctx):
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        await ctx.send("Skipping to the next song.")
        ctx.voice_client.stop()  # Stopping current song will trigger play_next automatically if there are more songs in the queue
    else:
        await ctx.send("No song is currently playing.")

@bot.hybrid_command(name='sira', help='Shows the current music queue.')
async def show_queue(ctx):
    if bot.queue:
        message = "Current queue:\n" + "\n".join(f"{idx + 1}. {title} Added By : {author}" for idx, (author,title, url) in enumerate(bot.queue))
        await ctx.send(message)
    else:
        bot.firstInQueue = True
        await ctx.send("The music queue is currently empty.")

@bot.hybrid_command(name='siradan-cikar', help='Removes a specific song from the queue by its position.')
async def remove(ctx, position: int):
    if len(bot.queue) >= position > 0:  # Ensure the position is within the valid range
        # Remove the song at the specified position (adjust for zero-based index)
        removed_song = bot.queue.pop(position - 1)
        await ctx.send(f"Removed song {position} from the queue.")
    else:
        await ctx.send("Invalid position. Please enter a valid song number.")


bot.run(TOKEN)
