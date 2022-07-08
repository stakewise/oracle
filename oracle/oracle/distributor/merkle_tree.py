from collections import OrderedDict
from typing import Dict, List, Tuple, Union

from eth_typing import ChecksumAddress
from eth_typing.encoding import HexStr
from eth_utils.crypto import keccak
from web3 import Web3

from .types import Claim, Claims, Rewards

w3 = Web3()


# Inspired by https://github.com/Uniswap/merkle-distributor/blob/master/src/merkle-tree.ts
class MerkleTree(object):
    def __init__(self, elements: List[bytes]):
        self.elements: List[bytes] = sorted(list(set(elements)))
        self.element_positions: Dict[bytes, int] = {
            el: index for index, el in enumerate(self.elements)
        }

        # create layers
        self.layers: List[List[bytes]] = self.get_layers(self.elements)

    def get_layers(self, elements: List[bytes]) -> List[List[bytes]]:
        if not elements:
            raise ValueError("Empty tree")

        layers = [elements]

        # get next layer until we reach the root
        while len(layers[-1]) > 1:
            layers.append(self.get_next_layer(layers[-1]))

        return layers

    def get_root(self) -> bytes:
        return self.layers[-1][0]

    def get_hex_root(self) -> HexStr:
        return w3.toHex(self.get_root())

    def get_proof(self, element: bytes) -> List[bytes]:
        index = self.element_positions.get(element, None)
        if index is None:
            raise ValueError("Element is not in Merkle Tree")

        proof: List[bytes] = []
        for layer in self.layers:
            pair_element = MerkleTree.get_pair_element(index, layer)
            if pair_element:
                proof.append(pair_element)

            index = index // 2

        return proof

    def get_hex_proof(self, element: bytes) -> List[HexStr]:
        proof = self.get_proof(element)
        return [w3.toHex(p) for p in proof]

    @staticmethod
    def get_next_layer(elements: List[bytes]) -> List[bytes]:
        next_layer: List[bytes] = []
        for i, el in enumerate(elements):
            if i % 2 == 0:
                # Hash the current element with its pair element
                if i < len(elements) - 1:
                    combined_hash = MerkleTree.combine_hash(el, elements[i + 1])
                else:
                    combined_hash = el

                next_layer.append(combined_hash)

        return next_layer

    @staticmethod
    def combine_hash(first: bytes, second: bytes) -> bytes:
        if not first:
            return second

        if not second:
            return first

        return keccak(primitive=b"".join(sorted([first, second])))

    @staticmethod
    def get_pair_element(index: int, layer: List[bytes]) -> Union[bytes, None]:
        if index % 2 == 0:
            pair_index = index + 1
        else:
            pair_index = index - 1

        if pair_index < len(layer):
            return layer[pair_index]

        return None


def get_merkle_node(
    index: int,
    tokens: List[ChecksumAddress],
    account: ChecksumAddress,
    values: List[int],
) -> bytes:
    """Generates node for merkle tree."""
    encoded_data: bytes = w3.codec.encode_abi(
        ["uint256", "address[]", "address", "uint256[]"],
        [index, tokens, account, values],
    )
    return w3.keccak(primitive=encoded_data)


def calculate_merkle_root(rewards: Rewards) -> Tuple[HexStr, Claims]:
    """Calculates merkle root and claims for the rewards."""
    merkle_elements: List[bytes] = []
    accounts: List[ChecksumAddress] = sorted(rewards.keys())
    claims: Claims = OrderedDict()
    for i, account in enumerate(accounts):
        tokens: List[ChecksumAddress] = sorted(rewards[account].keys())
        claim: Claim = Claims(
            index=i, tokens=tokens, values=[rewards[account][t] for t in tokens]
        )
        claims[account] = claim

        merkle_element: bytes = get_merkle_node(
            index=i,
            account=account,
            tokens=tokens,
            values=[int(val) for val in claim["values"]],
        )
        merkle_elements.append(merkle_element)

    merkle_tree = MerkleTree(merkle_elements)

    # collect proofs
    for i, account in enumerate(accounts):
        proof: List[HexStr] = merkle_tree.get_hex_proof(merkle_elements[i])
        claims[account]["proof"] = proof

    # calculate merkle root
    merkle_root: HexStr = merkle_tree.get_hex_root()

    return merkle_root, claims
