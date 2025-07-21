
import asyncio
import discord 
from discord.ext import commands, tasks
from discord import app_commands
import yt_dlp
import os
import sqlite3
import datetime as dt
from dotenv import load_dotenv

from cogs.utilities import *
from discord_servers_cogs import *


# Load the .env file
load_dotenv()

FFMPEG_PATH = os.getenv('FFMPEG_PATH')
ADMIN_ID = os.getenv('ADMIN_ID')


guilds_list = all_discord_servers

PLAYLIST_DB_FILE = "data/playlists.db"


class music_cog(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot = bot
        
        # Desiered options for youtube videos 
        self.YTDLP_OPTIONS = {'format': 'bestaudio/best', 'noplaylist': 'True'}

        # Reconnect ffmpeg in case of disconnection.
        self.FFMPEG_OPTIONS = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}

        # Connect to youtube
        self.ytdlp = yt_dlp.YoutubeDL(self.YTDLP_OPTIONS)

        # To append all the available sessions
        self.all_sessions = []

        # Auto disconnect
        self.last_active = {}
        self.auto_disconnect.start()


    def check_session(self, ctx:commands.Context) -> Session:
        """
        Checks if there is a session for the guild and channel the user is currently in.
        If not exists, create one.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.

        Returns:
            Session: Custom object that handle queues. Cant handle multiple servers, each with it's own Session.
        """
        if len(self.all_sessions) > 0:
            for ses in self.all_sessions:
                if (ses.guild == ctx.guild) and (ses.channel == ctx.author.voice.channel):
                    return ses
        session = Session(ctx.guild, ctx.author.voice.channel, id=len(self.all_sessions))
        self.all_sessions.append(session)
        return session


    def coroutine_function(self, ctx:commands.Context) -> None:
        """
        Prepare the coroutine for lambda functions to keep the queue in the event loop.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        prep = asyncio.run_coroutine_threadsafe(self.continue_queue(ctx), self.bot.loop)
        try:
            prep.result()
        except Exception as e:
            print(e)


    async def continue_queue(self, ctx:commands.Context) -> None:
        """
        |coroutine| Check if there is a next element in queue then proceeds to play it in queue.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        
        session = self.check_session(ctx)

        if not session.q.is_next_available():
           session.q.clear_queue()
           await ctx.send(embed=discord.Embed(title='The queue is over...', color=discord.Color.blurple()))
           return

        session.q.next()

        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)

        if not os.path.exists(FFMPEG_PATH):
            await ctx.send(embed=discord.Embed(title='FFmpeg not found. Check your installation.', color=discord.Color.blurple()))
            return

        source = discord.FFmpegOpusAudio(session.q.current_audio['url'], executable=FFMPEG_PATH ,**self.FFMPEG_OPTIONS)

        if voice.is_playing(): # Continue to the next element in the queue
            voice.stop()

        voice.play(source, after=lambda e: self.coroutine_function(ctx))
        self.last_active[ctx.guild.id] = dt.datetime.now()

        current_title = session.q.current_audio['title']
        # current_url = session.q.current_audio['url'] # Currently this is not needed, the url changes often.
        current_thumb = session.q.current_audio['thumb']
        current_duration = session.q.current_audio['duration']
        hours_minutes_seconds = str(dt.timedelta(seconds=current_duration))

        # embed = discord.Embed(title='Now playing:', description=f'{current_title}  -  {current_duration//60}:{current_duration%60}', color=discord.Color.blurple())
        embed = discord.Embed(title='Now playing:', description=f'{current_title}  -  {hours_minutes_seconds}', color=discord.Color.blurple())
        embed.set_thumbnail(url=current_thumb)
        await ctx.send(embed=embed)

    

    # Create a play slash command. /play, aliases=["p","playing"]
    # @app_commands.command(name="play", description="Plays a selected audio from youtube.")
    # @app_commands.command()
    # @app_commands.describe(arg='Name of the audio you want to search')
    @commands.command(name="play", aliases=["p","playing"], description="Plays a selected audio from youtube.")
    async def play(self, ctx:commands.Context, *, arg:str, is_playlist=False) -> None:
        """
        |coroutine| Look at the author's command and check if the author is in voice channel. If so, search for the given title of the audio in youtube
        and add it to the queue, then joins the author's voice channel and start playing the audio from youtube (without downloading it).
        \n
        e.g:
        \n
        /play {arg} (title or link)

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
            arg (str): The title of the audio to be searched in youtube. Can be a link as well.
            is_playlist (bool, optional): True if used in the playlist function, False otherwise.
        """
        await ctx.typing()
        try: # Check if you are connected to a voice channel before playing.
            voice_channel = ctx.author.voice.channel
        except AttributeError as e:
            print(e)
            await ctx.send(embed= discord.Embed(title='You are not connected to a voice channel.', color=discord.Color.blurple()))
        
        session = self.check_session(ctx)
        
        
        # Searches for the video
        with yt_dlp.YoutubeDL(self.YTDLP_OPTIONS) as ytdlp:
            try:
                info = ytdlp.extract_info(arg, download=False)
            except Exception as e:
                print(e)
                print('BOO')
                info = ytdlp.extract_info(f"ytsearch:{arg}", download=False)['entries'][0]
            
        # print(info)
        title = info['title']
        # url = info['formats'][0]['url'] # Old format
        url = info["url"]
        thumb = info['thumbnails'][0]['url']
        video_id = info['id']
        # print(video_id)
        try:
            duration = info['duration']
        except Exception as e:
            print(f'from play: duration unavailable')
            duration = 0
        # print(duration)

        # Add the audio to the queue
        session.q.append_to_queue(title, url, thumb, duration, video_id)

        if not os.path.exists(FFMPEG_PATH):
            await ctx.send(embed= discord.Embed(title='FFmpeg not found. Check your installation.', color=discord.Color.blurple()))
            return


        # Look for an available voice client for the bot where the author is and join in.
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        try:
            if not voice: # or (voice is None):
                await voice_channel.connect()
                voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        except Exception as e:
            # print(e)
            pass

        if (voice.is_playing() or voice.is_paused()):
            if is_playlist: # Only for playlist functionallity 
                print('from play: An item is added to the queue via a playlist.')
                return
            else:
                embed = discord.Embed(title='Added to queue', description=f'{title} - {duration//60}:{duration%60}', color=discord.Color.blurple()) # description=title
                embed.set_thumbnail(url=thumb)
                await ctx.send(embed=embed)
                return
        
        # Only for playlist functionallity 
        if is_playlist: 
            print('from play: An item is added to the queue via a playlist.')
            return


        embed = discord.Embed(title='Now playing', description=f'{title} - {duration//60}:{duration%60}', color=discord.Color.blurple()) # description=title
        embed.set_thumbnail(url=thumb)
        await ctx.send(embed=embed)

        # Guarantees that the requested title is the current title.
        session.q.set_current()
        source = discord.FFmpegOpusAudio(session.q.current_audio['url'], executable=FFMPEG_PATH ,**self.FFMPEG_OPTIONS)
        voice.play(source, after=lambda e: self.coroutine_function(ctx))
        self.last_active[ctx.guild.id] = dt.datetime.now()

        

    # Create a skip slash command, works only if there is something to skip. /skip, aliases=["s"]
    # @app_commands.command(name="skip", description="Skips the current audio being played.")
    @commands.command(name="skip", aliases=["s"], description="Skips the current audio being played.")
    async def skip(self, ctx:commands.Context) -> None:
        """
        |coroutine| If there is a queue in the current session and more than one element in it, skips to the next one in the queue.
  
        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        try:
            if voice is None:
                await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human trying to skip...",color=discord.Color.blurple()))
                return
        except TypeError:
            pass

        if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
            if not session.q.is_next_available():
                await ctx.send(embed=discord.Embed(title='There is nothing in the queue to skip to.', color=discord.Color.blurple()))
                return
            elif voice.is_playing():
                await ctx.send(embed= discord.Embed(title='Skipping...', color=discord.Color.blurple()))
                voice.stop()
                return
            else:
                session.q.set_current()
                source = discord.FFmpegOpusAudio(session.q.current_audio['url'], executable=FFMPEG_PATH ,**self.FFMPEG_OPTIONS)
                voice.play(source, after=lambda e: self.coroutine_function(ctx))
                await ctx.send(embed= discord.Embed(title='Here you go!', color=discord.Color.blurple()))
                return
        else:
            await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human trying to skip....",color=discord.Color.blurple()))



    @commands.command(name="findq", aliases=["fq"], description="Find if there is a queue and play it.")
    async def findq(self, ctx:commands.Context) -> None:
        """
        |coroutine| Look for a queue in the current session and play it. Mostly for testing, unnecessary for traditional usage.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)

        try:
            if not voice:
                await ctx.author.voice.channel.connect()
                voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
                await ctx.send(embed=discord.Embed(title='Connected to voice channel.', color=discord.Color.blurple()))
        except Exception as e:
            print(f'findq error: {e}')
            pass
        
        if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
            if voice.is_playing() or voice.is_paused():
                print('from findq: is_playing')
                return
            elif session.q.is_next_available():
                session.q.set_current()
                source = discord.FFmpegOpusAudio(session.q.current_audio['url'], executable=FFMPEG_PATH ,**self.FFMPEG_OPTIONS)
                voice.play(source, after=lambda e: self.coroutine_function(ctx))
                await ctx.send(embed= discord.Embed(title='Here you go!', color=discord.Color.blurple()))
            else:
                await ctx.send(embed=discord.Embed(title='There is nothing in the queue.', color=discord.Color.blurple()))
        else:
            await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human trying to find....",color=discord.Color.blurple()))



    # Create a pause command, works only if there is something to pause. /pause
    # @app_commands.command(name="pause", description="Pauses the current audio being played")
    @commands.command(name="pause", description="Pauses the current audio being played.") 
    async def pause(self, ctx:commands.Context) -> None:
        """
        |coroutine| If there is an audio playing, pause it.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        try:
            if voice is None:
                await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human trying to pause...",color=discord.Color.blurple()))
                return
        except TypeError:
            pass

        if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
            if voice.is_playing():
                await ctx.send(embed=discord.Embed(title='Pausing...', color=discord.Color.blurple()))
                voice.pause()
            else:
                await ctx.send(embed=discord.Embed(title='Nothing is playing right now.', color=discord.Color.blurple()))
        else:
            await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human trying to pause....",color=discord.Color.blurple()))



    # Create a resume command, works only if there is something to resume (after a pause). /resume, aliases=["r"]
    # @app_commands.command(name="resume", description="Resumes the current audio.")
    @commands.command(name="resume", aliases=["r"], description="Resumes the current audio.")
    async def resume(self, ctx:commands.Context) -> None:
        """
        |coroutine| Resumes the current audio if paused.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
        try:
            if voice in None:
                await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human trying to resume to...",color=discord.Color.blurple()))
                return
        except TypeError:
            pass

        if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
            if voice.is_paused():
                await ctx.send(embed=discord.Embed(title='Resuming...', color=discord.Color.blurple()))
                voice.resume()
            else:
                await ctx.send(embed=discord.Embed(title='Audio is already played.', color=discord.Color.blurple()))
        else:
            await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human trying to resume to....",color=discord.Color.blurple()))



    # Create a stop command, clear queue. /stop, aliases=["sp"]
    # @app_commands.command(name="stop", description="Stops playing audio and clears the session queue.")
    @commands.command(name="stop", aliases=["sp"], description="Stops playing the current audio and clears the session queue.")
    async def stop(self, ctx:commands.Context) -> None:
        """
        |coroutine| Stops playing the current audio and clears the session queue.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        try:
            if voice is None:
                await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human trying to stop...",color=discord.Color.blurple()))
                return
        except TypeError:
            pass

        if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
            if voice.is_playing():
                await ctx.send(embed=discord.Embed(title='Stopping, queue is cleared.', color=discord.Color.blurple()))
                voice.stop()
                session.q.clear_queue()
            else:
                await ctx.send(embed=discord.Embed(title='There is nothing playing.', color=discord.Color.blurple()))
        else:
            await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human trying to stop....",color=discord.Color.blurple()))



    # Create a queue command to show the queue. /queue, aliases=["q"]
    # @app_commands.command(name="queue", description="Displays the current elements in queue")
    @commands.command(name="queue", aliases=["q"], description="Displays the current elements in the queue.")
    async def queue(self, ctx:commands.Context) -> None:
        """
        |coroutine| Displays the current elements in the server queue.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        try:
            if voice is None:
                await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="Why this human try see the queue...",color=discord.Color.blurple()))
                return
        except TypeError:
            pass

        if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
            try:
                current_title = session.q.current_audio['title']
                # current_url = session.q.current_audio['url'] # Currently this is not needed, the url changes often.
                current_thumb = session.q.current_audio['thumb']
                current_duration = session.q.current_audio['duration']
            except TypeError as e:
                print(f'from queue: {e}')
                await ctx.send(embed=discord.Embed(title='There is no session in your voice channel, so there is no queue.', color=discord.Color.blurple()))
                return

            if len(session.q.queue) > 1:
                queue_description_list = []
                counter = 1
                for audio in session.q.queue[1:]:
                    audio_duration = audio['duration']
                    audio_hms = str(dt.timedelta(seconds=audio_duration))
                    # queue_description_list.append(f'{counter}. {audio['title']} - {audio['duration']//60}:{audio['duration']%60} \n')
                    queue_description_list.append(f'{counter}. {audio['title']} - {audio_hms} \n')
                    counter += 1
                counter = 0
                queue_description = ''.join(queue_description_list)

            else:
                queue_description = 'No queue left'
            
            embed = discord.Embed(title='Currently Playing', description=f'{current_title} - {current_duration//60}:{current_duration%60}', color=discord.Color.blurple())
            embed.set_thumbnail(url=current_thumb)
            embed.add_field(name='Queue List:', value=queue_description, inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="Why this human try see the queue....",color=discord.Color.blurple()))



    @commands.command(name="shuffle_queue", aliases=["sq", "shuffle", "shuffleq"], description="Shuffles the current queue.")
    async def shuffle(self, ctx:commands.Context) -> None:
        """
        |coroutine| Shuffles the current server queue.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        try:
            if voice is None:
                await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human try to shuffle...",color=discord.Color.blurple()))
                return
        except TypeError:
            pass

        if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
            if session.q.is_next_available():
                session.q.shuffle_queue()
                await ctx.send(embed= discord.Embed(title="All done!", description="Lets take a look at the new queue.",color=discord.Color.blurple()))
                await self.queue(ctx)
            else:
                await ctx.send(embed= discord.Embed(title="There is nothing to shuffle in the queue...",color=discord.Color.blurple()))
         
        else:
            await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human try to shuffle....",color=discord.Color.blurple()))


    # Create a delete command, works only if there is something to delete from a queue. /delete, aliases=["del"]
    # @app_commands.command(name="delete", description="Delete an element from the queue by calling the number of order in the queue.")
    @commands.command(name="delete", aliases=["del"], description="Delete an element from the queue by calling the number of order in the queue.") #, guild=TEST_SERVER_ID)
    async def delete(self, ctx:commands.Context, number:int) -> None:
        """
        |coroutine| Delete an element from the server queue by calling its queue number.
        \n
        e.g:
        \n 
        /delete {number} (delete element {number} from the queue)

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
            number (int): Queue number.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        try:
            if voice is None:
                await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human trying to delete...",color=discord.Color.blurple()))
                return
        except TypeError:
            pass

        if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
            if session.q.is_next_available():
                index = number
                try:               
                    await ctx.send(embed=discord.Embed(title=f'{session.q.queue[index]['title']} in position {index} in the queue is deleted.', description='Here is the new queue:', color=discord.Color.blurple()))
                    session.q.queue.pop(index)
                    await self.queue(ctx)
                except IndexError as e:
                    await ctx.send(embed=discord.Embed(title=f'There is no {index} items in the queue, please try using an index from the queue.', color=discord.Color.blurple()))
                    await self.queue(ctx)
                except Exception as e:
                    print(e)
            else:
                await ctx.send(embed=discord.Embed(title='There is no queue.', color=discord.Color.blurple()))
        else:
            await ctx.send(embed= discord.Embed(title="I am not connected to a voice channel, so I am not playing anything...", description="What is this human trying to delete....",color=discord.Color.blurple()))



    # Create a disconnect command to remove bot from voice channel, /disconnect. aliases=["dc"]
    # @app_commands.command(name="dc", description="Disconnect the bot from voice channel.")
    @commands.command(name="disconnect", aliases=["dc"], description="Disconnect the bot from voice channel.")
    async def disconnect(self, ctx:commands.Context) -> None:
        """
        |coroutine| Stop playing audio, clear the queue and disconnect the bot from voice channel.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        try:
            if voice is None:
                await ctx.send(embed=discord.Embed(title='I am not connected to a voice channel...', description='-50 Social Credit for trying.', color=discord.Color.blurple()))
                return
        except TypeError:
            pass

        if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
            session.q.clear_queue()
            voice.stop()
            # await self.stop(ctx)
            await voice.disconnect()
            await ctx.send(embed=discord.Embed(title='-10 Social Credit', color=discord.Color.blurple()))
        else:
            await ctx.send(embed=discord.Embed(title='I am not connected to a voice channel...', description='-50 Social Credit for trying..', color=discord.Color.blurple()))

    

    @commands.command(name="connect", aliases=["cn"], description="Connect the bot to the admin voice channel. Admin only.")
    async def connect(self, ctx:commands.Context) -> None:
        """
        |coroutine| Connect the bot to the admin voice channel. Admin only.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        if ctx.author.id == int(ADMIN_ID):
            voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
            try:
                if not voice or (voice in None):
                    await ctx.author.voice.channel.connect()
                    voice = discord.utils.get(self.bot.voice_clients, guild=ctx.guild)
                    await ctx.send(embed=discord.Embed(title='Connected to voice channel', description='+20 Social Credit',color=discord.Color.blurple()))
                    # self.last_active[ctx.guild.id] = dt.datetime.now() # Because this command is mostly for testing, you do not need a timer for disconnection (but you can if you want to...).
            except Exception as e:
                print(f'connect error: {e}')
                pass
        else:
            await ctx.send(embed=discord.Embed(title='Only my admin can connect me to voice channel with that command.', description='+10 Social Credit for trying <3',color=discord.Color.blurple()))



    @commands.command(name="repeat", aliases=["re"], description="Repeat an element from the queue using the position in queue. If no number is given, repeat the currently playing audio.")
    async def repeat(self, ctx:commands.Context, index=0) -> None:
        """
        |coroutine| Repeat an element from the queue using the position in queue. If no number is given, repeat the currently playing audio.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
            index (int, optional): The index of an element from the queue to be repeated. Defaults to 0.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        try:
            if voice is None:
                await ctx.send(embed=discord.Embed(title='I am not connected to a voice channel...', description='Try playing something before using this commad.', color=discord.Color.blurple()))
                return
        except TypeError:
            pass

        if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
            if session.q.queue: # If there is a queue
                try:
                    repeated_object = session.q.queue[index]
                    session.q.queue.append(repeated_object)
                    await ctx.send(embed=discord.Embed(title=f'{repeated_object['title']} is added to the queue (again).', color=discord.Color.blurple()))
                except IndexError as e:
                    await ctx.send(embed=discord.Embed(title=f'There is no {index} items in the queue, please try using an index in the queue.', color=discord.Color.blurple()))
                    await self.queue(ctx)
            else:
                await ctx.send(embed=discord.Embed(title='There is no queue.', color=discord.Color.blurple()))
        else:
            await ctx.send(embed=discord.Embed(title='I am not connected to a voice channel...', description='Try playing something before using this commad..', color=discord.Color.blurple()))


    # Auto disconnect when not playing anything after 15 minutes
    @tasks.loop(minutes=1)
    async def auto_disconnect(self):
        now = dt.datetime.now()
        for voice in self.bot.voice_clients:
            guild_id = voice.guild.id
            last = self.last_active.get(guild_id)

            if voice.is_connected() and not voice.is_playing() and not voice.is_paused():
                if last and (now - last).total_seconds() > 900: # 900 seconds = 15 minutes
                    try:
                        await voice.disconnect()
                        self.last_active.pop(guild_id, None)
                        print(f'Disconnected from {voice.guild.name} due to inactivity.')
                    except Exception as e:
                        print(f'Error disconnecting from {voice.guild.name}: {e}')
                    


    @commands.command(name="create_playlist", aliases=["clist"], description="Create a playlist (minimum 3 elements in queue)")
    async def create_playlist(self, ctx:commands.Context, *, playlist_name:str) -> None:
        """
        |coroutine| Create a playlist from all the elements in the current queue (minimum 3 elements) and save it in a database.
        If the database not exists, create one.
        \n
        e.g:
        \n
        /clist {playlist_name} (Create only if the queue has more than 3 elements)

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
            playlist_name (str): Playlist name.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        try:
            if voice is None:
                await ctx.send(embed=discord.Embed(title='I am not connected to a voice channel, so there is no queue to save as a playlist', description='What is this human trying to create...', color=discord.Color.blurple()))
                return
        except TypeError:
            pass

        if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
            user_id = ctx.author.id
            minimum_requirment = 3
            if len(session.q.queue) >= minimum_requirment:
                try: # Create playlist table in the database
                    with sqlite3.connect(PLAYLIST_DB_FILE) as connection:
                        print('Connected to playlists.db (create)')
                        # Create a cursor object
                        cursor = connection.cursor()

                        # Create a table with the given name (if not exists)
                        cursor.execute(f"""
                            CREATE TABLE IF NOT EXISTS {playlist_name} (
                                id INTEGER PRIMARY KEY AUTOINCREMENT,
                                user_id INTEGER,
                                audio_title TEXT,
                                audio_url TEXT,
                                audio_thumb TEXT,
                                audio_id TEXT
                            )
                        """)

                        # Insert a record into the new table
                        insert_query = f""" 
                                            INSERT INTO {playlist_name} (user_id, audio_title, audio_url, audio_thumb, audio_id) 
                                            VALUES (?, ?, ?, ?, ?);
                                            """
                        playlist_data = [(user_id, audio['title'], audio['url'], audio['thumb'], audio['video_id']) for audio in session.q.queue]

                        # Execute the query for multiple records and commiting it
                        cursor.executemany(insert_query, playlist_data)
                        connection.commit()
                    print('Disconnected from playlists.db (create) \n')
                except Exception as e:
                    print(f'from create_playlist: {e}')
                    await ctx.send(embed=discord.Embed(title='There is a problem creating your playlist', color=discord.Color.blurple()))
                    return
                await ctx.send(embed=discord.Embed(title=f'Your playlist {playlist_name} has been created!', description='...',color=discord.Color.blurple()))
            else:
                await ctx.send(embed=discord.Embed(title=f'You need at least 3 items in the queue to create a playlist', description=f'You need to add {minimum_requirment-len(session.q.queue)} more items to the queue',color=discord.Color.blurple()))
        else:
            await ctx.send(embed=discord.Embed(title='I am not connected to a voice channel, so there is no queue to save as a playlist', description='What is this human trying to create....', color=discord.Color.blurple()))



    @commands.command(name="load_playlist", aliases=["llist"], description="Load a playlist to the queue.")
    async def load_playlist(self, ctx:commands.Context, *, playlist_name:str) -> None:
        """
        |coroutine| Load an existing playlist from the database and add it to the queue.
        \n
        e.g:
        \n
        /llist {playlist_name} (Only existing playlists)

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
            playlist_name (str): Playlist name.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        try:
            if not voice:
                await ctx.author.voice.channel.connect()
                voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        except Exception as e:
            # print(e)
            pass

        if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
            try:
                with sqlite3.connect(PLAYLIST_DB_FILE) as connection:
                    print('Connected to playlists.db (load)')
                    # Create a cursor object
                    cursor = connection.cursor()

                    # Write the SQL command to select all records from the given playlist table
                    select_query = f"SELECT * FROM {playlist_name};"

                    # Execute the SQL command
                    cursor.execute(select_query)

                    # Fetch all records as a list of tuples
                    all_items = cursor.fetchall()

                print('Disconnected from playlists.db (load) \n')
            except Exception as e:
                print(f'from load_playlist: {e}')
                await ctx.send(embed=discord.Embed(title=f'There is a problem loading your playlist.', color=discord.Color.blurple()))
                return

            await ctx.send(embed=discord.Embed(title=f'Adding {playlist_name} playlist to the queue', description='It might take a few seconds to load, please avoid commands if possible.', color=discord.Color.blurple()))
            # Add all the records to the queue, #### The url is not valid, only the title matters
            await ctx.typing()
            for item in all_items:
                item_title = item[2]
                # item_url = item[3]
                # item_thumb = item[4]
                item_id = item[5]
                url_search = f'https://www.youtube.com/watch?v={item_id}'
                # await self.play(ctx, is_playlist=True ,arg=item_title) ######### need to add a parameter for queue message only for this
                await self.play(ctx, is_playlist=True ,arg=url_search)
                if item == all_items[1]: # Play the first item in the playlist while loading the others to the queue
                    print(f'from load_playlist: first item loaded')
                    print(f'from load_playlist: is next available - {session.q.is_next_available()}')
                    await self.findq(ctx)
                await asyncio.sleep(1) ## Testing to slow the requests from the loop (to the loop...)
                
            print(f'all items from {playlist_name} were added to the queue from load_playlist command.')  
            await ctx.typing()
            await ctx.send(embed=discord.Embed(title=f'{playlist_name} playlist is in the queue!', color=discord.Color.blurple()))
            await self.findq(ctx)
        else:
            await ctx.send(embed=discord.Embed(title='I am not connected to a voice channel, so you can not load the playlist', description='What is this human trying to load...', color=discord.Color.blurple()))



    @commands.command(name="show_playlists", aliases=["slists"], description="Show all the playlists in the database.")
    async def show_playlists(self, ctx:commands.Context) -> None:
        """
        |coroutine| Show all the playlists in the database.

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        try:
            with sqlite3.connect(PLAYLIST_DB_FILE) as connection:
                print('Connected to playlists.db (show)')
                # Create a cursor object
                cursor = connection.cursor()
                
                sql_query = """
                            SELECT name FROM sqlite_master  
                            WHERE type='table';
                            """
                
                # Execute the SQL command
                cursor.execute(sql_query)

                # Fetch all tables
                all_tables = cursor.fetchall()

                if len(all_tables) == 0:
                    await ctx.send(embed=discord.Embed(title='There are no playlists in the database.', description='Try to create one before using this command.', color=discord.Color.blurple()))
                    return  
                
                tables_description_list = []
                counter = 1

                for table in all_tables:
                    if table[0] != 'sqlite_sequence':
                        tables_description_list.append(f'{counter}. {table[0]} \n')
                        counter +=1
                counter = 0
                tables_description = ''.join(tables_description_list)

                embed = discord.Embed(title='Here are all the playlists:', description=tables_description, color=discord.Color.blurple())
                await ctx.send(embed=embed)
            print('Disconnected from playlists.db (show) \n')
        except Exception as e:
            print(f'from show_playlists: {e}')
            await ctx.send(embed=discord.Embed(title=f'There is a problem loading your playlist.', color=discord.Color.blurple()))

    

    @commands.command(name="detail_playlists", aliases=["dlist"], description="Show all the items in a given playlist.")
    async def detail_playlist(self, ctx:commands.Context, *, playlist_name:str) -> None:
        """
        |coroutine| Show all the items in a given playlist.
        \n
        e.g:
        \n
        /dlist {playlist_name} (Only existing playlists)

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
            playlist_name (str): Playlist name.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        # try:
        #     if voice is None:
        #         await ctx.send(embed=discord.Embed(title='I am not connected to a voice channel, so you can not load the playlist', description='What is this human trying to load...', color=discord.Color.blurple()))
        #         return
        # except TypeError:
        #     pass

        # if voice.is_connected() and (voice.channel.id == ctx.author.voice.channel.id):
        try:
            with sqlite3.connect(PLAYLIST_DB_FILE) as connection:
                print('Connected to playlists.db (detail)')
                # Create a cursor object
                cursor = connection.cursor()

                # Write the SQL command to select all records from the given playlist table
                select_query = f"SELECT * FROM {playlist_name};"

                # Execute the SQL command
                cursor.execute(select_query)

                # Fetch all records
                all_items = cursor.fetchall()

                items_description_list = []
                counter = 1
                
                # Add all the records to the queue
                for item in all_items:
                    item_title = item[2]
                    items_description_list.append(f'{counter}. {item_title} \n')
                    counter += 1
                counter = 0
                items_description = ''.join(items_description_list)

                embed = discord.Embed(title=f'Here are all the items in {playlist_name} playlist:', description=items_description, color=discord.Color.blurple())
                await ctx.send(embed=embed)   
            print('Disconnected from playlists.db (detail) \n')
        except Exception as e:
            print(f'from detail_playlist: {e}')
            await ctx.send(embed=discord.Embed(title=f'There is a problem loading your playlist.', color=discord.Color.blurple()))


    @commands.command(name="delete_playlists", aliases=["dellist"], description="Delete a playlist from the database. Admin only.") 
    async def delete_playlist(self, ctx:commands.Context, *, playlist_name:str) -> None:
        """
        |coroutine| Delete a playlist from the database. Only the admin can delete playlists.
        \n
         e.g:
        \n
        /dellist {playlist_name} (Only existing playlists)

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
            playlist_name (str): Playlist name.
        """
        session = self.check_session(ctx)
        voice = discord.utils.get(self.bot.voice_clients, guild=session.guild)
        if ctx.author.id == int(ADMIN_ID):
            try:
                with sqlite3.connect(PLAYLIST_DB_FILE) as connection:
                    print('Connected to playlists.db (delete)')
                    # Create a cursor object
                    cursor = connection.cursor()

                    # SQL command to delete a playlist
                    delete_query = f'DROP TABLE {playlist_name}'
                    
                    # Execute the SQL command
                    cursor.execute(delete_query)

                    # Commit the changes to save the deletion
                    connection.commit()
                    print(f'{playlist_name} is deleted from the database.')
                print('Disconnected from playlists.db (delete) \n')
                await ctx.send(embed=discord.Embed(title=f'{playlist_name} is deleted from the database.', description=f'Was the playlist that bad?', color=discord.Color.blurple()))
            except FileNotFoundError as e:
                print(e)
                await ctx.send(embed=discord.Embed(title=f'{playlist_name} does not exists in the database.', description=f'Please use /show_lists (/slists) to see all the playlists in the database.', color=discord.Color.blurple()))
            except Exception as e:
                print(f'from delete_playlist: {e}')
                await ctx.send(embed=discord.Embed(title=f'There is a problem deleting your playlist.', color=discord.Color.blurple()))

        else:
            await ctx.send(embed=discord.Embed(title=f'Only my admin can delete playlists.', color=discord.Color.blurple()))


# Set up the cog for the bot
async def setup(bot):
    await bot.add_cog(music_cog(bot), guilds=guilds_list) 

