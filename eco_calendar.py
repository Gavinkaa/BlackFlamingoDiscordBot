from datetime import datetime, timedelta, date

import requests
from pyquery import PyQuery as pq
import httpx
import re
from lxml import html as lh
import discord

class Event:
    def __init__(self, time, country, sentiment, name, actual, forecast, previous):
        self.time = time
        self.country = country
        self.sentiment = sentiment
        self.name = name
        self.actual = actual
        self.forecast = forecast
        self.previous = previous

    @classmethod
    def embed_events(cls,events:list):
        header_str = f"{'Time':5}  {'Country':15}  {'Event':25}  {'Actual':8}  {'Forecast':8}  {'Previous':8}\n"
        events_str = ""
        for day in events:
            events_str += f"====== {day['event_day']} ======\n"
            events_str += "".join([str(event) for event in day['events']])
        print(header_str+events_str)
        embed = discord.Embed(title='Calendrier économique', color=discord.Color.blue())
        # TODO finish embed, only display possible is in bot commands

    @classmethod
    def parse_events(cls,html: lh) -> list:
        #TODO just use lxml, no need for pyquery...

        all_events = []
        day_events = {'event_day': None, 'events': []}
        for event in html.iter('tr'):
            if len(event.getchildren())==1:
                # Empty on first day, otherwise add previous days.
                if day_events['events']:
                    all_events.append(day_events)
                    day_events = {'event_day': None, 'events': []}

            elif 'event_attr_id' in event.attrib:
                #TODO convert date to CET (add time filter in request)
                event_datetime = datetime.fromisoformat(event.attrib['data-event-datetime'].replace('/','-').replace(' ','T'))
                day_events['event_day'] = event_datetime.date()
                event_rows = event.getchildren()
                time = event_datetime.time().strftime("%H:%M")
                country = event_rows[1].find('span').attrib['title']
                sentiment = event_rows[2].attrib['title']
                name = event_rows[3].find('a').text.strip()
                actual = event_rows[4].text if event_rows[4].text else ""
                forecast = event_rows[5].text if event_rows[5].text else ""
                previous = event_rows[6].text if event_rows[6].text else ""
                new_event = cls(time,country, sentiment, name, actual, forecast, previous)
                day_events['events'].append(new_event)

            else:
                print('Error, unidentified event')

        return all_events

    def __str__(self):
        if len(self.name)>25:
            words = self.name.split(' ')
            multi_line=[]
            temp = []
            length = 0
            for word in words:
                length += len(word)+1
                if length>25:
                    multi_line.append(' '.join(temp))
                    temp=[]
                    length=0
                temp.append(word)

            event_str = f'{self.time:4}  {self.country:15}  {multi_line[0]:25}  {self.actual:8}  {self.forecast:8}  {self.previous:8}\n'
            for line in multi_line[1:]:
                event_str+=' '*30+f'{line:25}\n'

        else:
            event_str = f'{self.time:4}  {self.country:15}  {self.name:25}  {self.actual:8}  {self.forecast:8}  {self.previous:8}\n'

        return event_str

    @classmethod
    def fetch_events(cls,start_date: date, end_date: date):
        data = {
            "country[]": [72, 22, 5],
            "importance[]": 3,
            "dateFrom": str(start_date),  # "2023-02-01"
            "dateTo": str(end_date),
            "timeZone": 58,
            "timeFilter": "timeRemain",
            "currentTab": "custom",
            "submitFilters": 1,
            "limit_from": 0,
        }
        headers = {
            "Host": "www.investing.com",
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/109.0",
            "Accept": "*/*",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate, br",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://www.investing.com",
            "Connection": "keep-alive",
            "Referer": "https://www.investing.com/economic-calendar/",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin"
        }
        resp = httpx.post("https://www.investing.com/economic-calendar/Service/getCalendarFilteredData",
                                headers=headers, data=data)
        html = resp.json()['data']
        html = lh.fromstring(html)
        return html

# get_cookies_headers = {
#     "Host": "investing.com",
#     "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:109.0) Gecko/20100101 Firefox/109.0",
#     "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
#     "Accept-Language": "en-US,en;q=0.5",
#     "Accept-Encoding": "gzip, deflate, br",
#     "DNT": "1",
#     "Upgrade-Insecure-Requests": '1',
#     "Connection": "keep-alive",
#     "Sec-Fetch-Dest": "document",
#     "Sec-Fetch-Mode": "navigate",
#     "Sec-Fetch-Site": "none",
#     "Sec-Fetch-User": "?1"
# }
# # get_cookies= httpx.get("https://investing.com", headers=get_cookies_headers)
# cookies = get_cookies.cookies
# print(cookies)
#
# print(get_cookies.status_code)
