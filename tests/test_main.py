import random

from egobooster import binary_search


def test_main():
    aa = [1, 1, 6, 6, 8, 9, 10, 11, 12, 13]
    rand = random.Random(42)

    for _ in range(10000):
        n = rand.randint(0, len(aa))
        a = sorted(rand.sample(aa, n))
        ins = rand.randint(0, 14)
        index = binary_search(0, len(a), lambda i: a[i] < ins)
        for x in a[:index]:
            assert x < ins, f"Wanted to insert {ins} into {a} at index {index}"
        for x in a[index:]:
            assert not (x < ins), f"Wanted to insert {ins} into {a} at index {index}"
