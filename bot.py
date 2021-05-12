# bot.py
import os
import discord
from discord.ext import commands
from discord.utils import get
from pymongo import MongoClient
from dotenv import load_dotenv
from datetime import *
from keep_alive import keep_alive
import emoji
import logging
import os
import random
import re
import random
from collections import defaultdict

load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD = os.getenv('DISCORD_GUILD')

intents = discord.Intents().default()
intents.members = True
prefix = 'c!'
client = commands.Bot(command_prefix=prefix, intents=intents)

mongo = MongoClient(os.getenv('MONGO_URL'))

db = mongo.CloutManager
clout = db.clout
roles = db.roles
settings = db.settings
blockchain = db.blockchain


# *** COMMANDS ***#

@client.command(help='get clout manager bot\'s latency')
async def ping(ctx):
    await ctx.send(f'Pong! {round(client.latency * 1000)}ms')
    

#---Clout Manager  

@client.command(help="returns a user's clout")
async def getclout(ctx, user: discord.Member):
    user = clout.find_one({"username": str(user.name) + "#" + str(user.discriminator)},
                          {"username": 1, "clout_points": 1})
    await ctx.send(str(user['username']) + " has " + str(user['clout_points']) + " clout")


@client.command(help='returns the clout leaderboard')
async def topclout(ctx):
    message = ""
    count = 0
    for x in clout.find({}).sort("clout_points", -1):
        count = count + 1
        message = message + str(count) + ". " + str(x['username']) + ": " + str(x['clout_points']) + "\n"
        if count == 15:
          break
    await ctx.send(message)


@client.command(aliases=['setclout'], help='set a user\'s clout')
@commands.has_permissions(administrator=True)
async def setClout(ctx, user: discord.Member, theClout):
    username = str(user.name) + "#" + str(user.discriminator)
    if clout.find_one({"username": username}, {"username": 1, "clout_points": 1}):
        clout.update_one({"username": username}, {"$set": {"clout_points": int(theClout)}})
    else:
        clout.insert_one({"username": username, "clout_points": int(theClout)})


@client.command(help='sets the clout threshhold for a role')
@commands.has_permissions(administrator=True)
async def setCloutRole(ctx, role, threshhold):
    if roles.find_one({"role": role}, {"role": 1, "threshhold": 1}):
        roles.update_one({"role": role}, {"$set": {"threshhold": int(threshhold)}})
    else:
        roles.insert_one({"role": role, "threshhold": int(threshhold)})


@client.command(help='returns the clout roles and clout threshholds')
async def cloutroles(ctx):
    message = ""
    for x in roles.find({}).sort('threshhold'):
        message = message + str(x['role']) + " >= " + str(x['threshhold']) + " clout\n"
    await ctx.send(message)


@client.command(help='deletes a given clout role')
@commands.has_permissions(administrator=True)
async def deleteCloutRole(ctx, role):
    roles.delete_one({"role": role})


#---Bitclout

@client.command(help="bet your bitclout")
async def bet(ctx, amount):
  author = str(ctx.author)
  sender = clout.find_one({"username": author})
  message = ""
  if int(amount) > 0:
    if int(sender["bitclout"]) >= int(amount):
      message = await ctx.send(str(ctx.author) + " placed bet of " + str(int(amount)) + " bitclout. "+str(client.get_emoji(826702316920766474))+" to Match, "+str(client.get_emoji(433204223769968640))+" to Cancel")
    else:
      await ctx.send("Bet failed - Not enough bitclout.")
    await message.add_reaction(client.get_emoji(826702316920766474))
    await message.add_reaction(client.get_emoji(433204223769968640))
  else:
    await ctx.send("Bet failed - Must be positive bitclout")


@client.command(help='get a block\'s information')
async def block(ctx, block_id):
  block_id = int(block_id)
  block = blockchain.find_one({"block_id": block_id})
  message = "block_id: " + str(block["block_id"]) + "\ntransactions: "

  count = 0
  for transaction in block["transactions"]:
    if count != 0:
      message = message + "\n\t" + transaction
    else:
      count = count + 1
  message = message + "\nminer: " + str(block["miner"])
  message = message + "\nreward: " + str(int(block["reward"]))
  message = message + "\ndate: " + str(block["date"])
  await ctx.send(message)


