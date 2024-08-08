import discord
from discord.ext import commands
from discord import FFmpegPCMAudio, File, app_commands
import os
import random
from dotenv import load_dotenv
import yt_dlp
import asyncio
from util import join_channel
import datetime

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

class MusicBot(commands.Bot):

    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix, intents=intents)
        self.connected_since = {}  # Dictionary to track connection time by guild ID
        self.queue = {}
        self.firstInQueue = True
        self.currently_playing = {}

    def get_queue(self, guild_id):
        if guild_id not in self.queue:
            self.queue[guild_id] = []
        return self.queue[guild_id]
    
    def load_currently_playing(self, guild_id, songTuple):
        self.currently_playing[guild_id] = songTuple
    
    def get_currently_playing(self, guild_id):
        if self.currently_playing[guild_id] is None:
            return []
        return self.currently_playing[guild_id]
    
    def add_to_queue(self, guild_id, item):
        """Add an item to the guild-specific queue."""
        self.get_queue(guild_id).append(item)
    
    def pop_from_queue(self, guild_id):
        """Pop the first item from the guild-specific queue."""
        queue = self.get_queue(guild_id)
        if queue:
            return queue.pop(0)
        else:
            raise IndexError("Queue is empty, cannot pop.")

    def clear_queue(self, guild_id):
        """Clear the guild-specific queue."""
        self.get_queue(guild_id).clear()

    def remove_from_queue(self, guild_id, position):
        """Remove an item from a specific position in the guild-specific queue."""
        queue = self.get_queue(guild_id)
        if len(queue) > position >= 0:
            return queue.pop(position)
        else:
            raise IndexError("Queue position out of range.")

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
    await join_channel(ctx, bot)

@bot.hybrid_command(name='ayril', help='Bot leaves the voice channel')
async def leave(ctx):
    queue = bot.get_queue(ctx.guild.id)
    
    if ctx.voice_client:

        await ctx.send("Leaving the voice channel...")
        queue.clear()

        if ctx.guild.id in bot.connected_since:
            del bot.connected_since[ctx.guild.id]  # Clear the tracked time
        
        await ctx.voice_client.disconnect()
    else:

        await ctx.send("I'm not in a voice channel.")

@bot.hybrid_command(name='oynat', help='Searches and plays music from YouTube.')
async def play(ctx, *, search: str):

    if ctx.voice_client is None:
        isFirstSongPlayed = True
    else:
        isFirstSongPlayed = False

    queue = bot.queue.get(ctx.guild.id)
    voice_client = await join_channel(ctx, bot)
    if voice_client is None:
        return

    ydl_opts = {
        'format': 'bestaudio',
        'default_search': 'ytsearch',
        'noplaylist': True,
        'quiet': True
    }

    searchEmbed = discord.Embed(
        title="Searching...",
        color=discord.Colour.dark_purple(),
        description=f"Searching for '{search}' on YouTube..."
    )

    searchEmbed.set_thumbnail(url=bot.user.display_avatar.url)

    embedMessage = await ctx.send(embed=searchEmbed)

    author = ctx.author

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{search}", download=False)['entries'][0]
        title = info['title']
        url = info['webpage_url']
        thumbnail = info['thumbnail']
        sec_duration = info['duration']

    duration = str(datetime.timedelta(seconds = int(sec_duration)))
        
    songTuple = (author.name, title, url, thumbnail, duration, isFirstSongPlayed)  # Store title and URL as a tuple
    bot.add_to_queue(ctx.guild.id, songTuple)

    if not (voice_client.is_playing() or voice_client.is_paused()):

        await play_next(ctx, embedMessage)
    else:

        addQueueEmbed = discord.Embed(
        title=title,
        color=discord.Colour.dark_purple(),
        description=f"[Watch on YouTube]({url})"
        )

        addQueueEmbed.set_author(name=f"Added to Queue:")
        addQueueEmbed.set_thumbnail(url=thumbnail)
        addQueueEmbed.insert_field_at(1, name="Video Duration", value=f"> Duration: `{duration}`", inline=True)
        addQueueEmbed.insert_field_at(2, name="Added by", value=f"> Added by: {author.name}", inline=True)
        addQueueEmbed.set_footer(text=f"Addded to Position: {len(bot.get_queue(ctx.guild.id))}")

        await embedMessage.edit(embed=addQueueEmbed)

async def play_next(ctx, embedToEdit):

    queue = bot.get_queue(ctx.guild.id)

    if len(queue) > 0:

        playInfoTuple = bot.pop_from_queue(ctx.guild.id)
        bot.load_currently_playing(ctx.guild.id, playInfoTuple)
        await play_song(ctx, playInfoTuple, embedToEdit)
    elif not ctx.voice_client:

        await ctx.send("Queue is empty, add more songs!")


async def play_song(ctx, playInfo, embedToEdit):
    queue = bot.get_queue(ctx.guild.id)
    
    ydl_opts = {
        'format': 'm4a',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '192k',
        }],
        'quiet': False
    }

    requester, title, song_url, thumbnail_url, vid_duration, isFirstSongPlayed = playInfo

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(song_url, download=False)
        url = info['url']

    source = FFmpegPCMAudio(url, before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', options='-vn -sn -dn -ar 48000 -ab 64k -ac 2')
    ctx.voice_client.play(source, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx, embedToEdit), bot.loop))

    nowPlayingEmbed = discord.Embed(
        title=title,
        color=discord.Colour.dark_purple(),
        description=f"[Watch on YouTube]({song_url})"
        )

    nowPlayingEmbed.set_author(name=f"Now Playing:")
    nowPlayingEmbed.set_thumbnail(url=bot.user.display_avatar.url)
    nowPlayingEmbed.insert_field_at(1, name="Video Duration", value=f"> Duration: `{vid_duration}`", inline=True)
    nowPlayingEmbed.insert_field_at(2, name="Added by", value=f"> Added by: {requester}", inline=True)
    nowPlayingEmbed.set_image(url=thumbnail_url)
    nowPlayingEmbed.set_footer(text=f"Playing Next:\n > {queue[0][1] if queue else 'No more songs in queue'}")

    if isFirstSongPlayed:

        await embedToEdit.edit(embed=nowPlayingEmbed)
    else:

        await ctx.send(embed=nowPlayingEmbed)
    

