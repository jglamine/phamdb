import datetime
import humanize
from webphamerator.app import app

@app.template_filter('replaceifequal')
def replaceifequal(arg, value, replace_with):
    if arg == value:
        return replace_with

@app.template_filter('humandate')
def humandate(timestamp):
    if datetime.datetime.utcnow() - timestamp < datetime.timedelta(days=1):
        human_delta = humanize.naturaltime(timestamp + (datetime.datetime.now() - datetime.datetime.utcnow()))
        if str(human_delta) == 'now':
            human_delta = 'a few seconds ago'
        return human_delta
    month, day, year = timestamp.strftime('%B %d %Y').split()
    day = int(day)
    year = int(year)
    if year == datetime.datetime.utcnow().year:
        return '{} {}'.format(month, day)
    return '{} {}, {}'.format(month, day, year)

@app.template_filter('isodate')
def isodate(date):
    if date is not None:
        return date.isoformat() + 'Z'
