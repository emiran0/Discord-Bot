import discord
import asyncio

async def disconnect_after_timeout(bot, ctx, timeout):
    await asyncio.sleep(timeout)  # Wait for 3 hours
    guild_id = ctx.guild.id
    voice_client = bot.get_guild(guild_id).voice_client
    if voice_client and (discord.utils.utcnow() - bot.connected_since[guild_id]).total_seconds() >= timeout:
        print(f"Disconnected from {voice_client.channel.name} due to 3 hours limit.")
        await ctx.send("Disconnecting due to 3 hours limit.")
        await voice_client.disconnect()


async def join_channel(ctx, bot):
    if ctx.author.voice is None:
        await ctx.send("You are not connected to a voice channel.")
        return None
    channel = ctx.author.voice.channel
    if ctx.voice_client is not None:
        await ctx.voice_client.move_to(channel)
        return ctx.voice_client
    bot.clear_queue(ctx.guild.id)
    bot.firstInQueue = True
    voice_client = await channel.connect()
    bot.connected_since[ctx.guild.id] = discord.utils.utcnow()  # Store the connection time
    asyncio.create_task(disconnect_after_timeout(bot, ctx, 3 * 3600))  # Schedule disconnect after 3 hours
    return voice_client