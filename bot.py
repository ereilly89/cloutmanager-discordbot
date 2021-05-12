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
from collections import defaultdict

try:
    import cPickle as pickle
except ImportError:
    import pickle

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


class StringContinuationImpossibleError(Exception):
    pass

    def generateDatabase(self, textSample, sentenceSep='[.!?\n]', n=2):
        """ Generate word probability database from raw content string """
        # I'm using the database to temporarily store word counts
        textSample = _wordIter(textSample, sentenceSep)  # get an iterator for the 'sentences'
        # We're using '' as special symbol for the beginning
        # of a sentence
        db[('',)][''] = 0.0
        for line in textSample:
            words = line.strip().split()  # split words in line
            if len(words) == 0:
                continue
            # first word follows a sentence end
            db[("",)][words[0]] += 1

            for order in range(1, n + 1):
                for i in range(len(words) - 1):
                    if i + order >= len(words):
                        continue
                    word = tuple(words[i:i + order])
                    db[word][words[i + order]] += 1

                # last word precedes a sentence end
                db[tuple(words[len(words) - order:len(words)])][""] += 1

        # We've now got the db filled with parametrized word counts
        # We still need to normalize this to represent probabilities
        for word in self.db:
            wordsum = 0
            for nextword in self.db[word]:
                wordsum += self.db[word][nextword]
            if wordsum != 0:
                for nextword in self.db[word]:
                    self.db[word][nextword] /= wordsum

    def dumpdb(self):
        try:
            with open(self.dbFilePath, 'wb') as dbfile:
                pickle.dump(self.db, dbfile)
            # It looks like db was written successfully
            return True
        except IOError:
            logging.warn('Database file could not be written')
            return False

    def generateString(self):
        """ Generate a "sentence" with the database of known text """
        return self._accumulateWithSeed(('',))

    def generateStringWithSeed(self, seed):
        """ Generate a "sentence" with the database and a given word """
        # using str.split here means we're contructing the list in memory
        # but as the generated sentence only depends on the last word of the seed
        # I'm assuming seeds tend to be rather short.
        words = seed.split()
        if (words[-1],) not in self.db:
            # The only possible way it won't work is if the last word is not known
            raise StringContinuationImpossibleError('Could not continue string: '
                                                    + seed)
        return self._accumulateWithSeed(words)

    def _accumulateWithSeed(self, seed):
        """ Accumulate the generated sentence with a given single word as a
        seed """
        nextWord = self._nextWord(seed)
        sentence = list(seed) if seed else []
        while nextWord:
            sentence.append(nextWord)
            nextWord = self._nextWord(sentence)
        return ' '.join(sentence).strip()

    def _nextWord(self, lastwords):
        lastwords = tuple(lastwords)
        if lastwords != ('',):
            while lastwords not in self.db:
                lastwords = lastwords[1:]
                if not lastwords:
                    return ''
        probmap = self.db[lastwords]
        sample = random.random()
        # since rounding errors might make us miss out on some words
        maxprob = 0.0
        maxprobword = ""
        for candidate in probmap:
            # remember which word had the highest probability
            # this is the word we'll default to if we can't find anythin else
            if probmap[candidate] > maxprob:
                maxprob = probmap[candidate]
                maxprobword = candidate
            if sample > probmap[candidate]:
                sample -= probmap[candidate]
            else:
                return candidate
        # getting here means we haven't found a matching word. :(
        return maxprobword


# {words: {word: prob}}
# We have to define these as separate functions so they can be pickled.
def _db_factory():
    return defaultdict(_one_dict)


def _one():
    return 1.0


def _one_dict():
    return defaultdict(_one)


def _wordIter(text, separator='.'):
    """
    An iterator over the 'words' in the given text, as defined by
    the regular expression given as separator.
    """
    exp = re.compile(separator)
    pos = 0
    for occ in exp.finditer(text):
        sub = text[pos:occ.start()].strip()
        if sub:
            yield sub
        pos = occ.start() + 1
    if pos < len(text):
        # take case of the last part
        sub = text[pos:].strip()
        if sub:
            yield sub


# *** COMMANDS ***#

@client.command(help='get clout manager bot\'s latency.')
async def ping(ctx):
    await ctx.send(f'Pong! {round(client.latency * 1000)}ms')


