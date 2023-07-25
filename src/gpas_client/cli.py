import defopt

from gpas_client import lib

def test():
    return "cat"

def main():
    defopt.run(
        {"upload": test},
        no_negated_flags=True,
        strict_kwonly=False,
        short={},
    )
