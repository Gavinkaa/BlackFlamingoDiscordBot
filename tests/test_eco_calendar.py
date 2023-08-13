from datetime import timedelta, date

import eco_calendar

# html = pq(filename="test_html.html")
# html_events = lh.parse("test_html.html")
# print(html)
html_events = eco_calendar.Event.fetch_events(start_date=date.today(), end_date=date.today() + timedelta(days=7))
print(html_events)

# events = eco_calendar.Event.parse_events(html_events)
# eco_calendar.Event.embed_events(events)
#
#
# def _calendar(ctx, nb_days=7):
#     if nb_days > 30:
#         nb_days = 30
#     # Get events from investing.com, returns list of days {timestamp:,events:}
#     events = eco_calendar.Event.fetch_events(date.today(), date.today() + timedelta(days=nb_days))
#     header_str = f"{'Time':4}  {'Country':15}  {'Event':25}  {'Actual':8}  {'Forecast':8}  {'Previous':8}\n"
#     events_str = ""
#     for day in events:
#         events_str += f"====== {day['event_day']} ======\n"
#         events_str += "".join([str(event) for event in day['events']])
