import discord
from discord.ext import commands
from discord.ui import Button, View
from discord import FFmpegPCMAudio, File, app_commands, ButtonStyle
import os
import random
from dotenv import load_dotenv
import yt_dlp
import asyncio
from util import join_channel
from fetchLoLData import get_lol_info
import datetime
from wordleGame import get_wordle_guess, get_today_word
from firestore_manager import post_command_data, get_user_wordle_scores, store_user_wordle_score, get_all_user_scores

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

FFMPEG_OPTIONS = {'options': '-vn -sn -dn -ab 64k', 'before_options':'-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5'}
# -ar 48000 -ac 2 
class MusicBot(commands.Bot):

    def __init__(self, command_prefix, intents):
        super().__init__(command_prefix, intents=intents)
        self.connected_since = {}  # Dictionary to track connection time by guild ID
        self.queue = {}
        self.firstInQueue = True
        self.currently_playing = {}
        self.lolUserStatDict = {}
        self.wordleGuesses = {}
        self.worldeEmbeds = {}
        self.nowPlayingEmbedsToDelete = {}

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
    
    def get_server_rankings(self, guild_id):
        if guild_id not in self.lolUserStatDict:
            self.lolUserStatDict[guild_id] = {}
        return self.lolUserStatDict[guild_id]
    
    def get_lol_user_stat(self, guild_id):
        return self.get_server_rankings(guild_id)

    def insert_lol_user_stat(self,guild_id, summoner_name, statDict):
        self.get_server_rankings(guild_id)[summoner_name] = statDict
    
    def remove_lol_user_stat(self, guild_id):
        self.get_server_rankings(guild_id).clear()

class PlaybackControl(View):
    def __init__(self, voice_client, ctx):
        super().__init__()
        self.voice_client = voice_client
        self.ctx = ctx
        self.guild_id = ctx.guild.id

        # Pause button
        self.pause_button = Button(label="Pause", style=ButtonStyle.red, custom_id="pause_button", emoji='⏸️')
        self.pause_button.callback = self.pause_audio
        self.add_item(self.pause_button)

        # Resume button
        self.resume_button = Button(label="Resume", style=ButtonStyle.green, custom_id="resume_button", disabled=True, emoji='▶️')
        self.resume_button.callback = self.resume_audio
        self.add_item(self.resume_button)

        # Next song button
        self.next_button = Button(label="Next Song", style=ButtonStyle.blurple, custom_id="next_song_button", emoji='⏭️')
        self.next_button.callback = self.next_song
        self.add_item(self.next_button)

    async def pause_audio(self, interaction: discord.Interaction):
        if self.voice_client.is_playing():
            self.voice_client.pause()
            self.pause_button.disabled = True
            self.resume_button.disabled = False
            self.next_button.disabled = False
            await interaction.response.edit_message(view=self)

    async def resume_audio(self, interaction: discord.Interaction):
        if self.voice_client.is_paused():
            self.voice_client.resume()
            self.pause_button.disabled = False
            self.resume_button.disabled = True
            self.next_button.disabled = False
            await interaction.response.edit_message(view=self)

    async def next_song(self, interaction: discord.Interaction):
        if self.voice_client.is_playing() or self.voice_client.is_paused():
            self.voice_client.stop()  # This will trigger the 'after' callback which should be play_next
            # Optionally reset all buttons to default states
            self.pause_button.disabled = False
            self.resume_button.disabled = True
            self.next_button.disabled = True
            await interaction.response.edit_message(view=self)
            # The after callback of the voice_client.play() should handle playing the next song


bot = MusicBot(command_prefix='/', intents=discord.Intents.all())

@bot.event
async def on_ready():
    print(f'{bot.user.name} has connected to Discord!')
    await bot.tree.sync()
    # await tree.sync(guild=discord.Object(id=346798764435963904))

