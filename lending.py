import io
from datetime import datetime
from decimal import Decimal
from functools import reduce
from math import floor

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from tabulate import tabulate

TERM_TO_STR = {'all': 'all',
               't7': '7 days',
               't14': '14 days',
               't28': '28 days'}

plt.style.use('ggplot')


# Code par @Zané
async def kucoin_lending_get_orderbook_graph(kucoin):
    resp = kucoin.private_get_margin_market({'currency': 'USDT'})

    df = pd.DataFrame(columns=['rate', 'size'])
    for i in resp['data']:
        if int(i['size']) > 50000:
            df = df.append({"rate": float(i['dailyIntRate']), "size": int(i['size'])}, ignore_index=True)

    df_terms_aggr = df.groupby(['rate']).sum()
    df_terms_aggr.reset_index(level=0, inplace=True)
    df_terms_aggr['rate'] = round(df_terms_aggr['rate'] * 100, 3)
    max_size = int(reduce(lambda x, y: max(x, y), df_terms_aggr['size'].values))
    number_length = len(str(int(max_size))) - 1
    max_height = (floor(max_size / (10 ** number_length)) + 1) * (10 ** number_length)

    plt.figure(figsize=(12, 4))
    axes = plt.gca()
    axes.set_ylim([0, max_height])
    ax = sns.barplot(x="rate", y="size", data=df_terms_aggr)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=40, ha="right")
    plt.title(f'KuCoin Lending Orderbook {datetime.now().strftime("%d/%m/%Y %Hh%M")}')

    graph = io.BytesIO()
    plt.savefig(graph, dpi=400)
    graph.seek(0)
    return graph


def _kucoin_lending_fetch_all_contract_term(kucoin):
    # Data format: {'dailyIntRate': '0.00139', 'term': 7, 'size': '11740'}
    resp = kucoin.private_get_margin_market({'currency': 'USDT'})
    if resp['code'] != '200000':
        return f"Error while fetching lending market data: {resp['code']}"

    orderbook = resp['data']
    merged = {}
    for entry in orderbook:
        rate = entry['dailyIntRate']
        merged[rate] = merged.get(rate, 0) + int(entry['size'])

    rates = [{'dailyIntRate': Decimal(rate), 'size': size} for (rate, size) in merged.items()]
    return sorted(rates, key=lambda entry: entry['dailyIntRate'])


def _kucoin_lending_fetch_by_contract_term(kucoin, contract_term: int):
    resp = kucoin.private_get_margin_market({'currency': 'USDT', 'term': contract_term})
    if resp['code'] != '200000':
        return f"Error while fetching lending market by contract term: {resp['code']}"

    return [{'dailyIntRate': Decimal(entry['dailyIntRate']), 'size': int(entry['size'])}
            for entry in resp['data']]


def _kucoin_lending_format_rates(rates: list, min_size: int):
    return [(f"{entry['dailyIntRate'] * 100:<5.3}",
             f"{entry['size']:9,.0f} USDT")
            for entry in rates if (entry['size'] / 1000) >= min_size]


async def kucoin_lending_get_walls(kucoin, min_size: int, contract_term: str, length=10):
    # Rates format: [{'dailyIntRate': Decimal('0.00139'), 'size': 11740}, ...]
    if contract_term == 'all':
        fetched_rates = _kucoin_lending_fetch_all_contract_term(kucoin)
    else:
        fetched_rates = _kucoin_lending_fetch_by_contract_term(kucoin, contract_term[1:])

    formatted_rates = _kucoin_lending_format_rates(fetched_rates, min_size)
    table = tabulate(formatted_rates[:length], ("Rate", "Amount in USDT"), tablefmt='presto', stralign='right')
    return '''
KuCoin Crypto Lending USDT walls for **{}** contract term (minimum of {:d}k):
```
{}
```
'''.format(TERM_TO_STR[contract_term], min_size, table)


async def kucoin_lending_reach_rate(kucoin, rate_to_reach: float):
    rates = _kucoin_lending_fetch_all_contract_term(kucoin)
    amounts = [entry['size'] for entry in rates if (entry['dailyIntRate'] * 100) <= rate_to_reach]
    total = 0
    if len(amounts):
        total = reduce(lambda x, y: x + y, amounts)
    return f"`⟶ {rate_to_reach}%: {total:9,.0f} USDT needs to be borrowed`"
