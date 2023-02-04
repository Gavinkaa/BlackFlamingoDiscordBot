import json
import re


import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, date


import ccxt
import dateutil.parser
import discord

import interactions
import requests_async as requests

from dateutil import tz

import lending as ld
from decorator import *
from eco_calendar import Event

with open("config.json") as config_file:
    config = json.load(config_file)

TOKEN = config['discord_token']

kucoin = ccxt.kucoin({
    "apiKey": "nope",
    "secret": 'nope',
    "password": "nope",
    'enableRateLimit': True,
})

intents = discord.Intents.all()

# bot = commands.Bot(command_prefix='!',
#                    help_command=help_command, intents=intents)
bot = interactions.Client(token=TOKEN, intents=interactions.Intents.ALL)
bot.load('interactions.ext.files')  # Load extension for files uploading.


# Can dispose of extension when upgrading to interactions 4.4 (not available on pip yet)


@bot.command(name='funding')
async def funding(ctx):
    pass


@funding.subcommand(name="bitmex", description="Display the actual and the predicted funding from bitmex")
@cooldown(60, 10)  # have to be on the first layer of decorator
async def funding_bitmex(ctx):
    url = "https://www.bitmex.com/api/v1/instrument?symbol=XBTUSD&count=1&reverse=true"
    try:
        r = urllib.request.urlopen(url, timeout=3)
        request_json = json.loads(r.read().decode())
        actual_funding = request_json[0]['fundingRate']
        next_funding = request_json[0]['indicativeFundingRate']

        funding_timestamp = dateutil.parser.parse(request_json[0]['fundingTimestamp'])
        funding_timestamp = funding_timestamp.astimezone(
            tz=tz.gettz("Europe/Paris"))

        next_funding_timestamp = (funding_timestamp + timedelta(hours=8))

        message = "The next funding event is at " + \
                  funding_timestamp.strftime("%I:%M:%S %p (%Z)") + \
                  ".\n📈 The rate is " + str(round(actual_funding * 100, 4)) + "% 📈\n\n" + \
                  "The predicted funding event is at " + \
                  next_funding_timestamp.strftime("%I:%M:%S %p (%Z)") + \
                  ".\n📈 The rate is " + str(round(next_funding * 100, 4)) + "% 📈"
    except:
        message = "The funding rate could not be retrieved. Please try again later."
    await ctx.send(message)



@funding.subcommand(name="predicted", description="Display the predicted funding from several exchanges")
@cooldown(60, 10)  # have to be on the first layer of decorator
async def funding_predicted(ctx):
    list_of_requests_to_send = []
    # First we send all the requests
    url_bitmex = "https://www.bitmex.com/api/v1/instrument?symbol=XBTUSD&count=1&reverse=true"
    list_of_requests_to_send.append(('bitmex', url_bitmex))

    url_bybit = "https://api.bybit.com/v2/public/tickers"
    list_of_requests_to_send.append(('bybit', url_bybit))
    
    url_okex = "https://www.okex.com/api/swap/v3/instruments/BTC-USD-SWAP/funding_time"
    list_of_requests_to_send.append(('okex', url_okex))

    def get_response_json(to_request):
        """
        Do a request to the url and return the json if the request is successful else return None
        """

        exchange_name, url = to_request

        try:
            pre_request = urllib.request.Request(url, headers={
                'User-Agent': 'Mozilla/5.0'})
            request = urllib.request.urlopen(pre_request, timeout=3)
            request_json = json.loads(request.read().decode())
            return exchange_name, request_json
        except Exception as e:
            print(exchange_name + ": " + str(e))
            return exchange_name, None

    with ThreadPoolExecutor(max_workers=4) as pool:
        response_list = list(pool.map(get_response_json, list_of_requests_to_send))
    response_dict = {exchange_name: response_json for exchange_name, response_json in response_list}

    nb_fundings = 0
    total_funding_predicted = 0

    # Bitmex - processing the response
    try:
        predicted_bitmex = response_dict['bitmex'][0]['indicativeFundingRate']
        bitmex_percentage = "{:7.4f}%".format(predicted_bitmex * 100)

        nb_fundings += 1
        total_funding_predicted += predicted_bitmex
    except:
        bitmex_percentage = "Could not retrieve the funding rate from bitmex"
    # Bitmex - end
    print(bitmex_percentage)

    # Bybit - processing the response
    try:
        predicted_bybit = None

        for j in response_dict['bybit']['result']:
            if j['symbol'] == 'BTCUSD':
                predicted_bybit = float(j['predicted_funding_rate'])

        nb_fundings += 1
        total_funding_predicted += predicted_bybit
    except:
        predicted_bybit = None

    if predicted_bybit is None:
        bybit_percentage = "Could not retrieve the funding rate from bybit"
    else:
        bybit_percentage = "{:7.4f}%".format(predicted_bybit * 100)
    # Bybit - end
    print(bybit_percentage)

    # Okex - processing the response
    try:
        predicted_okex = response_dict['okex']['funding_rate']
        okex_percentage = "{:7.4f}%".format(predicted_okex * 100)

        nb_fundings += 1
        total_funding_predicted += predicted_okex
    except:
        okex_percentage = "Could not retrieve the funding rate from okex"
    # Okex - end
    print(okex_percentage)

    average = "{:7.4f}%".format(
        total_funding_predicted / nb_fundings * 100) if nb_fundings > 0 else "Could not retrieve the average"

    await ctx.send(
        "📈 **Predicted fundings** 📈\n" + "```" +
        "--> Bitmex     (XBTUSD): " + bitmex_percentage + "\n" +
        "--> Bybit      (BTCUSD): " + bybit_percentage + "\n" +
        "--> Okex (BTC-USD-SWAP): " + okex_percentage + "\n"+
        "\n" +
        "==> Average: " + average + " <==```"
        )


