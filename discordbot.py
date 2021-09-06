import time
import requests_async as requests
from datetime import datetime, timezone, timedelta
import dateutil.parser
from dateutil import tz
import discord
from discord.ext import commands
import json
import ccxt
import lending as ld
import re
import language_selection as ls

with open("config.json") as config_file:
    config = json.load(config_file)

TOKEN = config['discord_token']

kucoin = ccxt.kucoin({
    "apiKey": "nope",
    "secret": 'nope',
    "password": "nope",
    'enableRateLimit': True,
})

help_command = commands.DefaultHelpCommand(
    no_category='Commands',
)

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!',
                   help_command=help_command, intents=intents)


@bot.event
async def on_raw_reaction_add(payload):
    await ls.add_language_from_reaction(bot, payload)


@bot.event
async def on_raw_reaction_remove(payload):
    await ls.remove_language_from_reaction(bot, payload)


@bot.group(name='funding', brief="Commands related to the funding", aliases=['f'])
@commands.cooldown(10, 60, commands.BucketType.default)
async def funding(ctx):
    if ctx.invoked_subcommand == None:
        await ctx.send_help(funding)


@funding.command(name='bitmex', brief="Display the actual and the predicted funding from bitmex", aliases=['b'])
async def funding_bitmex(ctx):
    url = "https://www.bitmex.com/api/v1/instrument?symbol=XBTUSD&count=1&reverse=true"
    r = await requests.get(url)
    json = r.json()[0]
    actual_funding = json['fundingRate']
    next_funding = json['indicativeFundingRate']

    funding_timestamp = dateutil.parser.parse(json['fundingTimestamp'])
    funding_timestamp = funding_timestamp.astimezone(
        tz=tz.gettz("Europe/Paris"))

    next_funding_timestamp = (funding_timestamp + timedelta(hours=8))
    await ctx.send(
        "The next funding event is at " +
        funding_timestamp.strftime("%I:%M:%S %p (%Z)") +
        ".\n📈 The rate is " + str(round(actual_funding * 100, 4)) + "% 📈\n\n"
        "The predicted funding event is at " +
        next_funding_timestamp.strftime("%I:%M:%S %p (%Z)") +
        ".\n📈 The rate is " + str(round(next_funding * 100, 4)) + "% 📈")


@funding.command(name='predicted', brief="Display the predicted funding from several exchanges", aliases=['p'])
async def funding_predicted(ctx):
    # First we send all the requests
    url_bitmex = "https://www.bitmex.com/api/v1/instrument?symbol=XBTUSD&count=1&reverse=true"
    r_bitmex = requests.get(url_bitmex)

    url_bybit = "https://api.bybit.com/v2/public/tickers"
    r_bybit = requests.get(url_bybit)

    url_ftx = "https://ftx.com/api/futures/BTC-PERP/stats"
    r_ftx = requests.get(url_ftx)

    url_okex = "https://www.okex.com/api/swap/v3/instruments/BTC-USD-SWAP/funding_time"
    r_okex = requests.get(url_okex)

    # Bitmex - processing the response
    r_bitmex = await r_bitmex
    predicted_bitmex = r_bitmex.json()[0]['indicativeFundingRate']
    # Bitmex - end

    # Bybit - processing the response
    r_bybit = await r_bybit
    predicted_bybit = -999

    for j in r_bybit.json()['result']:
        if j['symbol'] == 'BTCUSD':
            predicted_bybit = float(j['predicted_funding_rate'])
    # Bybit - end

    # Ftx - processing the response
    r_ftx = await r_ftx
    predicted_ftx = r_ftx.json()['result']['nextFundingRate']*8
    # Ftx - end

    # Okex - processing the response
    r_okex = await r_okex
    predicted_okex = float(r_okex.json()['estimated_rate'])
    # Okex - end

    average = (predicted_bybit + predicted_bitmex +
               predicted_ftx + predicted_okex)/4

    await ctx.send(
        "📈 **Predicted fundings** 📈\n" + "```" +
        "--> Bitmex     (XBTUSD): " + "{:7.4f}".format(predicted_bitmex * 100) + "%\n" +
        "--> Bybit      (BTCUSD): " + "{:7.4f}".format(predicted_bybit * 100) + "%\n" +
        "--> Okex (BTC-USD-SWAP): " + "{:7.4f}".format(predicted_okex * 100) + "%\n" +
        "--> FTX  (BTC-PERP)(*8): " + "{:7.4f}".format(predicted_ftx * 100) + "%\n" +
        "\n" +
        "==> Average: " + "{:.4f}".format(average * 100, 4) + "% <==```"
    )


@bot.command(name='fiat', brief="Display the asked fiat rate")
@commands.cooldown(10, 60, commands.BucketType.default)
async def fiat(ctx, arg='eurusd'):
    if(len(arg) == 6 and arg.isalpha()):
        try:
            arg = arg.upper()
            url = "https://api.exchangeratesapi.io/latest?base=" + arg[0:3]
            r = await requests.get(url)
            response = r.json()['rates'][arg[3:6]]
            await ctx.send("```The rate of " + arg[:6] + " is " + str(response) + "```")
        except:
            await ctx.send("```Rate not found, please retry```")
    else:
        await ctx.send_help(fiat)


