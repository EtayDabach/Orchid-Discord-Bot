import asyncio
import discord 
from discord.ext import commands
from discord import app_commands
import requests 
import os
from dotenv import load_dotenv
import datetime as dt
from discord_servers_cogs import *


# Load the .env file
load_dotenv()

guilds_list = all_discord_servers

WEATHER_API_KEYE = os.getenv('WEATHER_API_KEY')
GEOCODING_URL = os.getenv('GEOCODING_URL')
WEATHER_URL = os.getenv('WEATHER_URL')



class weather_cog(commands.Cog):
    def __init__(self, bot:commands.Bot):
        self.bot = bot



    @commands.command(name="weather", aliases=["wthr"], description="Gives current weather in the given city")
    @app_commands.describe(city='The name of the city you wish to check the weather in. City name, state code (only for the US) and country code divided by comma. Please use ISO 3166 country codes.')
    @app_commands.rename(city='city')
    async def weather(self, ctx:commands.Context, *, city:str) -> None:
        """
        |coroutine| Check the current weather in the given city. Uses API to get the coordinates and the weather.
        \n
        e.g: 
        \n
        /weather {city name},{state code},{country code}

        Args:
            ctx (commands.Context): discord.ext.commands.Context Represents the context in which a command is being invoked under.
            city (str): The name of the city you wish to check the weather in. City name, state code (only for the US) and country code divided by comma:
            {city name},{state code},{country code}. Please use ISO 3166 country codes.
        """
        coordinates_parameters = {
            'q': city,
            'appid': WEATHER_API_KEYE,
            }
        await ctx.typing()
        try:
            # Get location coordinates
            coordinates_response = requests.get(url=GEOCODING_URL, params=coordinates_parameters)
            coordinates_response.raise_for_status()

            coordinates_data = coordinates_response.json()
            # print(coordinates_data)

            name = coordinates_data[0]['name']
            lat = coordinates_data[0]['lat']
            lon =  coordinates_data[0]['lon']
            country = coordinates_data[0]['country']
            print(f'{name} is at latitude of {lat} and longitude {lon} in the country {country}')

            # For the weather 
            weather_parameters = {
                'lat': lat,
                'lon': lon,
                'appid': WEATHER_API_KEYE,
                'units': 'metric',
                }
        except Exception as e:
            print(f'from first response (coorditanes): {e}')
            await ctx.send(embed=discord.Embed(title='Something went wrong while extracting the coordinates...', description=f'Please ask my admin to look at this problem.' ,color=discord.Color.blurple()))
            return
        
        await asyncio.sleep(3) # Slow the requests

        # Split the request to two parts of a try/except
        try:
            weather_response = requests.get(url=WEATHER_URL, params=weather_parameters)
            weather_response.raise_for_status()

            weather_data = weather_response.json()
            # print(weather_data)

            temperature = weather_data['main']['temp']  # °C
            wind_speed = weather_data['wind']['speed'] # meter/sec

            main_weather_list = []
            description_weather_list = []

            for weather in weather_data['weather']:
                main_weather_list.append(weather['main'])
                description_weather_list.append(weather['description'])

            message = f'The current weather and conditions in {name}, {country} as of {dt.datetime.now().strftime('%d-%m-%Y %H:%M:%S')}: \n'

            for index in range(len(main_weather_list)):
                message += f'{main_weather_list[index]} : {description_weather_list[index]}, \n'

            message += f'The temperature is {temperature}°C , \nThe wind speed is {wind_speed} meter/sec .'

            print(message)

            embed = discord.Embed(title='Here you go!', description=f'{message}' ,color=discord.Color.blurple())
            await ctx.send(embed=embed)

        except Exception as e:
            print(f'from second response (weather): {e}')
            await ctx.send(embed=discord.Embed(title='Something went wrong while extracting the weather...', description=f'Please ask my admin to look at this problem.' ,color=discord.Color.blurple()))
            return


# Set up the cog for the bot
async def setup(bot):
    await bot.add_cog(weather_cog(bot), guilds=guilds_list) 
