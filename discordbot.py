import asyncio
import io

import json
import math
import re
import time

import yaml
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta, date

import ccxt
import dateutil.parser
from discord import Intents

import interactions
from interactions import slash_command, slash_option, SlashContext, SlashCommandChoice, cooldown, Buckets, File

from dateutil import tz
from selenium.webdriver.support.wait import WebDriverWait

import lending as ld
from decorator import OnCooldownError
from eco_calendar import Event
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from dotenv import load_dotenv
import os
from dotenv import dotenv_values

# THISMA cfg
TOKEN = dotenv_values()['discord_token']  # For thisma the maxi bg
load_dotenv()

# LUDO cfg
# with open("config.json") as config_file:
#     config = json.load(config_file)
# TOKEN = config['discord_token']

kucoin = ccxt.kucoin({
    "apiKey": "nope",
    "secret": 'nope',
    "password": "nope",
    'enableRateLimit': True,
})

intents = Intents.all()

# bot = commands.Bot(command_prefix='!',
#                    help_command=help_command, intents=intents)

bot = interactions.Client(token=TOKEN, intents=interactions.Intents.ALL, send_command_tracebacks=False)


# bot.load('interactions.ext.files')  # Load extension for files uploading.


# Can dispose of extension when upgrading to interactions 4.4 (not available on pip yet)

@slash_command(name='coinalyze')
async def coinalyze(ctx):
    pass


@coinalyze.subcommand(sub_cmd_name="indicator",
                      sub_cmd_description="Display the actual aggregated fundings from exchanges")
@slash_option(name="indicator_type",
              description="Nom de l'indicateur à afficher",
              opt_type=interactions.OptionType.STRING,
              required=True,
              choices=[SlashCommandChoice(name="funding", value="funding"), SlashCommandChoice(name="oi", value="oi")])
@cooldown(Buckets.USER, 1, 20)  # have to be on the first layer of decorator
async def coinalyze_indicator(ctx, indicator_type: str):
    await ctx.defer()
    img = await get_coinalyze_data(indicator_type)
    if img:
        await ctx.send(file=File(io.BytesIO(img), "chart.png"))
    else:
        await ctx.send("Erreur lors de la récupération des données")


async def get_coinalyze_data(indicator_type: str):
    chrome_options = ChromeOptions()
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--headless")
    chrome_options.add_argument(
        "user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/114.0")
    driver = webdriver.Chrome(options=chrome_options)

    try:
        if indicator_type == "funding":
            url = "https://fr.coinalyze.net/bitcoin/funding-rate/"
        else:
            url = "https://fr.coinalyze.net/bitcoin/open-interest/"
        driver.get(url)
        await asyncio.sleep(5)
        widget_id = 'futures-data-tv-chart'
        widget = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, widget_id)))
        driver.execute_script("arguments[0].scrollIntoView();", widget)
        driver.implicitly_wait(3)
        img = widget.screenshot_as_png
        return img
    except Exception as e:
        print(e)
        driver.quit()
        return None


@slash_command(name='funding')
async def funding(ctx):
    pass


@funding.subcommand(sub_cmd_name="bitmex",
                    sub_cmd_description="Display the actual and the predicted funding from bitmex")
@cooldown(Buckets.USER, 1, 20)  # have to be on the first layer of decorator
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


@funding.subcommand(sub_cmd_name="predicted",
                    sub_cmd_description="Display the predicted funding from several exchanges")
@cooldown(Buckets.USER, 1, 20)  # have to be on the first layer of decorator
async def funding_predicted(ctx):
    list_of_requests_to_send = []
    # First we send all the requests
    url_bitmex = "https://www.bitmex.com/api/v1/instrument?symbol=XBTUSD&count=1&reverse=true"
    list_of_requests_to_send.append(('bitmex', url_bitmex))

    # No predicted funding in the API anymore...
    # url_bybit = "https://api.bybit.com/derivatives/v3/public/funding/history-funding-rate?symbol=BTCUSD&category=linear"
    # list_of_requests_to_send.append(('bybit', url_bybit))

    url_okex = "https://www.okx.com/api/v5/public/funding-rate?instId=BTC-USD-SWAP"
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
    # print(bitmex_percentage)

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

    # Okex - processing the response
    try:
        predicted_okex = None
        symbols_okex = response_dict['okex']['data']
        for symbol in symbols_okex:

            if symbol['instId'] == 'BTC-USD-SWAP':
                predicted_okex = float(symbol['nextFundingRate'])
                nb_fundings += 1
                total_funding_predicted += predicted_okex


    except:
        predicted_okex = None
    if predicted_okex is None:
        okex_percentage = "Could not retrieve the funding rate from okex"
    else:
        okex_percentage = "{:7.4f}%".format(predicted_okex * 100)
    # Okex - end

    average = "{:7.4f}%".format(
        total_funding_predicted / nb_fundings * 100) if nb_fundings > 0 else "Could not retrieve the average"

    await ctx.send(
        "📈 **Predicted fundings** 📈\n" + "```" +
        "--> Bitmex     (XBTUSD): " + bitmex_percentage + "\n" +
        "--> Okex (BTC-USD-SWAP): " + okex_percentage + "\n" +
        "\n" +
        "==> Average: " + average + " <==```"
    )