@client.command(aliases=['dailies','mine'], help='mine your daily bitclout')
async def daily(ctx):
    author = str(ctx.author)
    user = clout.find_one({"username": author})

    setting = settings.find_one({})
    blocksMined = setting["blocks_mined"]
    circulation = setting["circulation"]
    transactions = setting["transactions"]

    difficulty = (int)(blocksMined / 2441) + 1
    maxBitclout = 10000000
   
    date_format = "%H:%M:%S.%f"
    try:

      try:
        if user["lastModified"]:
          diff = datetime.utcnow()-timedelta(hours = 5)-user["lastModified"]
        time = datetime.strptime(str(diff), date_format)
        print("try!")
      except:
        print("except!")
        time = {}
        time["hour"] = 24
        time["minute"] = 0
      
    except:
      reward = 0
      if circulation < maxBitclout:
        if difficulty <= 11: #num halvings
            reward =  (4096 / pow(2, difficulty))
        else:
            reward = 1

        await updateUserSendMessage(ctx, reward, blocksMined)
        message = await welcomeNewUser(str(ctx.author))
        print("message:"+str(message))
        if message is not None:
          await ctx.send(message)
        await updateBlockchain(setting, reward)
        await updatePercentMined(ctx, reward, circulation)
       
        setting = settings.find_one({})
        if setting["blocks_mined"] % 2441 == 0:
          settings.update_one({}, {"$set":{"last_halved": datetime.utcnow()-timedelta(hours = 5), "mined_this_halving": 0}})
          ctx.send("The bitclout reward has halved!")
          
      else:
        await ctx.send("You claimed 0 daily bitclout from mining block #"+str(blocksMined))

      await insertBlock(blocksMined, transactions, str(ctx.author), reward, datetime.utcnow()-timedelta(hours = 5))

      message = await updateMaxTransactions(setting, transactions)
      if message is not None:
        await ctx.send(message)

      settings.update_one({},{"$set":{"transactions":[""]}})

    #print(str(24 - time.hour))

    try:
      if time.hour >= 24:
        reward = 0
        if circulation < maxBitclout:
          if difficulty <= 11:
              reward =  (4096 / pow(2, difficulty))
          else:
              reward = 1

          await updateUserSendMessage(ctx, reward, blocksMined)
          message = await welcomeNewUser(str(ctx.author))
          print("message:"+str(message))
          if message is not None:
            await ctx.send(message)
          await updateBlockchain(setting, reward)
          await updatePercentMined(ctx, reward, circulation)

          setting = settings.find_one({})
          if setting["blocks_mined"] % 2441 == 0:
            settings.update_one({}, {"$set":{"last_halved": datetime.utcnow()-timedelta(hours = 5), "mined_this_halving": 0}})
            ctx.send("The bitclout reward has halved!")
        else:
          await ctx.send("You claimed 0 daily bitclout from mining block #"+str(blocksMined))

        await insertBlock(blocksMined, transactions, str(ctx.author), reward, datetime.utcnow()-timedelta(hours = 5))
        
        message = await updateMaxTransactions(setting, transactions)
        if message is not None:
          await ctx.send(message)
        settings.update_one({},{"$set":{"transactions":[""]}}) 

      else:
        await ctx.send("You can mine your daily bitclout block in " + str(24 - time.hour - 1) +" hours, " + str(60 - time.minute) + " minutes")
    except:
      
      if time["hour"] >= 24:
        reward = 0
        if circulation < maxBitclout:
          if difficulty <= 11:
              reward =  (4096 / pow(2, difficulty))
          else:
              reward = 1

          await updateUserSendMessage(ctx, reward, blocksMined)
          message = await welcomeNewUser(str(ctx.author))
          print("message:"+str(message))
          if message is not None:
            await ctx.send(message)
          await updateBlockchain(setting, reward)
          await updatePercentMined(ctx, reward, circulation)

          setting = settings.find_one({})
          if setting["blocks_mined"] % 2441 == 0:
            settings.update_one({}, {"$set":{"last_halved": datetime.utcnow()-timedelta(hours = 5), "mined_this_halving": 0}})
            ctx.send("The bitclout reward has halved!")
        else:
          await ctx.send("You claimed 0 daily bitclout from mining block #"+str(blocksMined))

        await insertBlock(blocksMined, transactions, str(ctx.author), reward, datetime.utcnow()-timedelta(hours = 5))

        message = await updateMaxTransactions(setting, transactions)
        if message is not None:
          await ctx.send(message)
        settings.update_one({},{"$set":{"transactions":[""]}}) 


