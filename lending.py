import io
import pandas as pd
import matplotlib.pyplot as plt
from functools import reduce

plt.style.use('ggplot')

# Code par Wumos
async def get_orderbook_graph(kucoin):
    # GET ORDERBOOK
    res = kucoin.private_get_margin_market({'currency': 'USDT'})
    df = pd.DataFrame(res['data'])

    # ORDER BOOK DATAFRAME
    df['daily_rate'] = df['dailyIntRate'].astype(float)
    df['daily_rate'] = round(df['daily_rate']*100,1)
    df['size'] = df['size'].astype(float)

    # AGREGATION par daily_rate
    df_gr =df.groupby(['daily_rate']).agg({'size':'sum'})
    df_gr.reset_index(inplace=True)

    #plot
    fig,ax = plt.subplots(1)
    ax.barh(df_gr.daily_rate, width=df_gr['size'], height=0.1)
    ax.invert_xaxis()
    plt.title('Order Book Lending')
    plt.xlabel('USDT en millions')
    plt.ylabel('Taux % Journalier')

    # fig.savefig('order-book.png', dpi=1000)

    graph = io.BytesIO()
    fig.savefig(graph, dpi=400)
    graph.seek(0)
    return graph

def kucoin_lending_merge_interest_rate(orderbook):
    merged = {}
    for entry in orderbook:
        rate = entry['dailyIntRate']
        merged[rate] = merged.get(rate, 0) + int(entry['size'])

    return sorted(merged.items())

async def kucoin_lending_get_walls(kucoin, min_size, length=10):
    resp = kucoin.private_get_margin_market({'currency': 'USDT'})
    if resp['code'] != '200000':
        return f"KuCoin system error code: {resp['code']}"

    raw_walls = kucoin_lending_merge_interest_rate(resp['data'])
    walls = [f"- {float(rate) * 100:<5.3} :: {size:9,.0f} USDT"
             for (rate, size) in raw_walls if (size / 1000) >= min_size]
    return '''
KuCoin Crypto Lending USDT walls (minimum of {:d}k):
```
{}
```
'''.format(min_size,"\n".join(walls[:length]))

def kucoin_lending_reach_rate(kucoin, rate_to_reach: float):
    resp = kucoin.private_get_margin_market({'currency': 'USDT'})
    if resp['code'] != '200000':
        return f"KuCoin system error code: {resp['code']}"

    rates = kucoin_lending_merge_interest_rate(resp['data'])
    amounts = [size for (rate, size) in rates if (float(rate) * 100) <= rate_to_reach]
    total = reduce(lambda x, y: x+y, amounts)
    return f"`⟶ {rate_to_reach}%: {total:9,.0f} USDT needs to borrowed`"