@bot.hybrid_command(name='yardim', help='Shows commands list.')
async def help(ctx):

    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("I can only be accessed in a server.")
        return

    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'yardim'
    command_time = datetime.datetime.now()
    inputString = None
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)

    helpEmbed = discord.Embed(
        title="Commands List",
        color=discord.Colour.dark_purple()
    )

    helpEmbed.set_thumbnail(url=bot.user.display_avatar.url)
    helpEmbed.add_field(name="/help", value="Shows commands list.", inline=False)
    helpEmbed.add_field(name="/legend", value="Responds with a legendary music YouTube link.", inline=False)
    helpEmbed.add_field(name="/halifoto", value="Posts a random photo.", inline=False)
    helpEmbed.add_field(name="/lolstat", value="Gives the win rate and KDA of the given summonner name and tag (no hashtags).", inline=False)
    helpEmbed.add_field(name="/lolrank", value="Gives the rankings of previously checked summoner name.", inline=False)
    helpEmbed.add_field(name="/lolrank_clear", value="Removes the stats of all users in the rankings", inline=False)
    helpEmbed.add_field(name="/wordle", value="Starts a new wordle game.", inline=False)
    helpEmbed.add_field(name="/worlde_rankings", value="Shows the rankings of the Wordle game.", inline=False)
    helpEmbed.add_field(name="/katil", value="Bot joins the voice channel.", inline=False)
    helpEmbed.add_field(name="/ayril", value="Bot leaves the voice channel.", inline=False)
    helpEmbed.add_field(name="/oynat", value="Searches and plays music from YouTube.", inline=False)
    helpEmbed.add_field(name="/durdur", value="Pauses the currently playing audio.", inline=False)
    helpEmbed.add_field(name="/devam", value="Resumes the paused audio.", inline=False)
    helpEmbed.add_field(name="/atla", value="Skips the currently playing song.", inline=False)
    helpEmbed.add_field(name="/sira", value="Shows the current music queue.", inline=False)
    helpEmbed.add_field(name="/siradan-cikar", value="Removes a specific song from the queue by its position.", inline=False)


    helpEmbed.set_thumbnail(url=bot.user.display_avatar.url)
    await ctx.send(embed=helpEmbed)

@bot.hybrid_command(name='legend', help='Responds with a legendary music YouTube link.')
async def legend(ctx):

    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("I can only be accessed in a server.")
        return

    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'legend'
    command_time = datetime.datetime.now()
    inputString = None
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)

    response = 'https://youtu.be/cvav25BQ9Ec?si=98AxA8lc4EvhRLKI&t=20'
    await ctx.send(response)

@bot.hybrid_command(name='halifoto', help='Posts a random photo.')
async def halipic(ctx):

    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("I can only be accessed in a server.")
        return

    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'halifoto'
    command_time = datetime.datetime.now()
    inputString = None
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)

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

    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'ayril'
    command_time = datetime.datetime.now()
    inputString = None
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)
    
    if ctx.voice_client:

        await ctx.send("Leaving the voice channel...")
        queue.clear()

        if ctx.guild.id in bot.connected_since:
            del bot.connected_since[ctx.guild.id]  # Clear the tracked time
        
        await ctx.voice_client.disconnect()
    else:

        await ctx.send("I'm not in a voice channel.")

