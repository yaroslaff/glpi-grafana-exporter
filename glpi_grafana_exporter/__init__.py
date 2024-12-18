import argparse
import os
import json
import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, func, select, cast, Date

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from sqlalchemy.ext.automap import automap_base

__version__ = '0.0.1'

def get_args(dotenv_file = None):

    load_dotenv(dotenv_path=dotenv_file)

    def_dburl=os.getenv('DBURL', 'mysql:///localhost/glpi')
    def_tickets=os.getenv('TICKETS', 'glpi_tickets')
    def_jsonfile=os.getenv('JSONFILE', 'glpi.json')

    parser = argparse.ArgumentParser(description=f'GLPI to Grafana exporter ver. {__version__}')
    parser.add_argument('--db', metavar='database url', default=def_dburl,
                        help='Database URL e.g. mysql://glpi:glpi@localhost/glpi')
    parser.add_argument('--tickets', metavar='tickets table', default=def_tickets,
                        help='Tickets table name e.g. glpi_tickets')
    parser.add_argument('--jsonfile', metavar='json file', default=def_jsonfile,
                        help='JSON file name e.g. glpi_tickets.json')
    parser.add_argument('--hard', metavar='DAYS', type=int, default=None, help='recalculate statistics for last N days')
    parser.add_argument('--soft', metavar='DAYS', type=int, default=None, help='calculate statistics for last N days (only if not exists)')
    parser.add_argument('--day', metavar='YYYY-MM-DD', default=None, 
                        help='calculate statistics for specific day')
    parser.add_argument('-c','--config', metavar='CONFIG', default=None, help='path to dotenv config file')

    args = parser.parse_args()    

    if dotenv_file is None and args.config:
        args = get_args(dotenv_file=args.config)
    
    return args


def load_json(filename):

    default = {
        'summary': [],
        'daily': []
    }

    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return dict(default)



def get_daily_statistics(session, Tickets: Table,  date: str):
   # Count rows where solvedate matches the given date
        solve_count = session.query(func.count()).filter(
            cast(Tickets.solvedate, Date) == date
        ).scalar()
        open_count = session.query(func.count()).filter(
            cast(Tickets.date, Date) == date
        ).scalar()

        daily = {
            'date': date,
            'solved': solve_count,
            'open': open_count
        }

        return daily


def update_statistics(engine: Engine, Tickets: Table, statistics: dict, args):
    with Session(engine) as session:
        # Count the rows

        row_count = session.query(func.count(Tickets.id)).scalar()
        statistics['summary'].append({'status':'total', 'count': row_count })

        result = session.query(
            Tickets.status,
            func.count().label('count')
        ).group_by(Tickets.status).all()
        status_count = {status: count for status, count in result}

        statistics['summary'].append({'status': 'new', 'count': status_count.get(1, 0)})
        statistics['summary'].append({'status': 'open', 'count': status_count.get(2, 0)})
        statistics['summary'].append({'status': 'waiting', 'count': status_count.get(3, 0)})
        statistics['summary'].append({'status': 'inprogress', 'count': status_count.get(4, 0)})
        statistics['summary'].append({'status': 'resolved', 'count': status_count.get(5, 0)})
        statistics['summary'].append({'status': 'closed', 'count': status_count.get(6, 0)})
        
        


        if args.day:
            day = datetime.datetime.strptime(args.day, '%Y-%m-%d').date()
            daily = get_daily_statistics(session, Tickets, args.day)
            statistics['daily'].append(daily)

        if args.soft:
            today = datetime.date.today()
            for i in range(args.soft):
                day = today - datetime.timedelta(days=i)
                daystr =  day.isoformat()
                
                if any(ds.get("date") == daystr for ds in statistics['daily']):
                    continue

                daily = get_daily_statistics(session, Tickets, day.isoformat())
                statistics['daily'].append(daily)

        if args.hard:
            today = datetime.date.today()
            for i in range(args.hard):
                day = today - datetime.timedelta(days=i)
                daystr =  day.isoformat()

                if any(ds.get("date") == daystr for ds in statistics['daily']):
                    statistics['daily'] = [ds for ds in statistics['daily'] if ds.get("date") != daystr]

                daily = get_daily_statistics(session, Tickets, day.isoformat())
                statistics['daily'].append(daily)




def main():
    print("GLPI to Grafana exporter")
    args = get_args()
    
    # connect to database
    try:
        engine = create_engine(args.db)
    except ModuleNotFoundError as e:
        print(f"Module not installed: {e.name}")
        print("Install with proper extras:")
        print("  pip install glpi-grafana-exporter[mysql]")
        print("  pip install glpi-grafana-exporter[postgresql]")

        return

    # Reflect the database schema
    Base = automap_base()
    Base.prepare(engine, reflect=True)

    statistics = load_json(args.jsonfile)

    # Access the glpi_tickets table
    Tickets = Base.classes.get(args.tickets)

    update_statistics(engine, Tickets, statistics, args)

    with open(args.jsonfile, 'w') as f:
        json.dump(statistics, f, indent=4)



