import time
import requests_async as requests
from datetime import datetime, timezone, timedelta
import dateutil.parser
from dateutil import tz
import discord
from discord.ext import commands
import hmac
import json
import ccxt
import lending as ld


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

bot = commands.Bot(command_prefix='!', help_command=help_command)


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
async def lending_walls(ctx, arg='100'):
    try:
        min_size = int(arg)
    except ValueError:
        min_size = 100
    msg = await ld.kucoin_lending_get_walls(kucoin, min_size)
    await ctx.send(msg)


@lending.command(name='reach', brief="How much needs to be borrowed to reach a specific rate", aliases=['r'])
async def lending_reach(ctx, arg='2.0'):
    try:
        rate_to_reach = float(arg)
    except ValueError:
        rate_to_reach = 2.0
    msg = ld.kucoin_lending_reach_rate(kucoin, rate_to_reach)
    await ctx.send(msg)


@funding.error
@fiat.error
@lending.error
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