@bot.hybrid_command(name='oynat', help='Searches and joins to channel to plays music from YouTube.')
async def play(ctx, *, search: str):

    if ctx.voice_client is None:
        isFirstSongPlayed = True
    else:
        isFirstSongPlayed = False

    queue = bot.queue.get(ctx.guild.id)
    voice_client = await join_channel(ctx, bot)
    if voice_client is None:
        return

    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'oynat'
    command_time = datetime.datetime.now()
    inputString = search
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)

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
        sec_duration = info['duration'] 
        title = info['title']
        url = info['webpage_url']
        thumbnail = info['thumbnail']

    duration = str(datetime.timedelta(seconds = int(sec_duration)))
        
    songTuple = (author.name, title, url, thumbnail, duration, isFirstSongPlayed, sec_duration)  # Store title and URL as a tuple
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

        await embedMessage.edit(embed=addQueueEmbed, delete_after=10)

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
    guild_id = ctx.guild.id
    
    ydl_opts = {
        'format': 'm4a',
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'm4a',
            'preferredquality': '192k',
        }],
        'quiet': False
    }

    requester, title, song_url, thumbnail_url, vid_duration, isFirstSongPlayed, secDuration = playInfo

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(song_url, download=False)
        url = info['url']

    source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)
    #FFmpegPCMAudio(url, before_options='-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', options='-vn -sn -dn -ar 48000 -ab 64k -ac 2')
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

    
    view = PlaybackControl(ctx.voice_client, ctx)

    if isFirstSongPlayed:

        await embedToEdit.edit(embed=nowPlayingEmbed, view=view, delete_after=int(secDuration))
    else:

        new_msg = await ctx.send(embed=nowPlayingEmbed, view=view)
        if guild_id in bot.nowPlayingEmbedsToDelete:
            old_msg = bot.nowPlayingEmbedsToDelete[guild_id]
            if old_msg:
                try:
                    await old_msg.delete()
                except:
                    pass
        bot.nowPlayingEmbedsToDelete[guild_id] = new_msg

    

@bot.hybrid_command(name='durdur', help='Pauses the currently playing audio.')
async def pause(ctx):

    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'durdur'
    command_time = datetime.datetime.now()
    inputString = None
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)

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
        await ctx.send(embed = pauseEmbed, delete_after=5)
    else:
        noPauseEmbed = discord.Embed(
            title="No Audio Playing",
            color=discord.Colour.dark_purple()
        )

        pauseEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        pauseEmbed.set_footer(text=f"Use `/oynat` to play a song.")

        await ctx.send(embed = noPauseEmbed, delete_after=5)

@bot.hybrid_command(name='devam', help='Resumes the paused audio.')
async def resume(ctx):

    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'devam'
    command_time = datetime.datetime.now()
    inputString = None
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)

    if ctx.voice_client and ctx.voice_client.is_paused():

        currentSongTuple = bot.get_currently_playing(ctx.guild.id)

        resumeEmbed = discord.Embed(
            title=f"Resuming {currentSongTuple[1]}",
            color=discord.Colour.dark_purple(),
            description=f"Song is resumed by `{ctx.author.name}`."
        )

        resumeEmbed.set_thumbnail(url=bot.user.display_avatar.url)

        ctx.voice_client.resume()
        await ctx.send(embed = resumeEmbed, delete_after=5)
    else:

        noResumeEmbed = discord.Embed(
            title="No Audio Paused",
            color=discord.Colour.dark_purple()
        )

        noResumeEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        await ctx.send(embed = noResumeEmbed, delete_after=5)

@bot.hybrid_command(name='atla', help='Skips the currently playing song.')
async def skip(ctx):

    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'atla'
    command_time = datetime.datetime.now()
    inputString = None
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)

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

        await ctx.send(embed = skipEmbed, delete_after=5)
        ctx.voice_client.stop()  # Stopping current song will trigger play_next automatically if there are more songs in the queue
    else:

        noSkipEmbed = discord.Embed(
            title="No Audio Playing",
            color=discord.Colour.dark_purple(),
            description=f"To add a song to the queue, use `/oynat` command."
        )

        noSkipEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        await ctx.send(embed = noSkipEmbed, delete_after=5)

@bot.hybrid_command(name='sira', help='Shows the current music queue.')
async def show_queue(ctx):

    queue = bot.get_queue(ctx.guild.id)

    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'sira'
    command_time = datetime.datetime.now()
    inputString = None
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)
    
    if queue:

        first5_queue = queue[:10]

        queueEmbed = discord.Embed(
            title="Current Queue:",
            color=discord.Colour.dark_purple()
        )

        queueEmbed.add_field(name="", value=f"{"\n".join(f"{idx + 1}. {title} --> `Added By : {author}`" for idx, (author,title, _, _, _, _, _) in enumerate(first5_queue))}", inline=False)
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

        userID = ctx.author.id
        userName = ctx.author.name
        command_string = 'siradan_cikar'
        command_time = datetime.datetime.now()
        inputString = position
        serverID = ctx.guild.id
        serverName = ctx.guild.name
        channelID = ctx.channel.id
        channelName = ctx.channel.name
        await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)

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