@bot.command(name='lending', description="Commands for the KuCoin Crypto Lending USDT section")
@cooldown(60, 10)
async def lending(ctx):
    pass


@lending.subcommand(name="orderbook", description="Display a graph of the order book")
@cooldown(60, 10)  # have to be on the first layer of decorator
async def lending_orderbook(ctx: interactions.CommandContext):
    chart_io_bytes = await ld.kucoin_lending_get_orderbook_graph(kucoin)
    chart = interactions.File(fp=chart_io_bytes, filename="orderbook.png")
    await ctx.send(files=chart)


@lending.subcommand(name="walls",
                    description="Display the list of walls (up to 10) (minimum 100k)",
                    options=[
                        interactions.Option(
                            name="contract_term",
                            description="contract term (all - t7 - t14 - t28)",
                            type=interactions.OptionType.STRING,
                            required=False
                        ),
                        interactions.Option(
                            name="min_size",
                            description="minimum size (>100k)",
                            type=interactions.OptionType.INTEGER,
                            required=False
                        )
                    ])
@cooldown(60, 10)  # have to be on the first layer of decorator
async def lending_walls(ctx, contract_term='all|t7|t14|t28', min_size=100):
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


@lending.subcommand(name="reach",
                    description="How much needs to be borrowed to reach a specific rate",
                    options=[
                        interactions.Option(
                            name="rate",
                            description="rate to reach",
                            type=interactions.OptionType.STRING,
                            required=False
                        )
                    ])
@cooldown(60, 10)  # have to be on the first layer of decorator
async def lending_reach(ctx, rate='2.0'):
    try:

        rate_to_reach = float(rate)
        print(rate)
    except ValueError:
        rate_to_reach = 2.0
    msg = await ld.kucoin_lending_reach_rate(kucoin, rate_to_reach)
    await ctx.send(msg)


@bot.command(name="location", description="Commands related to the location")
async def location(ctx):
    pass


@location.subcommand(name="choose-my-town",
                     description="Register where you live!",
                     options=[
                         interactions.Option(
                             name="town",
                             description="your town",
                             type=interactions.OptionType.STRING,
                             required=True
                         )
                     ])
async def choose_my_town(ctx, town):
    valid_town = await _town_name_valid(ctx, town)
    if valid_town:
        author_id = str(ctx.author.id)
        try:
            with open("users_location.json", "r") as db:
                users = json.load(db)
                users.update({author_id: town.capitalize()})

            with open("users_location.json", "w") as db:
                json.dump(users, db)

            await ctx.send("{} a été assigné à ton nom !".format(town.capitalize()))

        except FileNotFoundError:
            with open("users_location.json", "w") as db:
                json.dump({author_id: town.capitalize}, db)
            await ctx.send("Erreur")


