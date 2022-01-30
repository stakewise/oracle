from decouple import Choices, config

LOG_LEVEL = config("LOG_LEVEL", default="INFO")

REWARD_VOTE_FILENAME = "reward-vote.json"
DISTRIBUTOR_VOTE_FILENAME = "distributor-vote.json"
VALIDATOR_VOTE_FILENAME = "validator-vote.json"
TEST_VOTE_FILENAME = "test-vote.json"

# supported networks
MAINNET = "mainnet"
GOERLI = "goerli"
GNOSIS = "gnosis"
# TODO: enable gnosis once supported
NETWORK = config(
    "NETWORK",
    default=MAINNET,
    cast=Choices([MAINNET, GOERLI], cast=lambda net: net.lower()),
)

if NETWORK == MAINNET:
    AWS_S3_BUCKET_NAME = config("AWS_S3_BUCKET_NAME", default="oracle-votes-mainnet")
elif NETWORK == GNOSIS:
    AWS_S3_BUCKET_NAME = config("AWS_S3_BUCKET_NAME", default="oracle-votes-gnosis")
elif NETWORK == GOERLI:
    AWS_S3_BUCKET_NAME = config("AWS_S3_BUCKET_NAME", default="oracle-votes-goerli")

AWS_S3_REGION = config("AWS_S3_REGION", default="eu-central-1")

# health server settings
ENABLE_HEALTH_SERVER = config("ENABLE_HEALTH_SERVER", default=False, cast=bool)
HEALTH_SERVER_PORT = config("HEALTH_SERVER_PORT", default=8080, cast=int)
HEALTH_SERVER_HOST = config("HEALTH_SERVER_HOST", default="127.0.0.1", cast=str)

# required confirmation blocks
CONFIRMATION_BLOCKS: int = config("CONFIRMATION_BLOCKS", default=15, cast=int)