@bot.hybrid_command(name='lolstat', help='Gives the win rate and KDA of the given summonner name and tag (no hashtags).')
async def lolstat(ctx, *, summoner_name: str, summoner_tag:str):
    
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("I can only be accessed in a server.")
        return
    
    if '#' in summoner_tag:
        await ctx.send("Please enter the summoner tag without the hashtag.")
        return
    
    input_str = f'{summoner_name}#{summoner_tag}'
    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'lolstat'
    command_time = datetime.datetime.now()
    inputString = input_str
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)

    initalEmbed = discord.Embed(
        title="Fetching LoL Stats...",
        color=discord.Colour.dark_purple(),
        description=f"Fetching LoL stats for `{summoner_name}`..."
    )

    initalEmbed.set_thumbnail(url=bot.user.display_avatar.url)
    initalEmbed.set_footer(text="Please wait...")
    embedMessage = await ctx.send(embed=initalEmbed)

    try:
        statsDict = await get_lol_info(summoner_name, summoner_tag)
    except Exception as e:
        errorEmbed = discord.Embed(
            title="Error Fetching LoL Stats",
            color=discord.Colour.dark_purple(),
            description=f"Fetching LoL stats for `{summoner_name}` failed. Check the summoner name and tag."
        )

        errorEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        errorEmbed.set_footer(text="Please try again after a minute.")
        await embedMessage.edit(embed=errorEmbed)
        return
    
    lolEmbed = discord.Embed(
        title=f"LoL Stats for {summoner_name} #{summoner_tag}",
        color=discord.Colour.dark_purple(),
        description=f"Stats of last 20 matches."
    )

    lolEmbed.set_thumbnail(url=bot.user.display_avatar.url)
    lolEmbed.insert_field_at(1, name="", value=f"> Win Rate: **{statsDict['winRate']}%**", inline=False)
    lolEmbed.insert_field_at(2, name="", value=f"> KDA: **{statsDict['kdaOverAll']}**", inline=False)
    lolEmbed.insert_field_at(3, name="", value=f"> Average Minion: **{statsDict['minionsKilledAverage']}**", inline=False)
    lolEmbed.insert_field_at(4, name="", value=f"> Average Vision Score: **{statsDict['visionScoreAverage']}**", inline=False)
    lolEmbed.insert_field_at(5, name="", value=f"> Popular Pick: **{(statsDict['mostlyPlayedChampion'])}**", inline=False)
    lolEmbed.insert_field_at(6, name="", value=f"> Average Damage Dealt: **{statsDict['averageDamageDealt']}**", inline=False)

    await embedMessage.edit(embed=lolEmbed)

    bot.insert_lol_user_stat(ctx.guild.id, summoner_name, statsDict)

    print(bot.lolUserStatDict)

@bot.hybrid_command(name='lolrank', help='Gives the rankings of previously checked summoner name.')
async def lolrank(ctx):

    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("I can only be accessed in a server.")
        return

    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'lolrank'
    command_time = datetime.datetime.now()
    inputString = None
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)

    allPlayerDict = bot.get_lol_user_stat(ctx.guild.id)

    if not allPlayerDict:
        await ctx.send("No player stats found.")
        return
    
    rankEmbed = discord.Embed(
        title="LoL Stats Rankings",
        color=discord.Colour.dark_purple(),
        description="Rankings of all the players in last 20 games."
    )

    rankEmbed.set_thumbnail(url=bot.user.display_avatar.url)
    rankEmbed.set_footer(text="Rankings are based on win rate.")
    rankList = sorted(allPlayerDict.items(), key=lambda x: x[1]['winRate'], reverse=True)
    print(rankList)
    rankEmbed.add_field(name="", value=f"{'\n'.join(f'**{idx + 1}. {player}** - `Win Rate: {stats["winRate"]}`' for idx, (player, stats) in enumerate(rankList))}", inline=False)

    await ctx.send(embed=rankEmbed)

