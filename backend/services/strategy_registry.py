# Strategy Registry
# Register new strategies here as they are added.

STRATEGY_REGISTRY = {}

def register_strategy(name: str, strategy_class):
    STRATEGY_REGISTRY[name] = strategy_class

def get_strategy(name: str):
    return STRATEGY_REGISTRY.get(name)

def list_strategies():
    return list(STRATEGY_REGISTRY.keys())