@slash_command(name='lending', description="Commands for the KuCoin Crypto Lending USDT section")
@cooldown(Buckets.USER, 1, 20)
async def lending(ctx):
    pass


@lending.subcommand(sub_cmd_name="orderbook", sub_cmd_description="Display a graph of the order book")
@cooldown(Buckets.USER, 1, 20)  # have to be on the first layer of decorator
async def lending_orderbook(ctx: SlashContext):
    chart_io_bytes = await ld.kucoin_lending_get_orderbook_graph(kucoin)
    chart = interactions.File(file=chart_io_bytes, file_name="orderbook.png")
    await ctx.send(files=chart)


@lending.subcommand(sub_cmd_name="walls",
                    sub_cmd_description="Display the list of walls (up to 10) (minimum 100k)",
                    )
@slash_option(name="contract_term",
              description="contract term (all - t7 - t14 - t28)",
              opt_type=interactions.OptionType.STRING,
              required=False)
@slash_option(name="min_size",
              description="minimum size (>100k)",
              opt_type=interactions.OptionType.INTEGER,
              required=False)
@cooldown(Buckets.USER, 1, 20)  # have to be on the first layer of decorator
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


@lending.subcommand(sub_cmd_name="reach",
                    sub_cmd_description="How much needs to be borrowed to reach a specific rate", )
@slash_option(name="rate",
              description="rate to reach",
              opt_type=interactions.OptionType.STRING,
              required=False)
@cooldown(Buckets.USER, 1, 20)  # have to be on the first layer of decorator
async def lending_reach(ctx, rate='2.0'):
    try:

        rate_to_reach = float(rate)
    except ValueError:
        rate_to_reach = 2.0
    msg = await ld.kucoin_lending_reach_rate(kucoin, rate_to_reach)
    await ctx.send(msg)


@slash_command(name="location", description="Commands related to the location")
async def location(ctx):
    pass


@location.subcommand(sub_cmd_name="choose-my-town",
                     sub_cmd_description="Register where you live!",
                     )
@slash_option(name="town",
              description="your town",
              opt_type=interactions.OptionType.STRING,
              required=True)
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


@location.subcommand(sub_cmd_name="who-is-at",
                     sub_cmd_description="Enter a town name to see who is nearby!",
                     )
@slash_option(name="town",
              description="the town to check",
              opt_type=interactions.OptionType.STRING,
              required=True)
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
                        guild = ctx.guild
                        member = guild.get_member(int(name_id))
                        # If user left guild, wont be found in get member
                        if member:
                            names_id.append(member.user.username + '#' + member.user.discriminator)

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


@location.subcommand(sub_cmd_name="where",
                     sub_cmd_description="Check where @user lives",
                     )
@slash_option(name="user",
              description="the user to check",
              opt_type=interactions.OptionType.USER,
              required=True)
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


@slash_command(name='calendar', description="Commands for the economic calendar section")
async def calendar(ctx):
    pass


@calendar.subcommand(sub_cmd_name="economic_events",
                     sub_cmd_description="Output the official economic calendar for US and EUROPE")
@cooldown(Buckets.USER, 1, 20)
async def economic_events(ctx: SlashContext):
    # Get events from investing.com, returns list of days {timestamp:,events:}
    events_html = Event.fetch_events(date.today(), date.today() + timedelta(days=7))
    events = (Event.parse_events(events_html))
    events_embed = Event.embed_events(events)
    await ctx.send(events_embed)


@slash_command(name='copy', description="Commands for the funding section")
async def copy(ctx):
    pass


@copy.subcommand(sub_cmd_name="size",
                 sub_cmd_description="Calculer la taille de position optimale pour le copy trading Bitget")
@slash_option(name="bot_name",
              description="Nom du bot à copier",
              opt_type=interactions.OptionType.STRING,
              required=True,
              choices=[SlashCommandChoice(name="alphabot", value="alphabot")])
