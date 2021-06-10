import asyncio
import datetime
import inspect
import io
import itertools
import json
import logging
import math
import os
import pickle
import pprint
import random
import re
import secrets
import shutil
import subprocess
import sys
import threading
import time
import traceback
import typing
import urllib.parse
import urllib.request
from functools import partial
from io import StringIO
from typing import Any, Iterable, Tuple
import yaml

import aiofiles
import aiohttp
import barcode
import discord
import humanfriendly
import numpy as np
import requests
from collections import Counter
import pandas

from async_timeout import timeout
from barcode.writer import ImageWriter
from discord import AsyncWebhookAdapter
from discord import RequestsWebhookAdapter
from discord import Webhook
from discord.ext import commands
from discord.ext import tasks
from discord_components import DiscordComponents, Button, ButtonStyle, InteractionType
from disputils import BotEmbedPaginator, BotConfirmation, BotMultipleChoice
from pandas.io.json import json_normalize
from PIL import Image

prefix = "!"

intents = discord.Intents.all()
bot = commands.AutoShardedBot(
	command_prefix=prefix, description="SKU Tracking Bot made by ThatOneCalculator#1337 for Fire Attire", intents=intents, chunk_guilds_at_startup=True)
ddb = DiscordComponents(bot)

upsince = datetime.datetime.now()
url_rx = re.compile(r'https?://(?:www\.)?.+')

def generate_sku(itemcode, category, logo, size: None, color: None):
	category = category.upper()
	sku = f"{itemcode}-{category}-{logo}"
	if size != None:
		sku += f"-{size[0:2]}"
	if color != None:
		color = re.sub(r'\W+', '', color).replace(" ", "")
		sku += f"-{color}"
	return sku.upper()


class CommandErrorHandler(commands.Cog):

	def __init__(self, bot):
		self.bot = bot

	@commands.Cog.listener()
	async def on_command_error(self, ctx, error):
		"""The event triggered when an error is raised while invoking a command.
		ctx   : Context
		error : Exception"""
		if hasattr(ctx.command, 'on_error'):
			return
		ignored = (commands.CommandNotFound, commands.UserInputError)
		error = getattr(error, 'original', error)
		if isinstance(error, ignored):
			return
		elif isinstance(error, commands.DisabledCommand):
			return await ctx.send(f'{ctx.command} has been disabled.')
		elif isinstance(error, commands.NoPrivateMessage):
			try:
				return await ctx.author.send(f'{ctx.command} can not be used in Private Messages.')
			except:
				pass
		elif isinstance(error, commands.BadArgument):
			if ctx.command.qualified_name == 'tag list':
				return await ctx.send('I could not find that member. Please try again.')
		# print('Ignoring exception in command {}:'.format(ctx.command), file=sys.stderr)
		try:
			traceback.print_exception(
				type(error), error, error.__traceback__, file=sys.stderr)
		except:
			pass