@bot.hybrid_command(name='lolrank_clear', help='Removes the stats of the given summoner name.')
async def lolrank_clear(ctx):
    
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("I can only be accessed in a server.")
        return

    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'lolrank_clear'
    command_time = datetime.datetime.now()
    inputString = None
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)

    if ctx.guild.id not in bot.lolUserStatDict:
        await ctx.send("No player stats found.")
        return
    
    bot.remove_lol_user_stat(ctx.guild.id)

    removedEmbed = discord.Embed(
        title="LoL Stats Cleared",
        color=discord.Colour.dark_purple(),
        description="All player stats have been removed."
    )

    removedEmbed.set_thumbnail(url=bot.user.display_avatar.url)
    removedEmbed.set_footer(text="Use `/lolstat` to check stats again and add to ranking list.")

    await ctx.send(embed=removedEmbed)

async def wordle_player_time_logic(ctx):

    if ctx.author.name not in bot.wordleGuesses:
        return

    playerInfoDict = bot.wordleGuesses[ctx.author.name]
    if playerInfoDict['playgroundEmbed'] is not None:
        embedHolder = playerInfoDict['playgroundEmbed']
    else:
        embedHolder = None

    if (playerInfoDict['gameStartTime'] + datetime.timedelta(hours=22) <= datetime.datetime.now(datetime.UTC)) and (len(playerInfoDict['playerWords']) >= 1):
        print("Game time has ended.")
        current_score = await get_user_wordle_scores(str(ctx.author.id))
        bot.wordleGuesses[ctx.author.name] = {
            'playerWords': [],
            'playerGuesses': [],
            'playerScore': current_score,
            'gameStartTime': datetime.datetime.now(datetime.UTC),
            'playgroundEmbed': embedHolder,
            'initialChannelId': ctx.channel.id,
            'initialChannelName': ctx.channel.name,
            'initialGuildId': ctx.guild.id,
            'initialGuildName': ctx.guild.name
        }
        return 

    return