@bot.group(name='lending', brief="Commands for the KuCoin Crypto Lending USDT section", aliases=['l'])
@commands.cooldown(10, 60, commands.BucketType.default)
async def lending(ctx):
    if ctx.invoked_subcommand == None:
        await ctx.send_help(lending)


@lending.command(name='orderbook', brief="Display a graph of the order book", aliases=['ob'])
async def lending_orderbook(ctx):
    chart_io_bytes = await ld.kucoin_lending_get_orderbook_graph(kucoin)
    chart = discord.File(chart_io_bytes, filename="orderbook.png")
    await ctx.send(file=chart)


@lending.command(name='walls', brief="Display the list of walls (up to 10) (minimum 100k)", aliases=['w'])
async def lending_walls(ctx, contract_term='all|t7|t14|t28', min_size='100'):
    matched_contract_term = re.search('^t(7|14|28)$', contract_term)
    if matched_contract_term:
        contract_term = matched_contract_term.group()
    else:
        contract_term = 'all'

    try:
        min_size = int(min_size)
    except ValueError:
        min_size = 100
    msg = await ld.kucoin_lending_get_walls(kucoin, min_size, contract_term)
    await ctx.send(msg)


@lending.command(name='reach', brief="How much needs to be borrowed to reach a specific rate", aliases=['r'])
async def lending_reach(ctx, arg='2.0'):
    try:
        rate_to_reach = float(arg)
    except ValueError:
        rate_to_reach = 2.0
    msg = await ld.kucoin_lending_reach_rate(kucoin, rate_to_reach)
    await ctx.send(msg)


@bot.group(name="location", brief="Commands related to the location", aliases=['loc'])
async def location(ctx):
    if ctx.invoked_subcommand == None:
        await ctx.send_help(location)


@location.command(name='town', brief="Use !town YOUR_TOWN to register where you live!")
async def town(ctx, *, arg=""):
    valid_town = await _town_name_valid(ctx, arg)
    if valid_town:
        author_id = str(ctx.author.id)
        try:
            with open("db.json", "r")as db:
                users = json.load(db)
                users.update({author_id: arg.capitalize()})

            with open("db.json", "w")as db:
                json.dump(users, db)

            await ctx.send("{} a été assigné à ton nom !".format(arg.capitalize()))

        except FileNotFoundError:
            with open("db.json", "w") as db:
                json.dump({author_id: arg.capitalize}, db)
            await ctx.send("Erreur")


@location.command(name="whoisat", brief="Enter a town name to see who is nearby!")
async def whoisat(ctx, *, arg="Paris"):
    valid_town = await _town_name_valid(ctx, arg)
    if valid_town:
        try:
            names_id = []
            with open("db.json", "r") as db:
                town = arg.capitalize()
                db_json = json.load(db)
                for name_id in db_json.keys():
                    if town == db_json[name_id]:
                        user = await bot.fetch_user(name_id)
                        names_id.append(user.name)
                if len(names_id) == 0:
                    await ctx.send(f"Personne n'a signalé habiter à {town}")
                else:
                    await ctx.send("Les personnes habitant à {} sont les suivantes : \n {}".format(town, "{}\n".join(names_id)))

        except FileNotFoundError:
            with open("db.json", "w") as db:
                json.dump({}, db)
            await ctx.send("Erreur")


async def _town_name_valid(ctx, town: str) -> bool:
    if len(town) < 1:
        await ctx.send("Town name should be more than 1 character long")
        return False
    elif re.search("[0-9]", town):
        await ctx.send("Please enter a valid town name!")
        return False
    else:
        return True


@location.command(name="where", brief="Use !where @NAME without the #")
async def where(ctx, *, arg="THISMA"):
    if "<@" in arg and "&" not in arg:
        called_id = arg.strip("<@!>")
        try:
            with open("db.json", "r") as db:
                users = json.load(db)
                if called_id in users:
                    sentence_draw = _random_commenting_sentence()
                    await ctx.send("{} habite à {}!\n {}".format(arg, users[called_id], sentence_draw))
                else:
                    await ctx.send("{} n'a pas donné sa liquidation! heu, sa ville!".format(arg))

        except FileNotFoundError:
            with open("db.json", 'w') as db:
                json.dump({}, db)
            await ctx.send("Erreur")

    else:
        await ctx.send("Merci de tagger le nom de la personne, exemple : !where @THISMA")


random_sentences = ["Ville des plus gros holders d'EOS", "La ville des adorateurs de $TONE", "aka lamboland", "Lieu préféré de THISMA le boss", "Lieu de pèlerinage TBF",
                    "Bapor le porc est passé par ici jadis", "L'endroit de liquidation préféré de ThOny", "Village préféré des francais!"]


def _random_commenting_sentence():
    from random import choice
    sentence_drawn = choice(random_sentences)
    return sentence_drawn


@funding.error
@fiat.error
@lending.error
@location.error
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        msg = ':exclamation: To avoid api congestion, this command is on cooldown, please try again in {:.2f}s :exclamation:'.format(
            error.retry_after)
        await ctx.reply(msg)


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------\n')

bot.run(TOKEN)
