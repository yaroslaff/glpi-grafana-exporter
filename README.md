# GLPI to Grafana exporter

This script exports GLPI statistics from database into JSON format, usable with [grafana-infinity-datasource](https://github.com/grafana/grafana-infinity-datasource) plugin of [Grafana](https://grafana.com/). Tested on GLPI version 10.0.6.



![image](demo/glpi-grafana-dashboard-small.png)

Example config:
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
(you can omit +driver part)


Use:
~~~
# make glpi.json with statistics for last year
glpi-grafana-exporter -c config.env --soft 365

# recalculate statistics for a last 3 days (for [daily] cron job)
glpi-grafana-exporter -c config.env --hard 3
~~~