@bot.hybrid_command(name='wordle', help='Starts a new wordle game.')
async def wordle(ctx, *, guess: str):

    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("I can only be accessed in a server.")
        return
    
    guessTypeLetterEmojisSource = ['🟥', '🟨', '🟩']
    holderGuessTypeList = []
    isCorrect = False
    isFinished = False

    await wordle_player_time_logic(ctx)

    lastScore = 0

    if ctx.author.name not in bot.wordleGuesses:

        playgroundEmbed = discord.Embed(
        title="Wordle Game",
        color=discord.Colour.dark_purple(),
        description=f"Guess the 5-letter word. \n`{ctx.author.name}` you have **6** guesses to find today's **WORDLE**."
        )
        playgroundToEdit = await ctx.send(embed=playgroundEmbed)

        bot.wordleGuesses[ctx.author.name] = {
            'playerWords': [],
            'playerGuesses': [],
            'playerScore': lastScore,
            'gameStartTime': datetime.datetime.now(datetime.UTC),
            'playgroundEmbed': playgroundToEdit,
            'initialChannelId': ctx.channel.id,
            'initialChannelName': ctx.channel.name,
            'initialGuildId': ctx.guild.id,
            'initialGuildName': ctx.guild.name
        }
        await asyncio.sleep(0.5)
    elif len(bot.wordleGuesses[ctx.author.name]['playerWords']) < 1:

        if bot.wordleGuesses[ctx.author.name]['playgroundEmbed'] is not None:
            try:
                await bot.wordleGuesses[ctx.author.name]['playgroundEmbed'].delete()
            except:
                bot.wordleGuesses[ctx.author.name]['playgroundEmbed'] = None

            print("Deleted the unfinicshedm embed playground.")

        playgroundEmbed = discord.Embed(
        title="Wordle Game",
        color=discord.Colour.dark_purple(),
        description=f"Guess the 5-letter word. \n`{ctx.author.name}` you have **6** guesses to find today's **WORDLE**."
        )
        playgroundToEdit = await ctx.send(embed=playgroundEmbed)

        bot.wordleGuesses[ctx.author.name] = {
            'playerWords': [],
            'playerGuesses': [],
            'playerScore': lastScore,
            'gameStartTime': datetime.datetime.now(datetime.UTC),
            'playgroundEmbed': playgroundToEdit,
            'initialChannelId': ctx.channel.id,
            'initialChannelName': ctx.channel.name,
            'initialGuildId': ctx.guild.id,
            'initialGuildName': ctx.guild.name
        }
        await asyncio.sleep(0.7)
    

    if len(guess) != 5:
        await ctx.send("Please enter a 5-letter word.")
        return
    elif not guess.isalpha():
        await ctx.send("Please enter a word with only alphabetic characters.")
        return
    
    formattedGuess = guess.lower()

    guessDetails = get_wordle_guess(formattedGuess)
    isCorrect = guessDetails['correctGuess']

    if guessDetails['validGuess'] == False:
        await ctx.send("Please enter a valid word.")
        return


    playerInfoDict = bot.wordleGuesses[ctx.author.name]
    holderGuessTypeList = playerInfoDict['playerGuesses']
    holderGuessedWordsList = playerInfoDict['playerWords']
    holderGuessedWordsList.append(formattedGuess)
    holderScore = await get_user_wordle_scores(str(ctx.author.id))

    if holderScore is None:
        holderScore = playerInfoDict['playerScore']

    print(datetime.datetime.now(datetime.UTC))
    
    if len(holderGuessedWordsList) > 6:
        await ctx.send(f"Your Wordle game has ended. Try again tomorrow. Your score is: `{holderScore}`")
        return
    
    correctGuessTypeList = [2, 2, 2, 2, 2]

    if correctGuessTypeList in holderGuessTypeList:
        await ctx.send(f"Your Wordle game has ended. Try again tomorrow. Your score is: `{holderScore}`")
        return

    if ctx.channel.id != playerInfoDict['initialChannelId']:
        if ctx.channel.id != playerInfoDict['initialChannelId']:
            await ctx.send(f"Please play the Wordle game in the same channel where you started the game. The channel you started: `{playerInfoDict['initialChannelName']}`.")
            return
        else:
            await ctx.send(f"Please play the Wordle game in the same server where you started the game. The server you started: `{playerInfoDict['initialGuildName']}` | `#{playerInfoDict['initialChannelName']}`.")
            return
        
    tempList = []

    if isCorrect:

        tempList = correctGuessTypeList
    else:

        for guess in guessDetails['letterGuessTypeId']:
            tempList.append(guess['letterTypeId'])
    
    holderGuessTypeList.append(tempList)
    
    embedMessage = discord.Embed(
        title=f"Wordle Game for {ctx.author.name}",
        color=discord.Colour.dark_purple()
    )

    embedMessage.set_thumbnail(url=bot.user.display_avatar.url)
    embedMessage.set_footer(text="🟥: Incorrect Letter | 🟨: Correct Letter in Wrong Position | 🟩: Correct Letter in Correct Position")
    idx = 0
    for typeList in holderGuessTypeList:
        embedMessage.add_field(name=f"{holderGuessedWordsList[idx]}", value=f"{''.join([guessTypeLetterEmojisSource[guess] for guess in typeList])}", inline=False)
        idx +=1
    
    if len(holderGuessedWordsList) == 6 and (not isCorrect):
        embedMessage.add_field(name="", value=f"Your Wordle game has ended. Todays word was **{get_today_word()}**. \nTry again tomorrow. Your score is: `{holderScore}`", inline=False)
        embedMessage.set_footer(text='THIS MESSAGE WILL BE DELETED IN 10 SECONDS.')
        playerInfoDict['playerScore'] = holderScore
        isFinished = True

    if isCorrect:
        scoreMultiplier = 7 - len(holderGuessedWordsList)
        holderScore += scoreMultiplier
        embedMessage.add_field(name=f"🎉🎉🎉🎉🎉", value=f"Congratulations! You have guessed the word correctly.", inline=False)
        embedMessage.add_field(name="", value=f"Your current score is: `{holderScore}`", inline=False)
        embedMessage.set_footer(text='THIS MESSAGE WILL BE DELETED IN 10 SECONDS.')
        playerInfoDict['playerScore'] = holderScore
        isFinished = True

    if playerInfoDict['playgroundEmbed']:
        embedToDelete = playerInfoDict['playgroundEmbed']
    
    playerInfoDict['playerGuesses'] = holderGuessTypeList
    playerInfoDict['playerWords'] = holderGuessedWordsList
    
    try:
        playerInfoDict['playgroundEmbed'] = await ctx.send(embed=embedMessage)
    except:
        errorEmbed = discord.Embed(
            title="Error in sending the message",
            color=discord.Colour.dark_purple(),
            description="Please try again."
        )
        playerInfoDict['playgroundEmbed'] = await ctx.send(embed=errorEmbed)

    bot.wordleGuesses[ctx.author.name] = playerInfoDict

    if embedToDelete:
        await embedToDelete.delete()
    
    if isFinished:

        playgroundToEdit = playerInfoDict['playgroundEmbed']
        await asyncio.sleep(10)
        await playgroundToEdit.delete()
        playerInfoDict['playgroundEmbed'] = None

        gameEndEmbed = discord.Embed(
            title=f"Wordle Game of `{ctx.author.name}`",
            color=discord.Colour.dark_purple(),
            description=f"Your Wordle game has ended. \nTry again tomorrow. Your score is: `{holderScore}`\n\n**WORDLE Game Preview:**\n"
        )

        gameEndEmbed.set_thumbnail(url=bot.user.display_avatar.url)
        
        for typeList in holderGuessTypeList:
            gameEndEmbed.add_field(name="", value=f"{''.join([guessTypeLetterEmojisSource[guess] for guess in typeList])}", inline=False)

        await ctx.send(embed=gameEndEmbed)
        bot.wordleGuesses[ctx.author.name] = playerInfoDict

        await store_user_wordle_score(str(ctx.author.id), ctx.author.name, holderScore, datetime.datetime.now(datetime.UTC))
    
    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'wordle'
    command_time = datetime.datetime.now(datetime.UTC)
    inputString = formattedGuess
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)
    

