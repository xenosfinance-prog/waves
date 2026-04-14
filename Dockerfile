FROM python:3.11-slim

WORKDIR /app

RUN pip install flask flask-cors anthropic yfinance pandas numpy plotly

COPY ew_server.py .

EXPOSE 5001

CMD ["python", "ew_server.py"]