async def updateBlockchain(setting, reward):
  settings.update_one({}, {"$inc": {"blocks_mined": 1, "mined_this_halving": 1, "circulation": reward}})
  

async def updateUserSendMessage(ctx, reward, blocksMined):
  clout.update_one({"username": str(ctx.author)}, {"$inc": {"bitclout": reward}, "$set": {"lastModified": datetime.utcnow()-timedelta(hours = 5)}})
  await ctx.send("You claimed " + "{:,}".format(int(reward)) + " daily bitclout from mining block #"+str(blocksMined))

async def updatePercentMined(ctx, reward, circ):
  setting = settings.find_one({})
  circ = int(setting["circulation"])
  print(str(circ))
  print(str(reward))
  print(str(int(circ / 100000.0)))
  print(str(int(int(reward + circ) / 100000.0)))
  
  if int((circ - reward) / 100000.0) != int((int(circ)) / 100000.0): #percentage (%) mined out of 10,000,000
    message = await reportMined(ctx, circ)
    if message is not None:
      await ctx.send(message)

async def updateMaxTransactions(setting, transactions):
  setting = settings.find_one({})
  maxTransactions = setting["maxTransactions"]
  message = ""
  print("lenTransactions: "+str(len(transactions)))
  print("maxTransactions: "+str(maxTransactions))
  if len(transactions) > maxTransactions:
    settings.update_one({},{"$set":{"maxTransactions":len(transactions)}})
    message = "\nNew largest block! ("+ str(len(transactions))+" transactions)\n"
    return message

async def insertBlock(block_id, transactions, miner, reward, datetime):
  blockchain.insert_one({"block_id":block_id, "transactions":transactions,"miner":miner,"reward":reward, "date":datetime})

async def welcomeNewUser(user):
  print("welcome new user.")
  if not blockchain.find_one({"miner":user}):
    setting = settings.find_one({})
    wallets = setting["wallets"]
    settings.update_one({}, {"$set":{"wallets":wallets + 1}})
    message = "\nThe bitclout network has grown to " + str(wallets + 1) + " users"
    return message

async def reportMined(ctx, circ):
  message = "\n" + str(int(int(circ)/100000.0)) + "% of the maximum bitclout supply has been mined."
  return message


@client.command(help='get a users bitclout balance.')
async def bitclout(ctx, user: discord.Member):
  user = clout.find_one({"username": str(user.name) + "#" + str(user.discriminator)},
                          {"username": 1, "bitclout": 1})
  await ctx.send(str(user['username']) + " has " + "{:,}".format(int(user['bitclout'])) + " bitclout")


@client.command(aliases=["credits", "balance", "bal"], help='get your bitclout balance')
async def wallet(ctx):
  user = clout.find_one({"username": str(ctx.author)},
                            {"username": 1, "bitclout": 1})
  await ctx.send("You have " + "{:,}".format(int(user['bitclout'])) + " bitclout")


@client.command(aliases=['halving'], help='displays how many blocks until the next bitclout reward halving')
async def halv(ctx):
  setting = settings.find_one({})
  blocksMined = setting["blocks_mined"]
  last_halved = setting["last_halved"]
  mined_this_halving = setting["mined_this_halving"]

  difficulty = (int)(blocksMined / 2441) + 1
  if setting["blocks_mined"] / 2441 > 11:
    await ctx.send("No more halvings, one bitclout reward per block mined until 10 million  bitclout have been mined")
  else:
     reward =  (4096 / pow(2, difficulty))
     predictedHalving = await predNextHalving(last_halved, datetime.utcnow()-timedelta(hours = 5), mined_this_halving)
     await ctx.send("Current reward is " + str(int(reward)) +" bitclout per block, "+ (str(2441 - setting["blocks_mined"] % 2441) + " blocks until next halving (" + str(int(setting["blocks_mined"] / 2441)+1)+"/11)"))
  
async def predNextHalving(date_last, date_current, numMined):
  print("time this halving:" + str(date_current - date_last))
  print("numMined this halving:" + str(numMined))
  timePerBlock = (date_current - date_last) / numMined
  timePerHalving = timePerBlock * 2411
  return date_current + timePerHalving
  
