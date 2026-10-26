FROM python:3.12-slim

WORKDIR /app
COPY index.html server.py ./

ENV DASHBOARD_PORT=8888
ENV INFLUX_HOST=influxdb
ENV INFLUX_PORT=8086

EXPOSE 8888
CMD ["python3", "server.py"]
