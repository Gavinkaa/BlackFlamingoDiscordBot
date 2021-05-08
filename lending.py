import io
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
from datetime import datetime
from functools import reduce
from math import floor

plt.style.use('ggplot')

# Code par @Zané
async def kucoin_lending_get_orderbook_graph(kucoin):
    resp = kucoin.private_get_margin_market({'currency': 'USDT'})

    df = pd.DataFrame(columns=['rate', 'size'])
    for i in resp['data']:
        if int(i['size']) > 50000:
            df = df.append({"rate":float(i['dailyIntRate']), "size": int(i['size'])}, ignore_index=True)

    df_terms_aggr = df.groupby(['rate']).sum()
    df_terms_aggr.reset_index(level=0, inplace=True)
    df_terms_aggr['rate'] = round(df_terms_aggr['rate']*100, 3)
    max_size = int(reduce(lambda x, y: max(x, y), df_terms_aggr['size'].values))
    number_length = len(str(int(max_size))) - 1
    max_height = (floor(max_size / (10 ** number_length)) + 1) * (10 ** number_length)

    plt.figure(figsize=(12,4))
    axes = plt.gca()
    axes.set_ylim([0, max_height])
    ax = sns.barplot(x="rate", y="size", data=df_terms_aggr)
    ax.set_xticklabels(ax.get_xticklabels(), rotation=40, ha="right")
    plt.title(f'KuCoin Lending Orderbook {datetime.now().strftime("%d/%m/%Y %Hh%M")}')

    graph = io.BytesIO()
    plt.savefig(graph, dpi=400)
    graph.seek(0)
    return graph

def _kucoin_lending_merge_interest_rate(orderbook):
    merged = {}
    for entry in orderbook:
        rate = entry['dailyIntRate']
        merged[rate] = merged.get(rate, 0) + int(entry['size'])

    return sorted(merged.items())

async def kucoin_lending_get_walls(kucoin, min_size, length=10):
    resp = kucoin.private_get_margin_market({'currency': 'USDT'})
    if resp['code'] != '200000':
        return f"KuCoin system error code: {resp['code']}"

    rates = _kucoin_lending_merge_interest_rate(resp['data'])
    walls = [f"⟶ {float(rate) * 100:<5.3} :: {size:9,.0f} USDT"
             for (rate, size) in rates if (size / 1000) >= min_size]
    return '''
KuCoin Crypto Lending USDT walls (minimum of {:d}k):
```
{}
```
'''.format(min_size,"\n".join(walls[:length]))

async def kucoin_lending_reach_rate(kucoin, rate_to_reach: float):
    resp = kucoin.private_get_margin_market({'currency': 'USDT'})
    if resp['code'] != '200000':
        return f"KuCoin system error code: {resp['code']}"

    rates = _kucoin_lending_merge_interest_rate(resp['data'])
    amounts = [size for (rate, size) in rates if (float(rate) * 100) <= rate_to_reach]
    total = 0
    if len(amounts):
        total = reduce(lambda x, y: x+y, amounts)
    return f"`⟶ {rate_to_reach}%: {total:9,.0f} USDT needs to be borrowed`"