@bot.hybrid_command(name='durdur', help='Pauses the currently playing audio.')
async def pause(ctx):

    if ctx.voice_client and ctx.voice_client.is_playing():

        currentSongTuple = bot.get_currently_playing(ctx.guild.id)

        pauseEmbed = discord.Embed(
            title=f"{currentSongTuple[1]} is Paused",
            color=discord.Colour.dark_purple(),
            description=f"Song is paused by `{ctx.author.name}`."
        )
        pauseEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        pauseEmbed.set_footer(text=f"Use `/devam` to resume the song.")

        ctx.voice_client.pause()
        await ctx.send(embed = pauseEmbed)
    else:
        noPauseEmbed = discord.Embed(
            title="No Audio Playing",
            color=discord.Colour.dark_purple()
        )

        pauseEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        pauseEmbed.set_footer(text=f"Use `/oynat` to play a song.")

        await ctx.send(embed = noPauseEmbed)

@bot.hybrid_command(name='devam', help='Resumes the paused audio.')
async def resume(ctx):

    if ctx.voice_client and ctx.voice_client.is_paused():

        currentSongTuple = bot.get_currently_playing(ctx.guild.id)

        resumeEmbed = discord.Embed(
            title=f"Resuming {currentSongTuple[1]}",
            color=discord.Colour.dark_purple(),
            description=f"Song is resumed by `{ctx.author.name}`."
        )

        resumeEmbed.set_thumbnail(url=bot.user.display_avatar.url)

        ctx.voice_client.resume()
        await ctx.send(embed = resumeEmbed)
    else:

        noResumeEmbed = discord.Embed(
            title="No Audio Paused",
            color=discord.Colour.dark_purple()
        )

        noResumeEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        await ctx.send(embed = noResumeEmbed)

@bot.hybrid_command(name='atla', help='Skips the currently playing song.')
async def skip(ctx):

    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):

        queue = bot.get_queue(ctx.guild.id)
        currentSongTuple = bot.get_currently_playing(ctx.guild.id)
        if queue:
            nexSongTuple = queue[0]
            descriptionText = f"Next song in queue: {nexSongTuple[1]}"
        else:
            descriptionText = f"No more songs in queue."

        skipEmbed = discord.Embed(
            title=f"Skipping {currentSongTuple[1]}",
            color=discord.Colour.dark_purple(),
            description=descriptionText
        )

        skipEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        skipEmbed.set_footer(text=f"Skipped by {ctx.author.name}")

        await ctx.send(embed = skipEmbed)
        ctx.voice_client.stop()  # Stopping current song will trigger play_next automatically if there are more songs in the queue
    else:

        noSkipEmbed = discord.Embed(
            title="No Audio Playing",
            color=discord.Colour.dark_purple(),
            description=f"To add a song to the queue, use `/oynat` command."
        )

        noSkipEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        await ctx.send(embed = noSkipEmbed)

@bot.hybrid_command(name='sira', help='Shows the current music queue.')
async def show_queue(ctx):

    queue = bot.get_queue(ctx.guild.id)
    
    if queue:

        first5_queue = queue[:10]

        queueEmbed = discord.Embed(
            title="Current Queue:",
            color=discord.Colour.dark_purple()
        )

        queueEmbed.add_field(name="", value=f"{"\n".join(f"{idx + 1}. {title} --> `Added By : {author}`" for idx, (author,title, _, _, _, _) in enumerate(first5_queue))}", inline=False)
        queueEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        await ctx.send(embed=queueEmbed)
    else:

        noQueueEmbed = discord.Embed(
            title="Queue is Empty",
            color=discord.Colour.dark_purple(),
            description="Add songs to the queue using `/oynat` command."
        )

        noQueueEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        
        bot.firstInQueue = True
        await ctx.send(embed=noQueueEmbed)

@bot.hybrid_command(name='siradan-cikar', help='Removes a specific song from the queue by its position.')
async def remove(ctx, position: int):
    queue = bot.queue.get(ctx.guild.id)
    if len(queue) >= position > 0:  # Ensure the position is within the valid range
        # Remove the song at the specified position (adjust for zero-based index)

        removed_song = queue.pop(position - 1)

        removeQueueEmbed = discord.Embed(
            title=f"Removing Song From Queue",
            color=discord.Colour.dark_purple(),
            description=f"Removed song '{removed_song[1]}' from the queue..."
        )

        removeQueueEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        removeQueueEmbed.add_field(name="New List Prewiew", value=f"{"\n".join(f"{idx + 1}. {title} --> `Added By : {author}`" for idx, (author,title, _, _, _, _) in enumerate(queue[:10]))}", inline=False)
        removeQueueEmbed.set_footer(text=f"Removed by {ctx.author.name}")
        
        await ctx.send(embed=removeQueueEmbed)
    else:

        noRemoveQueueEmbed = discord.Embed(
            title="Invalid Position",
            color=discord.Colour.dark_purple(),
            description="Please enter a valid song number or add songs to queue."
        )

        noRemoveQueueEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        await ctx.send(embed=noRemoveQueueEmbed)


bot.run(TOKEN)