@location.subcommand(name="who-is-at",
                     description="Enter a town name to see who is nearby!",
                     options=[
                         interactions.Option(
                             name="town",
                             description="the town to check",
                             type=interactions.OptionType.STRING,
                             required=True
                         )
                     ])
async def who_is_at(ctx, town):
    valid_town = await _town_name_valid(ctx, town)
    if valid_town:
        try:
            names_id = []
            with open("users_location.json", "r") as db:
                town = town.capitalize()
                db_json = json.load(db)
                for name_id in db_json.keys():
                    if town == db_json[name_id]:
                        user = await bot.guilds[0].get_member(int(name_id))
                        names_id.append(user.name)
                if len(names_id) == 0:
                    await ctx.send(f"Personne n'a signalé habiter à {town}")
                else:
                    await ctx.send(
                        "Les personnes habitant à {} sont les suivantes : \n{}".format(town, "\n".join(names_id)))


        except FileNotFoundError:
            with open("users_location.json", "w") as db:
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


@location.subcommand(name="where",
                     description="Check where @user lives",
                     options=[
                         interactions.Option(
                             name="user",
                             description="the user to check",
                             type=interactions.OptionType.USER,
                             required=True
                         )
                     ])
async def where(ctx, user: interactions.Member):
    username = "<@!" + str(user.id) + ">"
    if "<@" in username and "&" not in username:
        called_id = username.strip("<@!>")
        try:
            with open("users_location.json", "r") as db:
                users = json.load(db)
                if called_id in users:
                    sentence_draw = _random_commenting_sentence()
                    await ctx.send("{} habite à {}!\n {}".format(username, users[called_id], sentence_draw))
                else:
                    await ctx.send("{} n'a pas donné sa liquidation! heu, sa ville!".format(username))

        except FileNotFoundError:
            with open("users_location.json", 'w') as db:
                json.dump({}, db)
            await ctx.send("Error")

    else:
        await ctx.send("Merci de tagger le nom de la personne, exemple : !where @THISMA")


random_sentences = ["Ville des plus gros holders d'EOS", "La ville des adorateurs de $TONE", "aka lamboland",
                    "Lieu préféré de THISMA le boss", "Lieu de pèlerinage TBF",
                    "Bapor le porc est passé par ici jadis", "L'endroit de liquidation préféré de ThOny",
                    "Village préféré des francais!"]


def _random_commenting_sentence():
    from random import choice
    sentence_drawn = choice(random_sentences)
    return sentence_drawn


@bot.command(name='calendar', description="Commands for the economic calendar section")
async def calendar(ctx):
    pass


@calendar.subcommand(name="economic_events",
                     description="Output the official economic calendar for US and EUROPE",
                     options=[
                         interactions.Option(
                             name='nb_days',
                             description="Number of days ahead you want to fetch, default 7, max 30",
                             type=interactions.OptionType.INTEGER,
                             required=False
                         )
                     ])
async def economic_events(ctx: interactions.CommandContext, nb_days: int = 7):
    if nb_days > 30:
        nb_days = 30
    # Get events from investing.com, returns list of days {timestamp:,events:}
    events_html = Event.fetch_events(date.today(), date.today() + timedelta(days=nb_days))
    events = (Event.parse_events(events_html))
    events_embed = Event.embed_events(events)
    await ctx.send(events_embed)


@funding.error
@lending.error
@location.error
async def on_command_error(ctx, error):
    if isinstance(error, OnCooldownError):
        msg = ':exclamation: To avoid api congestion, this command is on cooldown, please try again in {:.2f}s :exclamation:'.format(
            error.retry_after)
        await ctx.reply(msg)
    else:
        print(error)
        await ctx.send('Error, please contact mod or admin')


@bot.event
async def on_bot_command_error(ctx, error):
    if isinstance(error, OnCooldownError):
        msg = ':exclamation: To avoid api congestion, this command is on cooldown, please try again in {:.2f}s :exclamation:'.format(
            error.retry_after)
        await ctx.reply(msg)


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.get_self_user())
    print(bot.user.id)
    print('------\n')


bot.start()