@bot.hybrid_command(name='wordle_rankings', help='Shows the Wordle game rankings based on scores from all servers.')
async def wordle_rankings(ctx):
    
    if isinstance(ctx.channel, discord.DMChannel):
        await ctx.send("I can only be accessed in a server.")
        return

    userID = ctx.author.id
    userName = ctx.author.name
    command_string = 'wordle_rankings'
    command_time = datetime.datetime.now()
    inputString = None
    serverID = ctx.guild.id
    serverName = ctx.guild.name
    channelID = ctx.channel.id
    channelName = ctx.channel.name
    await post_command_data(userID, userName, command_string, command_time, inputString, serverID, serverName, channelID, channelName)

    allPlayerList = await get_all_user_scores()
    allPlayerList.remove((None, 0))
    

    if not allPlayerList:
        await ctx.send("No player stats found.")
        return

    rankEmbed = discord.Embed(
        title="Wordle Game Rankings",
        color=discord.Colour.dark_purple(),
        description="Rankings of all the players in Wordle game."
    )

    rankEmbed.set_thumbnail(url=bot.user.display_avatar.url)
    rankEmbed.set_footer(text=f"Score Range: (0-6) per game. Earlier you finish, higher the score.")
    rankList = sorted(allPlayerList, key=lambda x: x[1], reverse=True)
    print(rankList)

    rankEmbed.add_field(name="", value=f"{'\n'.join(f'**{idx + 1}. {player}** - `Score: {score}`' for idx, (player, score) in enumerate(rankList))}", inline=False)

    await ctx.send(embed=rankEmbed)
            

bot.run(TOKEN)
