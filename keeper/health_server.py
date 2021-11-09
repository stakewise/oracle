from collections import Counter

from aiohttp import web

from keeper.utils import can_submit, get_keeper_params, get_oracles_votes

keeper_routes = web.RouteTableDef()


@keeper_routes.get("/")
async def health(request):
    try:
        # 1. Fetch current nonces of the validators, rewards and the total number of oracles
        params = get_keeper_params()
        if params.paused:
            return web.Response(text="keeper 0")

        # 2. Resolve and fetch latest votes of the oracles for validators and rewards
        votes = get_oracles_votes(
            rewards_nonce=params.rewards_nonce,
            validators_nonce=params.validators_nonce,
            oracles=params.oracles,
        )

        # 3. Check whether there are no submitted votes
        counter = Counter(
            [
                (vote["total_rewards"], vote["activated_validators"])
                for vote in votes.rewards
            ]
        )
        most_voted_rewards = counter.most_common(1)

        counter = Counter(
            [(vote["merkle_root"], vote["merkle_proofs"]) for vote in votes.distributor]
        )
        most_voted_distributor = counter.most_common(1)

        counter = Counter(
            [
                (vote["public_key"], vote["operator"])
                for vote in votes.initialize_validator
            ]
        )
        most_voted_init_validator = counter.most_common(1)

        counter = Counter(
            [
                (vote["public_key"], vote["operator"])
                for vote in votes.finalize_validator
            ]
        )
        most_voted_finalize_validator = counter.most_common(1)

        if not (
            (
                most_voted_rewards
                and can_submit(most_voted_rewards[0][1], len(params.oracles))
            )
            or (
                most_voted_distributor
                and can_submit(most_voted_distributor[0][1], len(params.oracles))
            )
            or (
                most_voted_init_validator
                and can_submit(most_voted_init_validator[0][1], len(params.oracles))
            )
            or (
                most_voted_finalize_validator
                and can_submit(most_voted_finalize_validator[0][1], len(params.oracles))
            )
        ):
            return web.Response(text="keeper 0")
    except:  # noqa: E722
        pass

    return web.Response(text="keeper 1")
