import argparse
import os
import json
import datetime
import random
from dotenv import load_dotenv
from sqlalchemy import create_engine, MetaData, Table, func, select, cast, Date, desc

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, aliased
from sqlalchemy.ext.automap import automap_base

from .fake import fake_ticket_titles, fake_users

__version__ = '0.0.1'


incident_status_map = {
    1: 'new',
    2: 'assigned',
    3: 'planned',
    4: 'pending',
    5: 'solved',
    6: 'closed'
}
"""
from inc/commonitilobject.class.php
   const INCOMING      = 1; // new
   const ASSIGNED      = 2; // assign
   const PLANNED       = 3; // plan
   const WAITING       = 4; // waiting
   const SOLVED        = 5; // solved
   const CLOSED        = 6; // closed
   const ACCEPTED      = 7; // accepted
   const OBSERVED      = 8; // observe
   const EVALUATION    = 9; // evaluation
   const APPROVAL      = 10; // approbation
   const TEST          = 11; // test
   const QUALIFICATION = 12; // qualification
"""

incident_type_map = {
    1: 'incident',
    2: 'request'
}

incident_lohi_map = {
    1: 'very low',
    2: 'low',
    3: 'medium',
    4: 'high',
    5: 'very high'
}



def get_args(dotenv_file = None):

    load_dotenv(dotenv_path=dotenv_file)

    def_dburl=os.getenv('DBURL', 'mysql:///localhost/glpi')
    def_tickets_table=os.getenv('TICKETS_TABLE', 'glpi_tickets')
    def_users_table=os.getenv('USERS_TABLE', 'glpi_users')
    def_jsonfile=os.getenv('JSONFILE', 'glpi.json')
    def_open=int(os.getenv('OPEN','0'))

    parser = argparse.ArgumentParser(description=f'GLPI to Grafana exporter ver. {__version__}')
    parser.add_argument('-c','--config', metavar='CONFIG', default=None, help='path to dotenv config file')
    parser.add_argument('--db', metavar='database url', default=def_dburl,
                        help='Database URL e.g. mysql://glpi:glpi@localhost/glpi')
    parser.add_argument('--tickets', metavar='tickets_table', default=def_tickets_table,
                        help=f'Tickets table name e.g. glpi_tickets')
    parser.add_argument('--users', metavar='users_table', default=def_users_table,
                        help=f'Tickets table name e.g. glpi_users')
    parser.add_argument('--jsonfile', metavar='json file', default=def_jsonfile,
                        help='JSON file name e.g. glpi_tickets.json')
    parser.add_argument('--hard', metavar='DAYS', type=int, default=None, help='recalculate statistics for last N days')
    parser.add_argument('--soft', metavar='DAYS', type=int, default=None, help='calculate statistics for last N days (only if not exists)')
    parser.add_argument('--day', metavar='YYYY-MM-DD', default=None, 
                        help='calculate statistics for specific day')
    parser.add_argument('-o','--open', metavar='N_TICKETS', default=def_open, help='Include last N tickets in statistics')
    parser.add_argument('-f','--fake', default=False, action='store_true', help='Mask real sensitive data with fake (for demo purpose)')

    args = parser.parse_args()    

    if dotenv_file is None and args.config:
        args = get_args(dotenv_file=args.config)
    
    return args


def load_json(filename):

    default = {
        'summary': [],
        'current': [],
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


def update_statistics(engine: Engine, Tickets: Table, Users: Table, statistics: dict, args: argparse.Namespace):

    statistics['summary'] = list()
    statistics['current'] = list()
    statistics['last_tickets'] = list()


    with Session(engine) as session:
        
        row_count = session.query(func.count(Tickets.id)).scalar()
        statistics['summary'].append({'status':'total', 'count': row_count })

        result = session.query(
            Tickets.status,
            func.count().label('count')
        ).group_by(Tickets.status).all()
        status_count = {status: count for status, count in result}


        for i in range(1,6):
            statistics['current'].append({'status': incident_status_map.get(i, str(i)), 
                                          'count': status_count.get(i, 0)})
            

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

        if args.open:

            users = dict()

            users_results = (
                session.query(Users)
                .all()
            )
            for user in users_results:
                users[user.id] = f'{user.realname} {user.firstname}'

            results = (
                session.query(Tickets)
                .filter(Tickets.status != 6)
                .order_by(desc(Tickets.date))
                .limit(args.open)
                .all()
            )



            for row in results:

                t = {
                    'id': row.id,
                    'name': row.name if not args.fake else random.choice(fake_ticket_titles),
                    'status': incident_status_map.get(row.status, str(row.status)),
                    'date': row.date.strftime('%Y-%m-%d %H:%M'),
                    'solvedate': row.solvedate.strftime('%Y-%m-%d %H:%M') if row.solvedate else "",

                    'type': incident_type_map.get(row.type, str(row.type)),

                    'impact': incident_lohi_map.get(row.impact, str(row.impact)),
                    'priority': incident_lohi_map.get(row.priority, str(row.priority)),
                    'urgency': incident_lohi_map.get(row.urgency, str(row.urgency)),

                    # users
                    'lastupdater': users[row.users_id_lastupdater] if not args.fake else random.choice(fake_users),
                    'recipient': users[row.users_id_recipient] if not args.fake else random.choice(fake_users),
                }
                statistics['last_tickets'].append(t)



def main():
    print("GLPI to Grafana exporter")
    args = get_args()
    
    # connect to database
    try:
        engine = create_engine(args.db)
    except ModuleNotFoundError as e:
        print(f"Module not installed: {e.name}")
        print("Install with proper extras:")
        print("  pipx install glpi-grafana-exporter[mysql]") 
        print("  pipx install glpi-grafana-exporter[postgresql]")

        return

    # Reflect the database schema
    Base = automap_base()
    Base.prepare(engine, reflect=True)

    statistics = load_json(args.jsonfile)

    # Access the glpi_tickets table
    Tickets = Base.classes.get(args.tickets)
    # Access the glpi_tickets table
    Users = Base.classes.get(args.users)

    update_statistics(engine, Tickets, Users, statistics, args)

    print(f"Saving {len(statistics['daily'])} days statistics to {args.jsonfile}")
    with open(args.jsonfile, 'w') as f:        
        json.dump(statistics, f, indent=4)