@client.command(aliases=["hashrate"], help='get the estimated halving date based on current hashrate')
async def hash(ctx):
  setting = settings.find_one({})
  last_halved = setting["last_halved"]
  mined_this_halving = setting["mined_this_halving"]
  predHalving = await predNextHalving(last_halved, datetime.utcnow()-timedelta(hours = 5), mined_this_halving)
  message = "At the current hashrate, the next halving will be " + str(predHalving.month) + "/" + str(predHalving.day) + "/" + str(predHalving.year) + " (" + str(round(mined_this_halving / ((datetime.utcnow()-timedelta(hours = 5) - last_halved).total_seconds() / 86400), 2))+ " blocks/day)"
  await ctx.send(message)
  #predictedHalving = await predNextHalving(last_halved, datetime.utcnow()-timedelta(hours = 5), mined_this_halving)

@client.command(aliases=["t"], help='transfer bitclout balance to another account')
async def transfer(ctx, amount, user: discord.Member):
  sender = clout.find_one({"username":str(ctx.author)})
  if str(ctx.author) != str(user.name) + "#" + str(user.discriminator):
    if int(amount) > 0:
      if int(sender["bitclout"]) >= int(amount):
        clout.update_one({"username": str(ctx.author)},{"$inc":{"bitclout": -1*int(amount)}})
        clout.update_one({"username": str(user.name) + "#" + str(user.discriminator)},{"$inc":{"bitclout": int(amount)}})
        setting = settings.find_one({})
        transactions = setting["transactions"]
        transactions.append(str(ctx.author)+" transferred "+str(int(amount))+" to "+str(user.name) + "#" + str(user.discriminator))
        print("transactions:"+str(transactions))
        settings.update_one({},{"$set":{"transactions":transactions}})
        await ctx.send("Successfully transferred " + str(int(amount)) + " bitclout to " + str(user.name) + "#" + str(user.discriminator))
      else:
        await ctx.send("Transfer failed - Not enough bitclout")
    else:
      await ctx.send("Transfer failed - Must be positive bitclout")
  else:
    await ctx.send("Transfer failed - Cannot send funds to yourself")


@client.command(aliases=['circulation'], help='get bitclout in circulation')
async def circ(ctx):
  setting = settings.find_one({})
  await ctx.send("{:,}".format(int(setting['circulation'])) + " out of 10,000,000 bitclout have been mined (" + str(round(int(setting['circulation'])/100000.0, 3)) + "%)")


# *** EVENTS ***#

@client.event
async def on_ready():
    print('Bot is ready.')


@client.event
async def on_raw_reaction_add(payload):
    guild = client.get_guild(payload.guild_id)
    channel = guild.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    theUser = str(message.author.name) + "#" + str(message.author.discriminator)
    user = clout.find_one({"username": theUser}, {"username": 1, "clout_points": 1})

    theReactor = str(payload.member.name) + "#" + str(payload.member.discriminator)

    if str(emoji.demojize(str(payload.emoji))) == "<:COLEWARE:826702316920766474>":
     
      if theUser == "Clout Manager#8162":
        messageSplit = message.content.split(" ")

        if(messageSplit[2] == "bet" and theReactor != "Clout Manager#8162"):
          betterString = messageSplit[0]
          amount = int(messageSplit[4])
          better1 = clout.find_one({"username": theReactor})

          if theReactor != betterString:
            if better1["bitclout"] >= amount:
              better2 = clout.find_one({"username": betterString})
              setting = settings.find_one({})
              transactions = setting["transactions"]

              if better2["bitclout"] >= amount:
                if random.randint(0, 1) == 0:
                  clout.update_one({"username": theReactor},{"$inc":{"bitclout": -1*int(amount)}})
                  clout.update_one({"username": betterString},{"$inc":{"bitclout": int(amount)}})
                  await channel.send(betterString + " beat " + theReactor + " to win "+ str(int(amount)*2) + " bitclout.")
                  
                  transactions.append(theReactor +" lost "+str(int(amount))+" to "+ betterString)
                  settings.update_one({},{"$set":{"transactions":transactions}})

                else:
                  clout.update_one({"username": betterString},{"$inc":{"bitclout": -1*int(amount)}})
                  clout.update_one({"username": theReactor},{"$inc":{"bitclout": int(amount)}})
                  await channel.send(theReactor + " beat " + betterString + " to win "+ str(int(amount)*2) + " bitclout.")
                  
                  transactions.append(betterString +" lost "+str(int(amount))+" to "+ theReactor)
                  settings.update_one({},{"$set":{"transactions":transactions}})

                await message.clear_reactions()
              else:
                await message.edit(content=message.content + "\n" + betterString  + " no longer has the funds to match")
            else:
              await message.edit(content=message.content+"\nYou don't have the funds to match")
          else:
            await message.edit(content=message.content+"\nCan't bet against yourself")
    elif str(emoji.demojize(str(payload.emoji))) == "<:militia:433204223769968640>": 
      messageSplit = message.content.split(" ")
      if theReactor == messageSplit[0]:
        await message.delete()

    elif theUser != theReactor:

        if str(payload.emoji) == str(client.get_emoji(433201549708361738)):
            if user is None:
                newUser = {"username": theUser,
                           "clout_points": 1}
                clout.insert_one(newUser)
            else:
                clout.update({"username": theUser}, {"$inc": {"clout_points": 1}})
                await changeRoleUp(theUser, message.author, payload.guild_id, channel)

        elif str(payload.emoji) == str(client.get_emoji(433206749735157780)):
            if user is None:
                newUser = {"username": theUser,
                           "clout_points": -1}
                clout.insert_one(newUser)
            else:
                clout.update({"username": theUser}, {"$inc": {"clout_points": -1}})
                await changeRoleDown(theUser, message.author, payload.guild_id, channel)