""""
@client.command()
async def test(ctx):
    markovChain = MarkovChain()

@client.command()
async def ga(ctx):
    with open('goldenage.png', 'rb') as f:
        picture = discord.File(f)
        await ctx.channel.send('This server has officially entered a golden age', file=picture)

@client.command()
async def maintdown(ctx):
    await ctx.channel.send("Clout Manager is temporarily down for maintenance.")


@client.command()
async def maintup(ctx):
    await ctx.channel.send("Clout Manager is back up and running.")
"""


@client.command(help="returns a user's clout.")
async def getclout(ctx, user: discord.Member):
    user = clout.find_one({"username": str(user.name) + "#" + str(user.discriminator)},
                          {"username": 1, "clout_points": 1})
    await ctx.send(str(user['username']) + " has " + str(user['clout_points']) + " clout.")


@client.command(help='returns the clout leaderboard.')
async def topclout(ctx):
    message = ""
    count = 0
    for x in clout.find({}).sort("clout_points", -1):
        count = count + 1
        message = message + str(count) + ". " + str(x['username']) + ": " + str(x['clout_points']) + "\n"
    await ctx.send(message)


@client.command(aliases=['setclout'], help='set a user\'s clout.')
@commands.has_permissions(administrator=True)
async def setClout(ctx, user: discord.Member, theClout):
    username = str(user.name) + "#" + str(user.discriminator)
    if clout.find_one({"username": username}, {"username": 1, "clout_points": 1}):
        clout.update_one({"username": username}, {"$set": {"clout_points": int(theClout)}})
    else:
        clout.insert_one({"username": username, "clout_points": int(theClout)})


@client.command(help='sets the clout threshhold for a role.')
@commands.has_permissions(administrator=True)
async def setCloutRole(ctx, role, threshhold):
    if roles.find_one({"role": role}, {"role": 1, "threshhold": 1}):
        roles.update_one({"role": role}, {"$set": {"threshhold": int(threshhold)}})
    else:
        roles.insert_one({"role": role, "threshhold": int(threshhold)})


@client.command(help='returns the clout roles and clout threshholds.')
async def cloutroles(ctx):
    message = ""
    for x in roles.find({}).sort('threshhold'):
        message = message + str(x['role']) + " >= " + str(x['threshhold']) + " clout\n"
    await ctx.send(message)


@client.command(help='deletes a given clout role.')
@commands.has_permissions(administrator=True)
async def deleteCloutRole(ctx, role):
    roles.delete_one({"role": role})


@client.command(help="bet your bitclout")
async def bet(ctx, amount):
    author = str(ctx.author)
    sender = clout.find_one({"username": author})

    if int(sender["bitclout"]) >= int(amount):
        message = await ctx.send(str(ctx.author) + " placed bet of " + str(int(amount)) + " bitclout. React to accept.")
    else:
        await ctx.send("Bet failed - not enough bitclout.")
    await message.add_reaction(client.get_emoji(826702316920766474))
    await message.add_reaction(client.get_emoji(433204223769968640))


@client.command(aliases=['dailies'], help='mine your daily bitclout.')
async def daily(ctx):
    author = str(ctx.author)
    user = clout.find_one({"username": author})
    setting = settings.find_one({})
    blocksMined = setting["blocks_mined"]
    circulation = setting["circulation"]

    difficulty = (int)(blocksMined / 5000) + 1
    maxBitclout = 10000000

    date_format = "%H:%M:%S.%f"
    try:
        test = user["lastModified"]
        diff = datetime.now() - user["lastModified"]
        time = datetime.strptime(str(diff), date_format)
    except:
        if difficulty <= 8:
            reward = (int)(maxBitclout / 5000) / pow(2, difficulty)
        else:
            reward = 1
        settings.update_one({}, {"$inc": {"blocks_mined": 1}})
        settings.update_one({}, {"$inc": {"circulation": reward}})
        clout.update_one({"username": str(ctx.author)}, {"$inc": {"bitclout": reward},
                                                         "$currentDate": {"lastModified": True,
                                                                          "last_claimed": {"$type": "timestamp"}}})
        await ctx.send("You claimed " + str(int(reward)) + " daily bitclout.")

    if time.hour > 24:
        if circulation < maxBitclout:
            if difficulty <= 8:
                reward = (int)(maxBitclout / 5000) / pow(2, difficulty)
            else:
                reward = 1
            settings.update_one({}, {"$inc": {"blocks_mined": 1}})
            settings.update_one({}, {"$inc": {"circulation": reward}})

            clout.update_one({"username": str(ctx.author)}, {"$inc": {"bitclout": reward},
                                                             "$currentDate": {"lastModified": True,
                                                                              "last_claimed": {"$type": "timestamp"}}})

            await ctx.send("You claimed " + str(int(reward)) + " daily bitclout.")
    else:
        await ctx.send("You've already mined your bitclout today.")


