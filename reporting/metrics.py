from prometheus_client import Gauge

# Prometheus metrics
REPORTER_BALANCE = Gauge('reporter_balance', 'Current balance of the reporter account (ETH)')