class Items(commands.Cog):

	def __init__(self, bot):
		self.bot = bot

	@commands.command(name="ping")
	async def ping(self, ctx):
		"""Pings the bot"""

		ping = await ctx.send(f":ping_pong: Pong! Bot latency is {str(round((bot.latency * 1000),2))} milliseconds.")
		beforeping = datetime.datetime.now()
		await ping.edit(content="Pinging!")
		afterping = datetime.datetime.now()
		pingdiff = afterping - beforeping
		pingdiffms = pingdiff.microseconds / 1000
		uptime = afterping - upsince
		await ping.edit(content=f"🏓 Pong! Bot latency is {str(round((bot.latency * 1000),2))} milliseconds.\n☎️ API latency is {str(round((pingdiffms),2))} milliseconds.\n:coffee: I have been up for {humanfriendly.format_timespan(uptime)}.")

	@commands.command()
	async def new(self, ctx):
		"""Registers new item"""

		embed = discord.Embed(title="New item", color=0xF5910D)
		embedmessage = await ctx.send(embed=embed)
		def check(x): return x.author == ctx.author
		name = None
		category = None
		logo = None
		colors = []
		items = {}
		validcategories = ["SS", "LS", "SWS", "HOOD",
						   "ZHOOD", "SHORT", "KID", "CAP", "ACC"]
		latestmsg = await ctx.send("What is the **item name**?")
		try:
			namemsg = await bot.wait_for('message', timeout=60.0, check=check)
		except asyncio.TimeoutError:
			return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
		else:
			if "cancel" in namemsg.content.lower():
				return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
			name = namemsg.content
			loading = await ctx.send("<a:loading:846144064805929040>")
			await latestmsg.delete()
			await namemsg.delete()
			embed.add_field(name="Name", value=name)
			await embedmessage.edit(embed=embed)
			await loading.delete()
		latestmsg = await ctx.send("What is the **item category**?",
								 components=[
									 [
										 Button(
											   style=ButtonStyle.blue, label="SS"),
										 Button(
											   style=ButtonStyle.blue, label="LS"),
										 Button(
											   style=ButtonStyle.blue, label="SWS"),
									   ],
									 [
										 Button(style=ButtonStyle.blue,
												  label="HOOD"),
										 Button(style=ButtonStyle.blue,
												  label="ZHOOD"),
										 Button(style=ButtonStyle.blue,
												  label="SHORT"),
										 Button(
											   style=ButtonStyle.blue, label="KID"),
									   ],
									 [
										 Button(
											   style=ButtonStyle.blue, label="CAP"),
										 Button(
											   style=ButtonStyle.blue, label="ACC"),
									   ],
									 Button(style=ButtonStyle.red,
											  label="Cancel!"),
								   ]
								   )
		try:
			categorymsg = await bot.wait_for('button_click', timeout=60.0, check=check)
		except asyncio.TimeoutError:
			return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
		else:
			loading = await ctx.send("<a:loading:846144064805929040>")
			if "Cancel!" in categorymsg.component.label:
				await loading.delete()
				return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
			category = categorymsg.component.label.upper()
		if category not in validcategories:
			return await ctx.send(f"Cancelled, not a valid category. Valid categories: `{validcategories}`")
		await latestmsg.delete()
		await loading.delete()
		embed.add_field(name="Category", value=category)
		await embedmessage.edit(embed=embed)
		latestmsg = await ctx.send("What is the **item logo**?")
		try:
			logomsg = await bot.wait_for('message', timeout=60.0, check=check)
		except asyncio.TimeoutError:
			return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
		else:
			if "cancel" in logomsg.content.lower():
				return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
			logo = logomsg.content.replace(" ", "")
			loading = await ctx.send("<a:loading:846144064805929040>")
			await latestmsg.delete()
			await logomsg.delete()
			embed.add_field(name="Logo", value=logo)
			await embedmessage.edit(embed=embed)
			await loading.delete()
		if category == "CAP":
			items = {
				"sm": {},
				"ml": {},
				"lx": {},
				"x2": {}
			}
			latestmsg = await ctx.send("Does this item have sizes?",
									 components=[
										 [
											 Button(
												   style=ButtonStyle.green, label="Yes"),
											 Button(
												   style=ButtonStyle.blue, label="No"),
										   ],
										 Button(style=ButtonStyle.red,
												  label="Cancel!"),
									   ]
									   )
			try:
				issizemsg = await bot.wait_for('button_click', timeout=60.0, check=check)
			except asyncio.TimeoutError:
				return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
			else:
				loading = await ctx.send("<a:loading:846144064805929040>")
				if "Cancel!" in categorymsg.component.label:
					await loading.delete()
					return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
				issize = True if issizemsg.component.label == "Yes" else False
			await loading.delete()
			await latestmsg.delete()
			latestmsg = await ctx.send("Does this item have sizes?",
									 components=[
										 [
											 Button(
												   style=ButtonStyle.blue, label="Snapback"),
											 Button(
												   style=ButtonStyle.blue, label="Flexfit"),
											 Button(
												   style=ButtonStyle.blue, label="Fitted"),
										   ],
										 Button(style=ButtonStyle.red,
												  label="Cancel!"),
									   ]
									   )
			try:
				stylemsg = await bot.wait_for('button_click', timeout=60.0, check=check)
			except asyncio.TimeoutError:
				return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
			else:
				loading = await ctx.send("<a:loading:846144064805929040>")
				if "Cancel!" in categorymsg.component.label:
					await loading.delete()
					return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
				if stylemsg.component.label == "Snapback":
					fit = "SNAP"
				elif stylemsg.component.label == "Flexfit":
					fit = "FLEX"
				else:
					fit = "FIT"
				ogcategory = category
				category += fit
			await loading.delete()
			await latestmsg.delete()
			if issize:
				skipped = []
				for size in items:
					latestmsg = await ctx.send(f"How much stock is there of {name} in **size {size}**? Enter a number for a value, or a letter to skip.")
					try:
						countmsg = await bot.wait_for('message', timeout=60.0, check=check)
					except asyncio.TimeoutError:
						return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
					else:
						loading = await ctx.send("<a:loading:846144064805929040>")
						if "cancel" in countmsg.content.lower():
							return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
						count = countmsg.content
						await countmsg.delete()
						await latestmsg.delete()
						try:
							count = int(count)
							items[size].update({"NA": count})
						except:
							skipped.append(f"{size}")
						await loading.delete()
				latest = len(os.listdir('skus/'))
				finalskus = {"name": name, "category": ogcategory, "skus": {}}
				loading = await ctx.send("<a:loading:846144064805929040>")
				msg = ""
				for i, j in items.items():
					if len(j) != 0:
						for k, l in j.items():
							sku = generate_sku(latest, category, logo, i)
							msg += f"\n`{sku}`: {l}"
							finalskus["skus"].update({sku: l})
				embed.add_field(name="Skipped", value=str(skipped))
				embed.add_field(name="SKUs", value=msg)
				embed.title = "New item REGISTERED!"
				embed.color = 0x33854B
				with open(f"skus/{latest}.json", "w") as f:
					json.dump(finalskus, f, indent=4)
				await embedmessage.edit(embed=embed)
				await loading.delete()
			else:
				sku = generate_sku(latest, category, logo)
				finalskus["skus"].update({sku: l})
				embed.add_field(name="SKU", value=f"`{sku}`: {l}")
				embed.title = "New item REGISTERED!"
				embed.color = 0x33854B
				await embedmessage.edit(embed=embed)
				await loading.delete()
		elif category == "ACC":
			items = {
				"small": {},
				"medium": {},
				"large": {},
				"xl": {},
				"2xl": {}
			}
			latestmsg = await ctx.send("Does this item have sizes?",
										components=[
											[
												Button(
													style=ButtonStyle.green, label="Yes"),
												Button(
													style=ButtonStyle.blue, label="No"),
											],
											Button(style=ButtonStyle.red,
													label="Cancel!"),
										]
										)
			try:
				issizemsg = await bot.wait_for('button_click', timeout=60.0, check=check)
			except asyncio.TimeoutError:
				return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
			else:
				loading = await ctx.send("<a:loading:846144064805929040>")
				if "Cancel!" in categorymsg.component.label:
					await loading.delete()
					return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
				issize = True if issizemsg.component.label == "Yes" else False
			await loading.delete()
			await latestmsg.delete()
			if issize:
				skipped = []
				for size in items:
					latestmsg = await ctx.send(f"How much stock is there of {name} in **size {size}**? Enter a number for a value, or a letter to skip.")
					try:
						countmsg = await bot.wait_for('message', timeout=60.0, check=check)
					except asyncio.TimeoutError:
						return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
					else:
						loading = await ctx.send("<a:loading:846144064805929040>")
						if "cancel" in countmsg.content.lower():
							return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
						count = countmsg.content
						await countmsg.delete()
						await latestmsg.delete()
						try:
							count = int(count)
							items[size].update({"NA": count})
						except:
							skipped.append(f"{size}")
						await loading.delete()
				latest = len(os.listdir('skus/'))
				finalskus = {"name": name, "category": category, "skus": {}}
				loading = await ctx.send("<a:loading:846144064805929040>")
				msg = ""
				for i, j in items.items():
					if len(j) != 0:
						for k, l in j.items():
							sku = generate_sku(latest, category, logo, i)
							msg += f"\n`{sku}`: {l}"
							finalskus["skus"].update({sku: l})
				embed.add_field(name="Skipped", value=str(skipped))
				embed.add_field(name="SKUs", value=msg)
				embed.title = "New item REGISTERED!"
				embed.color = 0x33854B
				with open(f"skus/{latest}.json", "w") as f:
					json.dump(finalskus, f, indent=4)
				await embedmessage.edit(embed=embed)
				await loading.delete()
			else:
				sku = generate_sku(latest, category, logo)
				finalskus["skus"].update({sku: l})
				embed.add_field(name="SKU", value=f"`{sku}`: {l}")
				embed.title = "New item REGISTERED!"
				embed.color = 0x33854B
				await embedmessage.edit(embed=embed)
				await loading.delete()
		else:
			items = {
				"small": {},
				"medium": {},
				"large": {},
				"xl": {},
				"2xl": {},
				"3xl": {},
				"4xl": {},
				"5xl": {}
			}
			latestmsg = await ctx.send("What are all the **item's colors**? Please seperate colors with spaces. Ex: `red, orange, yellow, lime green, black`")
			try:
				colorsstring = await bot.wait_for('message', timeout=60.0, check=check)
			except asyncio.TimeoutError:
				return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
			else:
				if "cancel" in colorsstring.content.lower():
					return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
				loading = await ctx.send("<a:loading:846144064805929040>")
				colors = colorsstring.content.split(",")
				colorcount = 0
				for i in colors:
					colors[colorcount] = i.strip()
					colorcount += 1
				await latestmsg.delete()
				await colorsstring.delete()
				embed.add_field(name="Colors", value=colors)
				await embedmessage.edit(embed=embed)
				await loading.delete()
			skipped = []
			for color in colors:
				# for size in items:
				# for color in colors:
				for size in items:
					latestmsg = await ctx.send(f"How much stock is there of {name} in **size {size}** and **color {color}**? Enter a number for a value, or a letter to skip.")
					try:
						countmsg = await bot.wait_for('message', timeout=60.0, check=check)
					except asyncio.TimeoutError:
						return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
					else:
						loading = await ctx.send("<a:loading:846144064805929040>")
						if "cancel" in countmsg.content.lower():
							return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
						count = countmsg.content
						await countmsg.delete()
						await latestmsg.delete()
						try:
							count = int(count)
							items[size].update({color: count})
						except:
							skipped.append(f"{size}/{color}")
							# skippedmsg = await ctx.send(f"{size}/{color} skipped")
						await loading.delete()
			latest = len(os.listdir('skus/'))
			finalskus = {"name": name, "category": category, "skus": {}}
			loading = await ctx.send("<a:loading:846144064805929040>")
			msg = ""
			for i, j in items.items():
				if len(j) != 0:
					for k, l in j.items():
						sku = generate_sku(latest, category, logo, i, k)
						msg += f"\n`{sku}`: {l}"
						finalskus["skus"].update({sku: l})
			embed.add_field(name="Skipped", value=str(skipped))
			embed.add_field(name="SKUs", value=msg)
			embed.title = "New item REGISTERED!"
			embed.color = 0x33854B
			with open(f"skus/{latest}.json", "w") as f:
				json.dump(finalskus, f, indent=4)
			await embedmessage.edit(embed=embed)
			await loading.delete()

	@commands.command()
	async def barcode(self, ctx, *, sku=""):
		"""Generates a barcode from an SKU"""

		if sku == "":
			return await ctx.send("Please provide a SKU. Example usage: `!barcode SKU-GOES-HERE`")
		filename = barcode.get(
			'code128', sku, writer=ImageWriter()).save('code128')
		await ctx.send(file=discord.File(filename, filename=filename))

	@commands.command()
	async def low(self, ctx):
		"""Checks what SKUs are below 12"""

		a = os.listdir("skus/")
		embed = discord.Embed(title="SKUs below 12", description="And above 0", color=0xF5910D)
		for i in a:
			with open(f"skus/{i}", "r") as f:
				var = json.load(f)
				for j in var["skus"]:
					if int(var["skus"][j]) < 12 and int(var["skus"][j]) != 0:
						embed.add_field(name=j, value=var["skus"][j])
		await ctx.send(embed=embed)

	@commands.command()
	async def out(self, ctx):
		"""Checks what SKUs are out of stock"""

		a = os.listdir("skus/")
		embed = discord.Embed(title="SKUs out of stock", description="", color=0xED4245)
		for i in a:
			with open(f"skus/{i}", "r") as f:
				var = json.load(f)
				for j in var["skus"]:
					if int(var["skus"][j]) == 0:
						embed.description += f'{j}\n'
		await ctx.send(embed=embed)

	@commands.command()
	async def list(self, ctx):
		"""Lists all SKUs"""

		def check(x): return x.author == ctx.author
		msg = await ctx.send("What category would you like to look up?",
							components=[
								[
									Button(style=ButtonStyle.green,
										label="All")
								],
								[
									Button(style=ButtonStyle.blue,
										label="SS"),
									Button(style=ButtonStyle.blue,
										label="LS"),
									Button(style=ButtonStyle.blue,
										label="SWS"),
								],
								[
									Button(style=ButtonStyle.blue,
										label="HOOD"),
									Button(style=ButtonStyle.blue,
										label="ZHOOD"),
									Button(style=ButtonStyle.blue,
										label="SHORT"),
									Button(style=ButtonStyle.blue,
										label="KID"),
								],
								[
									Button(style=ButtonStyle.blue,
										label="CAP"),
									Button(style=ButtonStyle.blue,
										label="ACC"),
								],
								Button(style=ButtonStyle.red,
									label="Cancel!"),
							]
							)
		try:
			categorymsg = await bot.wait_for('button_click', timeout=60.0, check=check)
		except asyncio.TimeoutError:
			return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
		else:
			loading = await ctx.send("<a:loading:846144064805929040>")
			if "Cancel!" in categorymsg.component.label:
				await loading.delete()
				return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
			category = categorymsg.component.label
		await msg.delete()
		await loading.delete()
		if category == "All":
			count = 0
			embedlist = []
			a = os.listdir("skus/")
			embed = discord.Embed(title=f"All SKUs:", color=0x5865F2)
			for i in a:
				with open(f"skus/{i}", "r") as f:
					var = json.load(f)
				if count % 10 == 0 and count != 0:
					embedlist.append(embed)
					embed = discord.Embed(title=f"All SKUs:", color=0x5865F2)
				count += 1
				try:
					embed.add_field(name=var["name"], value=str(json.dumps(var["skus"], sort_keys=False, indent=4)).replace(
						"\"", "").replace("{", "").replace("}", "").replace(",", ""))
				except:
					embed.add_field(name=var["name"], value="None")
				embed.set_footer(text=f"Page {len(embedlist) + 1}")
				if count == len(a):
					embedlist.append(embed)
			paginator = BotEmbedPaginator(ctx, embedlist)
			await paginator.run()
		else:
			count = 0
			embedlist = []
			catlist = []
			a = os.listdir("skus/")
			embed = discord.Embed(title=f"All SKUs in {category}:", color=0x5865F2)
			for i in a:
				with open(f"skus/{i}", "r") as f:
					var = json.load(f)
				if var["category"] == category:
					catlist.append(i)
			for i in catlist:
				with open(f"skus/{i}", "r") as f:
					var = json.load(f)
				if count % 10 == 0 and count != 0:
					embedlist.append(embed)
					embed = discord.Embed(title=f"All SKUs:", color=0x5865F2)
				count += 1
				try:
					embed.add_field(name=var["name"], value=str(json.dumps(var["skus"], sort_keys=False, indent=4)).replace(
						"\"", "").replace("{", "").replace("}", "").replace(",", ""))
				except:
					embed.add_field(name=var["name"], value="None")
				embed.set_footer(text=f"Page {len(embedlist) + 1}")
				if count == len(catlist):
					embedlist.append(embed)
			paginator = BotEmbedPaginator(ctx, embedlist)
			await paginator.run()

	@commands.command()
	async def lookup(self, ctx, *, sku=""):
		"""Looks up an SKU"""

		if sku == "":
			return await ctx.send("Please provide a SKU. Example usage: `!lookup SKU-GOES-HERE`")
		try:
			theid = sku.split("-")[0]
			with open(f"skus/{theid}.json", "r") as f:
				var = json.load(f)
		except:
			return await ctx.send("That ID doesn't exist! Looks like you got the SKU wrong.")
		for i in var["skus"]:
			if i == sku:
				return await ctx.send(f"{i}: {var['skus'][i]}")
		return await ctx.send("I couldn't find that SKU!")

	@commands.command()
	async def update(self, ctx, *, sku=""):
		"""Updates an SKU"""

		def check(x): return x.author == ctx.author
		if sku == "":
			return await ctx.send("Please provide a SKU. Example usage: `!update SKU-GOES-HERE`")
		message = await ctx.send("What would you like to do?",
								components=[
									[
										Button(style=ButtonStyle.green,
											label="Add", emoji="➕"),
										Button(style=ButtonStyle.grey,
											label="Subtract", emoji="➖"),
										Button(style=ButtonStyle.blue,
											label="Update", emoji="🔄"),
										Button(style=ButtonStyle.grey,
											label="Remove", emoji="🗑️"),
									],
									Button(style=ButtonStyle.red,
										label="Cancel!", emoji="✖"),
								]
								)
		try:
			res = await bot.wait_for('button_click', timeout=60.0, check=check)
		except asyncio.TimeoutError:
			return await ctx.send("Cancelled!")
		else:
			if res.component.label == "Add":
				await ctx.send(f"How much stock do you want to add to {sku}?")
				try:
					msg = await bot.wait_for('message', timeout=60.0, check=check)
				except asyncio.TimeoutError:
					return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
				else:
					try:
						toadd = int(msg.content)
					except:
						return await ctx.send("That's not a number!")
					try:
						theid = skus.split("-")[0]
						with open(f"skus/{theid}.json", "r") as f:
							var = json.load(f)
					except:
						return await ctx.send("That ID doesn't exist! Looks like you got the SKU wrong.")
					for i in var["skus"]:
						if i == sku:
							i = var["skus"][i] + toadd
							with open(f"skus/{theid}.json", "w") as f:
								json.dump(var, f, indent=4)
							return await ctx.send("Done!")
					return await ctx.send("I couldn't find that SKU!")
			elif res.component.label == "Subtract":
				await ctx.send(f"How much stock do you want to subtract from {sku}?")
				try:
					msg = await bot.wait_for('message', timeout=60.0, check=check)
				except asyncio.TimeoutError:
					return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
				else:
					try:
						toadd = int(msg.content)
					except:
						return await ctx.send("That's not a number!")
					try:
						theid = skus.split("-")[0]
						with open(f"skus/{theid}.json", "r") as f:
							var = json.load(f)
					except:
						return await ctx.send("That ID doesn't exist! Looks like you got the SKU wrong.")
					for i in var["skus"]:
						if i == sku:
							if var["skus"][i] - toadd < 0:
								i = 0
							else:
								i = var["skus"][i] - toadd
							theid = skus.split("-")[0]
							with open(f"skus/{theid}.json", "w") as f:
								json.dump(var, f, indent=4)
							return await ctx.send("Done!")
					return await ctx.send("I couldn't find that SKU!")
			elif res.component.label == "Update":
				await ctx.send(f"What is {sku}'s stock?")
				try:
					msg = await bot.wait_for('message', timeout=60.0, check=check)
				except asyncio.TimeoutError:
					return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
				else:
					try:
						toadd = int(msg.content)
					except:
						return await ctx.send("That's not a number!")
					try:
						theid = skus.split("-")[0]
						with open(f"skus/{theid}.json", "r") as f:
							var = json.load(f)
					except:
						return await ctx.send("That ID doesn't exist! Looks like you got the SKU wrong.")
					for i in var["skus"]:
						if i == sku:
							i = toadd
							theid = skus.split("-")[0]
							with open(f"skus/{theid}.json", "w") as f:
								json.dump(var, f, indent=4)
							return await ctx.send("Done!")
					return await ctx.send("I couldn't find that SKU!")
			elif res.component.label == "Remove":
				await ctx.send("Are you sure?",
								components=[
									[
										Button(style=ButtonStyle.red,
												label="Yes!"),
										Button(style=ButtonStyle.red,
												label="No."),
									]
								]
								)
				try:
					categorymsg = await bot.wait_for('button_click', timeout=60.0, check=check)
				except asyncio.TimeoutError:
					return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
				else:
					if "No." in categorymsg.component.label:
						return await ctx.send(embed=discord.Embed(title="Cancelled!", color=0xED4245))
				try:
					theid = skus.split("-")[0]
					with open(f"skus/{theid}.json", "r") as f:
						var = json.load(f)
				except:
					return await ctx.send("That ID doesn't exist! Looks like you got the SKU wrong.")
				for i in var["skus"]:
					if i == sku:
						var.pop(i)
						theid = skus.split("-")[0]
						with open(f"skus/{theid}.json", "w") as f:
							json.dump(var, f, indent=4)
						return await ctx.send("Done!")
				return await ctx.send("I couldn't find that SKU!")
			else:
				return await ctx.send("Cancelled!")

	@commands.command()
	async def help(self, ctx):
		"""This help message!"""

		embed = discord.Embed(
			title="My commands!", description="Made by ThatOneCalculator#1337", color=0x5865F2)
		for i in Items.walk_commands(self):
			embed.add_field(name=f"`!{i.name}`", value=i.help)
		await ctx.send(embed=embed)


@bot.event
async def on_ready():
	await bot.change_presence(activity=discord.Activity(
		type=discord.ActivityType.watching,
		name=f"Fire Attire!"
	))
	print("Logged in!")

bot.remove_command("help")
bot.add_cog(CommandErrorHandler(bot))
bot.add_cog(Items(bot))


def read_token():
	with open("token.txt", "r") as f:
		lines = f.readlines()
		return lines[0].strip()


token = read_token()

dt = str(datetime.datetime.now())
logging.basicConfig(filename="logging.txt", format=dt + '%(message)s')
stderrLogger = logging.StreamHandler()
stderrLogger.setLevel(logging.INFO)
stderrLogger.setFormatter(logging.Formatter(logging.BASIC_FORMAT))
logging.getLogger().addHandler(stderrLogger)
print("Logging in...")
try:
	bot.run(token)
except:
	raise Exception("Couldn't run token!")
