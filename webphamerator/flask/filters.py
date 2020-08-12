import datetime
import humanize
from flask_sqlalchemy import Blueprint

bp = Blueprint("filters", __name__)

@bp.template_filter('replaceifequal')
def replaceifequal(arg, value, replace_with):
    if arg == value:
        return replace_with


@bp.template_filter('humandate')
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


@bp.template_filter('isodate')
def isodate(date):
    if date is not None:
        return date.isoformat() + 'Z'


@bp.template_filter('toclocktime')
def toclocktime(timedelta):
    total_seconds = int(timedelta.total_seconds())
    if total_seconds == 0:
        hours = 0
        minutes = 0
        seconds = 0
    else:
        hours = total_seconds / 3600
        if (total_seconds % 3600) == 0:
            minutes = 0
        else:
            minutes = (total_seconds % 3600) / 60
        seconds = total_seconds % 60

    return '{0:02d}:{1:02d}:{2:02d}'.format(hours, minutes, seconds)
