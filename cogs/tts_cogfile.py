import asyncio
import discord 
from discord.ext import commands
from discord import app_commands
import elevenlabs
from elevenlabs.client import ElevenLabs, AsyncElevenLabs
import random
import os
from dotenv import load_dotenv
import datetime as dt
import io
from discord_servers_cogs import *

# dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

# Load the .env file
load_dotenv()

audio_dir = "./audio"
repeatable_audio = "./repeatable_audio"
os.makedirs(audio_dir, exist_ok=True)
os.makedirs(repeatable_audio, exist_ok=True)

ELEVENLABS_API_KEY = os.getenv('ELEVENLABS_API_KEY')
FFMPEG_PATH = os.getenv('FFMPEG_PATH')

guilds_list = all_discord_servers


class tts_cog(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot = bot

        self.client = AsyncElevenLabs(api_key=ELEVENLABS_API_KEY)
        # self.source = discord.FFmpegPCMAudio()


    async def play_tts(self, voice, source):
        resume_after = False

        if voice.is_playing():
            voice.pause()
            resume_after = True

        voice.play(source)
        while voice.is_playing():
            await asyncio.sleep(2)

        if resume_after and voice.is_paused():
            voice.resume()


    @commands.command(name="say", aliases=["speak", "talk"], description="Say what you wrote as tts.") 
    async def say(self, ctx:commands.Context, *, text:str) -> None:
        """
        |coroutine| Say what you wrote as tts (text-to-speech). Automatically save the speeches as .mp3 files in audio file.
        By specifying 'save: ' at the start of the sentence, you can choose to save the speech in the repeatable_audio file.
        \n
        e.g:
        \n
        /say {your sentence}

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
            text (str): Your sentece for tts.
        """
        try: # Check if you are connected to voice channel.
            voice_channel = ctx.author.voice.channel
        except AttributeError as e:
            print(e)
            await ctx.send(embed= discord.Embed(title='You are not connected to a voice channel.', color=discord.Color.blurple()))

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        try:
            if not voice: 
                await voice_channel.connect()
                voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        except Exception as e:
            # print(e)
            pass

        await ctx.message.delete()

        current_datetime = dt.datetime.now().strftime('%d-%m-%Y_%H%M%S')
        author_name = ctx.message.author.name

        if text[:6].lower()=='save: ':
            text_to_save = text[6:]
            audio = await self.client.generate(text=text_to_save, voice="Sarah", model="eleven_multilingual_v2")
            save_name = '_'.join(text_to_save.split(' ')[:4]) # Takes the first 4 words seperated by space, list them and join them with _ for the filename
            filename = f"{save_name}.mp3"
            filepath = os.path.join(repeatable_audio, filename)
        else:
            audio = await self.client.generate(text=text, voice="Sarah", model="eleven_multilingual_v2")
            filename = f"{author_name}_{current_datetime}.mp3"
            filepath = os.path.join(audio_dir, filename)

        output = io.BytesIO()
        async for value in audio:
            if value:
                output.write(value)
        output.seek(0)
        
        elevenlabs.save(output, filepath)

        source = discord.FFmpegPCMAudio(executable=FFMPEG_PATH, source=filepath)

        voice.play(source)
        while voice.is_playing():
            await asyncio.sleep(2)



    @commands.command(name="motivation", aliases=["dor", "mot"], description="Say motivational quotes to your friends.") 
    async def motivation(self, ctx:commands.Context) -> None:
        """
        |coroutine| Say motivational quotes to your friends. Uses a random saved .mp3 files from repeatable_audio file.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        try: # Check if you are connected to voice channel.
            voice_channel = ctx.author.voice.channel
        except AttributeError as e:
            print(e)
            await ctx.send(embed= discord.Embed(title='You are not connected to a voice channel.', color=discord.Color.blurple()))

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        try:
            if not voice: 
                await voice_channel.connect()
                voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        except Exception as e:
            # print(e)
            pass

        await ctx.message.delete()

        
        # Creates a list of all the available audio files with .mp3 from repeatable_audio file.
        audiofile_names = []
        for filename in os.listdir(repeatable_audio):
            if filename.endswith('.mp3'):
                audiofile_names.append(filename) # Appends only the files with .mp3
            
        filepath = os.path.join(audio_dir, random.choice(audiofile_names))

        source = discord.FFmpegPCMAudio(executable=FFMPEG_PATH, source=filepath)

        voice.play(source)
        while voice.is_playing():
            await asyncio.sleep(2)


async def setup(bot):
    await bot.add_cog(tts_cog(bot), guilds=guilds_list) 