@client.event
async def on_raw_reaction_remove(payload):
    guild = client.get_guild(payload.guild_id)
    channel = guild.get_channel(payload.channel_id)
    message = await channel.fetch_message(payload.message_id)

    ctx = await client.get_context(message)

    theUser = str(message.author.name) + "#" + str(message.author.discriminator)
    user = clout.find_one({"username": theUser}, {"username": 1, "clout_points": 1})

    theReactee = message.author.id
    theReactor = payload.user_id

    if theReactor != theReactee:

        if str(payload.emoji) == str(client.get_emoji(433201549708361738)):

            if user is None:
                newUser = {"username": theUser,
                           "clout_points": 0}
                clout.insert(newUser)

            else:
                clout.update({"username": theUser}, {"$inc": {"clout_points": -1}})
                await changeRoleDown(theUser, message.author, payload.guild_id, channel)

        elif str(payload.emoji) == str(client.get_emoji(433206749735157780)):

            if user is None:
                newUser = {"username": theUser,
                           "clout_points": 0}
                clout.insert(newUser)

            else:
                clout.update({"username": theUser}, {"$inc": {"clout_points": 1}})
                await changeRoleUp(theUser, message.author, payload.guild_id, channel)


# *** HELPER METHODS ***#

async def changeRoleUp(theUser, member, guildId, channel):
    orderedRoles = roles.find({}).sort("threshhold", -1)
    user = clout.find_one({"username": theUser})

    if roles.find_one({"threshhold": int(user['clout_points'])}):

        guild = client.get_guild(guildId)

        for y in orderedRoles:
            await member.remove_roles(discord.utils.get(guild.roles, name=y['role']))

        orderedRoles = roles.find({}).sort("threshhold", -1)
        for x in orderedRoles:

            if user['clout_points'] >= x['threshhold']:
                await member.add_roles(discord.utils.get(guild.roles, name=x['role']))
                await channel.send(str(member) + " was promoted to " + x['role'] + ", congratulations.")
                break


async def changeRoleDown(theUser, member, guildId, channel):
    orderedRoles = roles.find({}).sort("threshhold", -1)
    user = clout.find_one({"username": theUser})

    if roles.find_one({"threshhold": int(user['clout_points']) + 1}):

        guild = client.get_guild(guildId)

        for y in orderedRoles:
            await member.remove_roles(discord.utils.get(guild.roles, name=y['role']))

        orderedRoles = roles.find({}).sort("threshhold", -1)
        for x in orderedRoles:

            if user['clout_points'] >= x['threshhold']:
                await member.add_roles(discord.utils.get(guild.roles, name=x['role']))
                await channel.send(str(member) + " was demoted to " + x['role'] + " (ouch).")
                break


keep_alive()
client.run(TOKEN)