@slash_option(name="capital_user",
              description="Capital total que vous souhaitez dédier au copy trading",
              required=True,
              opt_type=interactions.OptionType.INTEGER)
@slash_option(name="dd_max_user",
              description="Drawdown maximal sur votre capital, doit etre inférieur à 60%. Par défaut 30%",
              required=False,
              opt_type=interactions.OptionType.INTEGER)
@cooldown(Buckets.USER, 1, 20)
async def size(ctx: SlashContext, capital_user: int, dd_max_user: int = 30, bot_name: str = "alphabot"):
    with open('copy_bot_settings.yaml', 'r') as bot_settings:
        donnees = yaml.load(bot_settings, Loader=yaml.FullLoader)
        if bot_name not in donnees:
            raise ValueError("Bot name not found in settings file, dev error")

    dd_max_bot = donnees[bot_name]["maxDD"]
    capital_bot = donnees[bot_name]["capital"]
    smallest_position_size_bot = donnees[bot_name]["smallestPositionSize"]

    if dd_max_user > 60:
        await ctx.send("Le drawdown maximal doit être inférieur à 60%")
        return

    if dd_max_user < 0:
        await ctx.send("Le drawdown maximal doit être supérieur à 0%")
        return

    if capital_user < 100:
        await ctx.send("Le capital total doit être supérieur à 100")
        return

    multiplier = (capital_user / capital_bot) * (dd_max_user / dd_max_bot)

    if multiplier * smallest_position_size_bot < 100:
        await ctx.send(
            "Le capital total est trop faible pour le drawdown maximal choisi, une position doit etre supérieure à 100$")
        return

    await ctx.send("Vos réglages optimaux pour le copy trading Bitget sont les suivants (Cliquer sur Advanced) : \n"
                   "Margin mode : Copy margin\n"
                   "Leverage : Specified leverage : 15 short et long\n"
                   "Copy mode : Multiplier avec un multiplier de {:.2f}\n".format(multiplier))


@slash_command(name='calls', description="Commands for the calls section")
async def calls(ctx):
    pass


@calls.subcommand(sub_cmd_name="new_trade", sub_cmd_description="Ajouter un nouveau trade")
@slash_option(name="pair",
              description="pair du trade (ex: BTC/USDT)",
              opt_type=interactions.OptionType.STRING,
              required=True)
@slash_option(name="trade_direction",
              description="direction du trade",
              opt_type=interactions.OptionType.STRING,
              required=True,
              choices=[SlashCommandChoice(name="long", value="long"), SlashCommandChoice(name="short", value="short")])
@slash_option(name="index",
              description="index du trade dans le canal",
              opt_type=interactions.OptionType.INTEGER,
              required=True)
@slash_option(name="entry_price",
              description="prix d'entrée du trade",
              opt_type=interactions.OptionType.NUMBER,
              required=True)
@slash_option(name="tp_price",
              description="prix du take profit",
              opt_type=interactions.OptionType.NUMBER,
              required=True)
@slash_option(name="sl_price",
              description="prix du stop loss",
              opt_type=interactions.OptionType.NUMBER,
              required=True)
@slash_option(name="success_estimation",
              description="estimation de la probabilité d'atteindre le tp (en %)",
              opt_type=interactions.OptionType.NUMBER,
              required=True)
@slash_option(name="screenshot",
              description="screenshot du trade",
              opt_type=interactions.OptionType.ATTACHMENT,
              required=False)
async def new_trade(ctx, pair, trade_direction, index, entry_price, tp_price, sl_price, success_estimation,
                    screenshot=None):
    pair = pair.Upper()
    rr = (tp_price - entry_price) / (entry_price - sl_price)
    tp_perc = abs((tp_price - entry_price) / entry_price * 100)
    sl_perc = -abs((sl_price - entry_price) / entry_price * 100)
    ev = tp_perc / 100 * success_estimation / 100 + sl_perc / 100 * (100 - success_estimation / 100)
    embed = interactions.Embed(title="{} - {} - #{}".format(pair, trade_direction, index),
                               description="Trade ajouté par {}".format(ctx.author.display_name),
                               color='588157' if trade_direction == "long" else 'c1121f')
    embed.add_field(name="Entry price", value=entry_price)
    embed.add_field(name="Take profit", value="{} - {}".format(tp_price, tp_perc))

    embed.add_field(name="Stop loss",
                    value="{} / {}%".format(sl_price, sl_perc))
    embed.add_field(name="RR / EV", value="{} / {}".format(rr, ev))
    # embed.set_image(screenshot)
    await ctx.send(embed=embed)


