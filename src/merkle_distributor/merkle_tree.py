from typing import List, Union, Dict

from eth_typing import HexStr
from eth_utils import keccak
from web3 import Web3


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
        return Web3.toHex(self.get_root())

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
        return [Web3.toHex(p) for p in proof]

    @staticmethod
    def get_next_layer(elements: List[bytes]) -> List[bytes]:
        next_layer: List[bytes] = []
        for i, el in enumerate(elements):
            if i % 2 == 0:
                # Hash the current element with its pair element
                next_layer.append(
                    MerkleTree.combine_hash(
                        el, elements[i + 1] if i < len(elements) - 1 else None
                    )
                )

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
