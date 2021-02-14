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
import lending


with open("config.json") as config_file:
    config = json.load(config_file)

TOKEN = config['discord_token']

kucoin = ccxt.kucoin({
    "apiKey": "nope",
    "secret": 'nope',
    "password": "nope",
    'enableRateLimit': True,
})

bot = commands.Bot(command_prefix='!', help_command=None)


@bot.command(name='funding', description="Display the actual and the predicted funding from bitmex")
async def funding(ctx):
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


@bot.command(name='predicted', description="Display the predicted funding from several exchanges")
async def funding(ctx):
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


@bot.command(name='fiat', description="Display the asked rate")
async def fiat(ctx, arg):
    if(len(arg) == 6, arg.isalpha()):
        try:
            arg = arg.upper()
            url = "https://api.exchangeratesapi.io/latest?base=" + arg[0:3]
            r = await requests.get(url)
            response = r.json()['rates'][arg[3:6]]
            await ctx.send("```The rate of " + arg[:6] + " is " + str(response) + "```")
        except:
            await ctx.send("```Rate not found, please retry```")
    else:
        await ctx.send("invalid request, please retry")

@bot.command(name='lending', description="Commands for the KuCoin Crypto Lending USDT section")
async def kucoin_lending(ctx, subcommand = 'help', arg = ''):
    if subcommand == 'orderbook' or subcommand == 'ob':
        chart_io_bytes = await lending.get_orderbook_graph(kucoin)
        chart = discord.File(chart_io_bytes, filename="orderbook.png")
        await ctx.send(file=chart)
    elif subcommand == 'walls':
        msg = await lending.kucoin_lending_get_walls(kucoin)
        await ctx.send("```This command will be implemented soon!```")
        # await ctx.send(msg)
    else:
        usage = '''
```
# Commands for the KuCoin Crypto Lending USDT section

## Display a graph of the order book
  !lending orderbook
  !lending ob

## Display the list of walls (minimum 250k)
  !lending walls
```
'''
        await ctx.send(usage)


@bot.event
async def on_ready():
    print('Logged in as')
    print(bot.user.name)
    print(bot.user.id)
    print('------\n')

bot.run(TOKEN)