@calls.subcommand(sub_cmd_name="position_adjustment", sub_cmd_description="Ajouter un ajustement de position")
@slash_option(name="pair",
              description="pair du trade (ex: BTC/USDT)",
              opt_type=interactions.OptionType.STRING,
              required=True)
@slash_option(name="trade_direction",
              description="direction du trade",
              opt_type=interactions.OptionType.STRING,
              required=True,
              choices=[SlashCommandChoice(name="long", value="long"),
                       SlashCommandChoice(name="short", value="short")])
@slash_option(name="index",
              description="index du trade dans le canal",
              opt_type=interactions.OptionType.NUMBER,
              required=True)
@slash_option(name="position_operation",
              description="opération d'ajustement de position",
              opt_type=interactions.OptionType.STRING,
              required=True,
              choices=[SlashCommandChoice(name="addition", value="addition"),
                       SlashCommandChoice(name="reduction", value="réduction")])
@slash_option(name="operation_size",
              description="taille de l'opération",
              opt_type=interactions.OptionType.NUMBER,
              required=True)
@slash_option(name="adjustment_price",
              description="prix d'ajustement",
              opt_type=interactions.OptionType.NUMBER,
              required=True)
@slash_option(name="reason",
              description="raison de l'ajustement",
              opt_type=interactions.OptionType.STRING,
              required=True)
async def position_adjustment(ctx, pair, trade_direction, index, position_operation, operation_size, adjustment_price,
                              reason):
    pair = pair.Upper()
    embed = interactions.Embed(title="{} - {} - #{}".format(pair, trade_direction, index),
                               description="Ajustement de position ajouté par {}".format(ctx.author.display_name),
                               color='588157' if trade_direction == "long" else 'c1121f')
    embed.add_field(name="Opération", value="{} / {}".format(position_operation, operation_size))
    embed.add_field(name="Prix d'ajustement", value=adjustment_price)
    embed.add_field(name="Raison", value=reason)
    await ctx.send(embed=embed)


@calls.subcommand(sub_cmd_name="position_summary", sub_cmd_description="Ajouter un résumé de position")
@slash_option(name="pair",
              description="pair du trade (ex: BTC/USDT)",
              opt_type=interactions.OptionType.STRING,
              required=True)
@slash_option(name="trade_direction",
              description="direction du trade",
              opt_type=interactions.OptionType.STRING,
              required=True,
              choices=[SlashCommandChoice(name="long", value="long"),
                       SlashCommandChoice(name="short", value="short")])
@slash_option(name="index",
              description="index du trade dans le canal",
              opt_type=interactions.OptionType.NUMBER,
              required=True)
@slash_option(name="profit_loss_in_perc",
              description="profit/loss en pourcentage",
              opt_type=interactions.OptionType.NUMBER,
              required=True)
@slash_option(name="profit_loss_in_r",
              description="profit/loss en R",
              opt_type=interactions.OptionType.NUMBER,
              required=True)
@slash_option(name="comment",
              description="commentaire",
              opt_type=interactions.OptionType.STRING,
              required=True)
async def position_summary(ctx, pair, trade_direction, index, profit_loss_in_perc, profit_loss_in_r, comment):
    pair = pair.Upper()
    embed = interactions.Embed(title="{} - {} - #{}".format(pair, trade_direction, index),
                               description="Ajustement de position ajouté par {}".format(ctx.author.display_name),
                               color='588157' if trade_direction == "long" else 'c1121f')
    embed.add_field(name="Profit/Loss", value="{}% / {}R".format(profit_loss_in_perc, profit_loss_in_r))
    embed.add_field(name="Commentaire", value=comment)
    await ctx.send(embed=embed)


@funding.error
@lending.error
@location.error
@calendar.error
async def on_command_error(ctx, error):
    if isinstance(error, OnCooldownError):
        msg = ':exclamation: To avoid api congestion, this command is on cooldown, please try again in {:.2f}s :exclamation:'.format(
            error.retry_after)
        await ctx.reply(msg)
    else:
        print(error)
        await ctx.send('Error, please contact mod or admin')


@interactions.listen()
async def on_bot_command_error(ctx, error):
    if isinstance(error, OnCooldownError):
        msg = ':exclamation: To avoid api congestion, this command is on cooldown, please try again in {:.2f}s :exclamation:'.format(
            error.retry_after)
        await ctx.reply(msg)
    else:
        print(error)
        await ctx.send('Error, please contact mod or admin')


@interactions.listen()
async def on_ready(event):
    print(f'Connected to {bot.guilds}')
    print(f'Logged in as {bot.user.username} (ID: {bot.user.id})')


bot.start()