@client.command(help='get a users bitclout balance.')
async def bitclout(ctx, user: discord.Member):
    user = clout.find_one({"username": str(user.name) + "#" + str(user.discriminator)},
                          {"username": 1, "bitclout": 1})
    await ctx.send(str(user['username']) + " has " + str(int(user['bitclout'])) + " bitclout.")


@client.command(help='get your bitclout balance.')
async def wallet(ctx):
    user = clout.find_one({"username": str(ctx.author)},
                          {"username": 1, "bitclout": 1})
    await ctx.send("You have " + str(int(user['bitclout'])) + " bitclout.")


@client.command(help='displays how many blocks until the next bitclout reward halving.')
async def halv(ctx):
    setting = settings.find_one({})
    if setting["blocks_mined"] / 5000 > 8:
        await ctx.send("No more halvings, one bitclout reward per block mined until 10,000,000 bitclout reached.")
    else:
        await ctx.send((str(5000 - setting["blocks_mined"] % 5000) + " blocks until next halving (" + str(
            int(setting["blocks_mined"] / 5000) + 1) + "/8)"))


@client.command(help='transfer bitclout balance to another account.')
async def transfer(ctx, amount, user: discord.Member):
    sender = clout.find_one({"username": str(ctx.author)})
    if int(sender["bitclout"]) >= int(amount):
        clout.update_one({"username": str(ctx.author)}, {"$inc": {"bitclout": -1 * int(amount)}})
        clout.update_one({"username": str(user.name) + "#" + str(user.discriminator)},
                         {"$inc": {"bitclout": int(amount)}})
        await ctx.send("Successfully transferred " + str(int(amount)) + " bitclout to " + str(user.name) + "#" + str(
            user.discriminator))
    else:
        await ctx.send("Transfer failed - not enough bitclout.")


@client.command(help='get bitclout in circulation.')
async def circ(ctx):
    setting = settings.find_one({})
    await ctx.send(str(int(setting['circulation'])) + "/10,000,000 bitclout in circulation.")


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

            if (messageSplit[2] == "bet" and theReactor != "Clout Manager#8162"):
                betterString = messageSplit[0]
                amount = int(messageSplit[4])
                better1 = clout.find_one({"username": theReactor})

                if theReactor != betterString:
                    if better1["bitclout"] >= amount:
                        better2 = clout.find_one({"username": betterString})
                        if better2["bitclout"] >= amount:
                            if random.randint(0, 1) == 0:
                                clout.update_one({"username": theReactor}, {"$inc": {"bitclout": -1 * int(amount)}})
                                clout.update_one({"username": betterString}, {"$inc": {"bitclout": int(amount)}})
                                await message.edit(content=betterString + " beat " + theReactor + " to win " + str(
                                    int(amount) * 2) + " bitclout.")
                            else:
                                clout.update_one({"username": betterString}, {"$inc": {"bitclout": -1 * int(amount)}})
                                clout.update_one({"username": theReactor}, {"$inc": {"bitclout": int(amount)}})
                                await message.edit(content=theReactor + " beat " + betterString + " to win " + str(
                                    int(amount) * 2) + " bitclout.")

                            await message.clear_reactions()
                        else:
                            await message.edit(
                                content=message.content + "\n" + betterString + " no longer has the funds to match.")
                    else:
                        await message.edit(content=message.content + "\nYou don't have the funds to match.")
                else:
                    await message.edit(content=message.content + "\nCan't bet against yourself.")
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
