# GLPI to Grafana exporter

This script exports GLPI statistics from database into JSON format, usable with [grafana-infinity-datasource](https://github.com/grafana/grafana-infinity-datasource) plugin of [Grafana](https://grafana.com/). Tested on GLPI version 10.0.6.

![image](https://raw.githubusercontent.com/yaroslaff/glpi-grafana-exporter/refs/heads/master/demo/glpi-grafana-dashboard-small.png)

## Install
~~~
pipx install glpi-grafana-exporter[mysql]
~~~
(or postgresql)

Example config (`config.env`):
~~~
DBURL=mysql:///support
TICKETS_TABLE=glpi_tickets
USERS_TABLE=glpi_users
JSONFILE=/var/www/html/statistics/glpi.json
OPEN=25
~~~

DBURL is in SQLAlchemy format: `dialect+driver://username:password@host:port/database`, e.g.:
~~~
postgresql+psycopg2://user:password@localhost:5432/mydatabase
mysql://user:password@localhost:3306/mydatabase
~~~
(you can omit `+driver` part)


## Make JSON file 
~~~
# make glpi.json with statistics for last year
glpi-grafana-exporter -c config.env --hard 365

# recalculate statistics for a last 3 days (for [daily] cron job)
glpi-grafana-exporter -c config.env --hard 3
~~~
at this step you get glpi.json file for Grafana with Infinity Datasource plugin. Update it from cron job.

## Make grafana dashboard
1. Install [Grafana Infinity Datasource
](https://grafana.com/grafana/plugins/yesoreyeram-infinity-datasource/) plugin
2. Configure it (Connection > Data Sources > yesoreyeram-infinity-datasource > Security), to allow "https://raw.githubusercontent.com/" (for demo JSON) or your URL. Save & test.
3. use [demo/dashboard.json](https://raw.githubusercontent.com/yaroslaff/glpi-grafana-exporter/refs/heads/master/demo/dashboard.json) to create dashboard in Grafana (or Grafana Cloud)
